"""Read-only audit for Pathly's verified neural-foundations chain."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pathly_neo4j import require_neo4j
from verified_golden_sources import GOLDEN_PATH, VerifiedGoldenSourceRegistry


ROOT = Path(__file__).resolve().parent
KG_DIR = (ROOT.parent / "KG_construction").resolve()
DEFAULT_OUTPUT = ROOT / "artifacts" / "k1_golden_chain_audit.json"


def _load_environment() -> None:
    sys.path.insert(0, str(KG_DIR))
    try:
        from env_loader import load_project_env

        load_project_env()
    except (ImportError, AttributeError):
        from dotenv import load_dotenv

        load_dotenv(KG_DIR.parent / ".env", override=False)
        load_dotenv(KG_DIR / ".env", override=False)


def _normal(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").split())


def classify_concept(
    concept_name: str,
    *,
    node_exists: bool,
    prerequisites: list[str],
    unlocks: list[str],
    source_verified: bool,
    chroma_chunks: int,
    chroma_has_pages: bool,
) -> dict[str, str]:
    """Derive auditable statuses without mutating any source system."""
    prereq = {_normal(item) for item in prerequisites}
    next_nodes = {_normal(item) for item in unlocks}
    name = _normal(concept_name)
    relationship = "verified"
    reasons: list[str] = []
    if not node_exists:
        relationship = "needs_relationship_review"
        reasons.append("canonical Neo4j Concept node is missing")
    if name == "neural networks" and "activation functions" in prereq:
        relationship = "needs_relationship_review"
        reasons.append("Activation Functions currently points into Neural Networks, creating a pedagogical cycle")
    if name == "activation functions" and "neural networks" in next_nodes:
        relationship = "needs_relationship_review"
        reasons.append("Neural Networks and Activation Functions form a prerequisite cycle")
    if name == "gradient descent" and "backpropagation" in prereq:
        relationship = "needs_relationship_review"
        reasons.append("Backpropagation is currently a prerequisite of Gradient Descent and needs direction review")
    if name == "linear separability" and "xor" not in next_nodes:
        relationship = "needs_relationship_review"
        reasons.append("the intended Linear Separability to XOR bridge is absent")

    if not source_verified:
        source = "needs_source"
        reasons.append("no validated continuous PDF sequence is available")
    elif chroma_chunks <= 0:
        source = "usable"
        reasons.append("PDF sequence is validated but no public Chroma chunks were found")
    elif not chroma_has_pages:
        source = "usable"
        reasons.append("content is indexed, but Chroma chunks do not preserve page metadata")
    else:
        source = "verified"

    overall = "verified" if node_exists and relationship == "verified" and source == "verified" else (
        "needs_source" if source == "needs_source" else "needs_relationship_review"
    )
    return {
        "node_status": "verified" if node_exists else "needs_relationship_review",
        "relationship_status": relationship,
        "source_status": source,
        "overall_status": overall,
        "reason": "; ".join(reasons) or "canonical node, relationships, and traceable source coverage passed",
    }


def _chroma_resource_stats(resource_id: str) -> dict[str, Any]:
    import chromadb

    client = chromadb.PersistentClient(path=str(KG_DIR / "data" / "chroma"))
    collection = client.get_collection("kg_chunks")
    result = collection.get(where={"resource_id": resource_id}, include=["metadatas"])
    metadata = result.get("metadatas") or []
    page_keys = ("page", "page_number", "page_start", "page_end")
    return {
        "chunk_count": len(result.get("ids") or []),
        "chunks_with_page_metadata": sum(1 for item in metadata if any(item.get(key) not in (None, "") for key in page_keys)),
        "chunks_with_concept_metadata": sum(1 for item in metadata if item.get("concept_id") or item.get("concept_name")),
    }


def run_audit() -> dict[str, Any]:
    _load_environment()
    os.environ["KG_BACKEND"] = "neo4j"
    health = require_neo4j(start_desktop=False)
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    registry = VerifiedGoldenSourceRegistry(KG_DIR)
    verified = {item["concept_name"]: item for item in registry.audit()}
    rows: list[dict[str, Any]] = []
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        with driver.session(database=database) as session:
            for concept_name in GOLDEN_PATH:
                graph = session.run(
                    """
                    OPTIONAL MATCH (c:Concept) WHERE toLower(c.name)=toLower($name)
                    OPTIONAL MATCH (p:Concept)-[:PREREQUISITE_OF]->(c)
                    WITH c, collect(DISTINCT p.name) AS prerequisites
                    OPTIONAL MATCH (c)-[:PREREQUISITE_OF]->(n:Concept)
                    WITH c, prerequisites, collect(DISTINCT n.name) AS unlocks
                    OPTIONAL MATCH (c)-[:HAS_RESOURCE]->(r:Resource)
                    WITH c, prerequisites, unlocks, collect(DISTINCT properties(r)) AS resources
                    OPTIONAL MATCH (t:Topic)-[]-(c)
                    RETURN c IS NOT NULL AS node_exists,
                           CASE WHEN c IS NULL THEN {} ELSE properties(c) END AS concept,
                           prerequisites, unlocks, resources,
                           collect(DISTINCT properties(t)) AS topics
                    """,
                    name=concept_name,
                ).single()
                canonical = session.run(
                    """
                    OPTIONAL MATCH (c:CanonicalConcept) WHERE toLower(c.name)=toLower($name)
                    OPTIONAL MATCH (p:CanonicalConcept)-[:PREREQUISITE_OF]->(c)
                    WITH c, collect(DISTINCT p.name) AS prerequisites
                    OPTIONAL MATCH (c)-[:PREREQUISITE_OF]->(n:CanonicalConcept)
                    WITH c, prerequisites, collect(DISTINCT n.name) AS unlocks
                    OPTIONAL MATCH (c)-[:HAS_TEACHING_CLAIM]->(claim:TeachingClaim)
                    OPTIONAL MATCH (c)-[:HAS_MISCONCEPTION]->(m:Misconception)
                    OPTIONAL MATCH (a:AssessmentTarget)-[:ASSESSES]->(c)
                    RETURN c IS NOT NULL AS node_exists, prerequisites, unlocks,
                           count(DISTINCT claim) AS claim_count,
                           count(DISTINCT m) AS misconception_count,
                           count(DISTINCT a) AS target_count
                    """,
                    name=concept_name,
                ).single()
                source = (verified.get(concept_name) or {}).get("source")
                resource_id = str((source or {}).get("resource_id") or "")
                chroma = _chroma_resource_stats(resource_id) if resource_id else {
                    "chunk_count": 0, "chunks_with_page_metadata": 0, "chunks_with_concept_metadata": 0
                }
                canonical_graph = {
                    "node_exists": bool(canonical["node_exists"]),
                    "prerequisites": list(canonical["prerequisites"] or []),
                    "unlocks": list(canonical["unlocks"] or []),
                }
                verdict = classify_concept(
                    concept_name,
                    node_exists=canonical_graph["node_exists"],
                    prerequisites=canonical_graph["prerequisites"],
                    unlocks=canonical_graph["unlocks"],
                    source_verified=bool(source),
                    chroma_chunks=int(chroma["chunk_count"]),
                    chroma_has_pages=bool(chroma["chunks_with_page_metadata"]),
                )
                rows.append({
                    "concept_name": concept_name,
                    **verdict,
                    "neo4j": {
                        "node_exists": bool(graph["node_exists"]),
                        "properties": dict(graph["concept"] or {}),
                        "topics": list(graph["topics"] or []),
                        "prerequisites": list(graph["prerequisites"] or []),
                        "unlocks": list(graph["unlocks"] or []),
                        "resources": list(graph["resources"] or []),
                    },
                    "canonical_neo4j": {
                        **canonical_graph,
                        "claim_count": int(canonical["claim_count"] or 0),
                        "misconception_count": int(canonical["misconception_count"] or 0),
                        "target_count": int(canonical["target_count"] or 0),
                    },
                    "verified_pdf_source": source,
                    "public_chroma": chroma,
                    "license_status": "needs_source_review",
                })
    finally:
        driver.close()
    return {
        "audit_version": "k1-golden-chain-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "neo4j_health": health,
        "concepts": rows,
        "summary": {
            "concept_count": len(rows),
            "verified_overall": sum(item["overall_status"] == "verified" for item in rows),
            "needs_relationship_review": sum(item["overall_status"] == "needs_relationship_review" for item in rows),
            "needs_source": sum(item["overall_status"] == "needs_source" for item in rows),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    audit = run_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
