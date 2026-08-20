"""Reusable public Concept -> Resource -> Pages -> Chunks sidecar registry.

The registry is derived from real Neo4j, public Chroma and reviewed PDF page
coverage.  It never writes to Neo4j, Chroma, plans or learner-owned data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pathly_neo4j import require_neo4j
from verified_golden_sources import GOLDEN_PATH, GOLDEN_PATH_VERSION, VerifiedGoldenSourceRegistry


PUBLIC_SOURCE_VERSION = "public-concept-source-p1-v1"

ALIASES = {
    "Linear Separability": ["linear separable", "linearly separable", "linear decision boundary"],
    "XOR": ["exclusive or", "xor problem", "xor classification"],
    "Neural Networks": ["neural network", "multilayer perceptron", "mlp"],
    "Activation Functions": ["activation function", "nonlinearity", "nonlinear activation"],
    "Gradient Descent": ["gradient optimization", "stochastic gradient descent", "sgd"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _canonical_id(name: str, neo4j_id: str | None = None) -> str:
    if neo4j_id:
        return str(neo4j_id)
    return "canonical:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class PublicConceptSourceRegistry:
    """Read-only-source, rebuildable SQLite projection shared across plans."""

    def __init__(self, db_path: str | Path, kg_dir: str | Path):
        self.db_path = Path(db_path)
        self.kg_dir = Path(kg_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.reviewed = VerifiedGoldenSourceRegistry(self.kg_dir)
        self.migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS public_concept_sources (
                    link_id TEXT PRIMARY KEY,
                    canonical_concept_id TEXT NOT NULL,
                    canonical_concept_name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_title TEXT,
                    page_sequence_json TEXT NOT NULL,
                    chunk_ids_json TEXT NOT NULL,
                    relevance_score REAL NOT NULL,
                    coverage_score REAL NOT NULL,
                    match_method TEXT NOT NULL,
                    match_reason TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    coverage_status TEXT NOT NULL,
                    neo4j_node_status TEXT NOT NULL,
                    neo4j_resource_status TEXT NOT NULL,
                    source_url TEXT,
                    license_status TEXT,
                    source_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(canonical_concept_id, resource_id, source_version)
                );
                CREATE INDEX IF NOT EXISTS idx_public_source_concept
                    ON public_concept_sources(canonical_concept_id, source_version);
                CREATE INDEX IF NOT EXISTS idx_public_source_resource
                    ON public_concept_sources(resource_id, source_version);
                """
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["aliases"] = json.loads(item.pop("aliases_json") or "[]")
        item["page_sequence"] = json.loads(item.pop("page_sequence_json") or "[]")
        item["chunk_ids"] = json.loads(item.pop("chunk_ids_json") or "[]")
        item["source_scope"] = "public"
        item["source_readiness"] = "public_registry"
        return item

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT count(*) FROM public_concept_sources").fetchone()[0])

    def list_all(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM public_concept_sources ORDER BY canonical_concept_name, resource_id"
            ).fetchall()
        return [self._decode(row) for row in rows]

    def resolve(self, *, concept_id: str, concept_name: str) -> dict[str, Any] | None:
        requested = {_normal(concept_id), _normal(concept_name)} - {""}
        candidates = []
        for item in self.list_all():
            names = {
                _normal(item["canonical_concept_id"]),
                _normal(item["canonical_concept_name"]),
                *(_normal(alias) for alias in item["aliases"]),
            }
            if requested & names:
                candidates.append(item)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                item["review_status"] == "verified",
                item["coverage_score"],
                item["relevance_score"],
            ),
            reverse=True,
        )
        return candidates[0]

    def replace_all(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stamp = _now()
        with self._connect() as connection:
            connection.execute("DELETE FROM public_concept_sources")
            for item in rows:
                identity = f"{item['canonical_concept_id']}|{item['resource_id']}|{PUBLIC_SOURCE_VERSION}"
                link_id = "public-source-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
                connection.execute(
                    """
                    INSERT INTO public_concept_sources (
                        link_id, canonical_concept_id, canonical_concept_name, aliases_json,
                        resource_id, document_id, document_title, page_sequence_json,
                        chunk_ids_json, relevance_score, coverage_score, match_method,
                        match_reason, review_status, coverage_status, neo4j_node_status,
                        neo4j_resource_status, source_url, license_status, source_version,
                        created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        link_id, item["canonical_concept_id"], item["canonical_concept_name"],
                        json.dumps(item.get("aliases") or [], ensure_ascii=False), item["resource_id"],
                        item["document_id"], item.get("document_title"),
                        json.dumps(item.get("page_sequence") or [], ensure_ascii=False),
                        json.dumps(item.get("chunk_ids") or [], ensure_ascii=False),
                        float(item.get("relevance_score") or 0), float(item.get("coverage_score") or 0),
                        item["match_method"], item["match_reason"], item["review_status"],
                        item["coverage_status"], item["neo4j_node_status"],
                        item["neo4j_resource_status"], item.get("source_url"),
                        item.get("license_status"), PUBLIC_SOURCE_VERSION, stamp, stamp,
                    ),
                )
        return self.list_all()

    def _chroma_chunks(self, resource_id: str) -> tuple[list[str], list[dict[str, Any]]]:
        import chromadb

        collection = chromadb.PersistentClient(path=str(self.kg_dir / "data" / "chroma")).get_collection("kg_chunks")
        result = collection.get(where={"resource_id": resource_id}, include=["metadatas"])
        return [str(item) for item in result.get("ids") or []], list(result.get("metadatas") or [])

    def rebuild(self) -> dict[str, Any]:
        """Rebuild using a mandatory real Neo4j query and public Chroma reads."""
        os.environ["KG_BACKEND"] = "neo4j"
        health = require_neo4j(start_desktop=False)
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))
        database = os.getenv("NEO4J_DATABASE", "neo4j")
        reviewed = {item["concept_name"]: item.get("source") for item in self.reviewed.audit()}
        output: list[dict[str, Any]] = []
        driver = GraphDatabase.driver(uri, auth=auth)
        try:
            with driver.session(database=database) as session:
                for name in GOLDEN_PATH:
                    graph = session.run(
                        """
                        OPTIONAL MATCH (c:Concept)
                        WHERE toLower(c.name) = toLower($name)
                        OPTIONAL MATCH (c)-[:HAS_RESOURCE]->(r:Resource)
                        RETURN CASE WHEN c IS NULL THEN {} ELSE properties(c) END AS concept,
                               collect(DISTINCT properties(r)) AS resources
                        """,
                        name=name,
                    ).single()
                    concept = dict((graph or {}).get("concept") or {})
                    neo_resources = [dict(item) for item in ((graph or {}).get("resources") or []) if item]
                    source = reviewed.get(name)
                    if not source:
                        continue
                    resource_id = str(source["resource_id"])
                    chunk_ids, metadata = self._chroma_chunks(resource_id)
                    neo_ids = {str(item.get("id") or item.get("resource_id") or item.get("sha256") or "") for item in neo_resources}
                    canonical_id = _canonical_id(name, str(concept.get("id") or concept.get("concept_id") or "") or None)
                    pages = [dict(item) for item in source.get("page_sequence") or []]
                    coverage_status = "verified_pages_and_resource_chunks" if chunk_ids else "verified_pages_without_resource_chunks"
                    output.append(
                        {
                            "canonical_concept_id": canonical_id,
                            "canonical_concept_name": name,
                            "aliases": ALIASES.get(name, []),
                            "resource_id": resource_id,
                            "document_id": source.get("document_id") or f"public:{resource_id}",
                            "document_title": source.get("document_title"),
                            "page_sequence": pages,
                            "chunk_ids": chunk_ids,
                            "relevance_score": 1.0,
                            "coverage_score": 1.0,
                            "match_method": "neo4j_chroma_reviewed_pages",
                            "match_reason": source.get("match_reason") or source.get("reason") or "Reviewed public source coverage.",
                            "review_status": "verified",
                            "coverage_status": coverage_status,
                            "neo4j_node_status": "present" if concept else "missing",
                            "neo4j_resource_status": "linked" if resource_id in neo_ids else "missing_or_id_mismatch",
                            "source_url": next((item.get("url") for item in neo_resources if str(item.get("id") or item.get("sha256") or "") == resource_id), None),
                            "license_status": "needs_source_review",
                            "chroma_metadata_count": len(metadata),
                        }
                    )
        finally:
            driver.close()
        saved = self.replace_all(output)
        return {
            "source_version": PUBLIC_SOURCE_VERSION,
            "kg_source": health["actual_backend"],
            "neo4j_query_verified": health["query_verified"],
            "concept_count": len(saved),
            "verified_count": sum(item["review_status"] == "verified" for item in saved),
            "missing_neo4j_nodes": [item["canonical_concept_name"] for item in saved if item["neo4j_node_status"] == "missing"],
            "records": saved,
        }


class PublicThenReviewedResolver:
    """Prefer reusable public rows while keeping reviewed coverage during rebuilds."""

    def __init__(self, public_registry: PublicConceptSourceRegistry, reviewed_registry: Any):
        self.public_registry = public_registry
        self.reviewed_registry = reviewed_registry

    def resolve(self, *, concept_id: str, concept_name: str) -> dict[str, Any] | None:
        return self.public_registry.resolve(concept_id=concept_id, concept_name=concept_name) or self.reviewed_registry.resolve(
            concept_id=concept_id, concept_name=concept_name
        )
