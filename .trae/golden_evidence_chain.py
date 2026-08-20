"""KQ2 public evidence chain for the five approved V4 teaching profiles."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from golden_teaching_semantics import KQ1_SEMANTICS_VERSION, teaching_profile
from verified_golden_sources import GOLDEN_PATH, VerifiedGoldenSourceRegistry


KQ2_EVIDENCE_VERSION = "kq2-golden-public-evidence-v1"
REQUIRED_CHROMA_METADATA = (
    "canonical_concept_id", "resource_id", "document_id", "page_numbers",
    "chunk_id", "content_role", "source_version", "review_status",
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", str(text or "").lower()))


def _match_pages_to_chunks(pages: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[int, list[str]]:
    """Map each verified PDF page to its most text-overlapping indexed chunk.

    Source PDFs contain slides and chunks may span several pages, so a chunk is
    allowed to support more than one page. The mapping is recorded explicitly
    rather than pretending every chunk is a page.
    """
    result: dict[int, list[str]] = {}
    for page in pages:
        page_tokens = _tokens(page.get("text") or "")
        scored = []
        for chunk in chunks:
            chunk_tokens = _tokens(chunk.get("text") or "")
            score = len(page_tokens & chunk_tokens) / max(1, len(page_tokens | chunk_tokens))
            scored.append((score, str(chunk["id"])))
        best = max(scored, default=(0.0, ""))
        if not best[1]:
            raise ValueError(f"No public Chroma chunk is available for verified page {page.get('page_number')}")
        result[int(page["page_number"])] = [best[1]]
    return result


def _load_chunks(kg_dir: Path, resource_id: str) -> list[dict[str, Any]]:
    import chromadb
    collection = chromadb.PersistentClient(path=str(kg_dir / "data" / "chroma")).get_collection("kg_chunks")
    result = collection.get(where={"resource_id": resource_id}, include=["documents", "metadatas"])
    return [
        {"id": str(chunk_id), "text": text or "", "metadata": dict(metadata or {})}
        for chunk_id, text, metadata in zip(result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or [])
    ]


def build_evidence_manifest(kg_dir: str | Path) -> dict[str, Any]:
    root = Path(kg_dir)
    registry = VerifiedGoldenSourceRegistry(root)
    records = []
    for concept_name in GOLDEN_PATH:
        profile = teaching_profile(concept_name)
        source = registry.resolve(concept_id=concept_name, concept_name=concept_name)
        if not source:
            raise RuntimeError(f"Unverified source for {concept_name}")
        source["concept_name"] = concept_name
        pages = registry.page_evidence(source)
        by_page = _match_pages_to_chunks(pages, _load_chunks(root, str(source["resource_id"])))
        claims = []
        for claim in profile["claims"]:
            refs = []
            for number in claim["source_pages"]:
                refs.append({"page_number": number, "chunk_ids": by_page[number]})
            claims.append({"kind": claim["kind"], "text": claim["text"], "evidence": refs})
        records.append({
            "concept_name": concept_name,
            "canonical_concept_id": profile["canonical_id"],
            "resource_id": source["resource_id"],
            "document_id": source["document_id"],
            "document_title": source["document_title"],
            "pages": [{**page, "chunk_ids": by_page[int(page["page_number"])]} for page in pages],
            "claims": claims,
        })
    return {"evidence_version": KQ2_EVIDENCE_VERSION, "semantics_version": KQ1_SEMANTICS_VERSION, "records": records}


def _settings() -> tuple[str, str, str, str]:
    return (os.getenv("NEO4J_URI", "bolt://localhost:7687"), os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""), os.getenv("NEO4J_DATABASE", "neo4j"))


def publish_evidence_chain(*, kg_dir: str | Path, dry_run: bool = False) -> dict[str, Any]:
    """Write only KQ2 labels/relationships and enrich public Chroma metadata."""
    manifest = build_evidence_manifest(kg_dir)
    if dry_run:
        return {"dry_run": True, "concepts": len(manifest["records"]), "claim_evidence_links": sum(len(c["evidence"]) for r in manifest["records"] for c in r["claims"])}
    root = Path(kg_dir)
    import chromadb
    collection = chromadb.PersistentClient(path=str(root / "data" / "chroma")).get_collection("kg_chunks")
    chunk_context: dict[str, dict[str, Any]] = {}
    for record in manifest["records"]:
        for page in record["pages"]:
            for chunk_id in page["chunk_ids"]:
                entry = chunk_context.setdefault(chunk_id, {"concept_ids": set(), "pages": set(), "roles": set(), "record": record})
                entry["concept_ids"].add(record["canonical_concept_id"])
                entry["pages"].add(int(page["page_number"]))
                entry["roles"].add(str(page.get("role") or "source"))
    for chunk_id, context in chunk_context.items():
        record = context["record"]
        existing = collection.get(ids=[chunk_id], include=["metadatas"]).get("metadatas") or [{}]
        metadata = dict(existing[0] or {})
        metadata.update({
            "canonical_concept_id": sorted(context["concept_ids"])[0] if len(context["concept_ids"]) == 1 else "golden:multiple",
            "canonical_concept_ids": json.dumps(sorted(context["concept_ids"])),
            "resource_id": record["resource_id"], "document_id": record["document_id"],
            "page_numbers": json.dumps(sorted(context["pages"])), "chunk_id": chunk_id,
            "content_role": ",".join(sorted(context["roles"])), "source_version": KQ2_EVIDENCE_VERSION,
            "review_status": "approved",
        })
        collection.update(ids=[chunk_id], metadatas=[metadata])
    from neo4j import GraphDatabase
    uri, user, password, database = _settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    stamp = datetime.now(timezone.utc).isoformat()
    links = 0
    try:
        with driver.session(database=database) as session:
            for record in manifest["records"]:
                for page in record["pages"]:
                    page_id = f"{record['document_id']}:page:{page['page_number']}"
                    session.run("""
                        MERGE (r:Resource {id:$resource_id})
                        SET r.title=$title, r.source_scope='public'
                        MERGE (d:Document {id:$document_id})
                        SET d.title=$title, d.resource_id=$resource_id, d.source_scope='public'
                        MERGE (r)-[:HAS_DOCUMENT {evidence_version:$version}]->(d)
                        MERGE (p:Page {id:$page_id})
                        SET p.document_id=$document_id, p.page_number=$page_number, p.review_status='approved'
                        MERGE (d)-[:HAS_PAGE {evidence_version:$version}]->(p)
                    """, resource_id=record["resource_id"], document_id=record["document_id"], title=record["document_title"], page_id=page_id, page_number=page["page_number"], version=KQ2_EVIDENCE_VERSION)
                    for chunk_id in page["chunk_ids"]:
                        session.run("""
                            MATCH (p:Page {id:$page_id})
                            MERGE (c:ChunkRef {id:$chunk_id})
                            SET c.chunk_id=$chunk_id, c.resource_id=$resource_id, c.document_id=$document_id,
                                c.source_version=$version, c.review_status='approved', c.updated_at=$stamp
                            MERGE (p)-[:HAS_CHUNK_REF {evidence_version:$version}]->(c)
                        """, page_id=page_id, chunk_id=chunk_id, resource_id=record["resource_id"], document_id=record["document_id"], version=KQ2_EVIDENCE_VERSION, stamp=stamp)
                for claim in record["claims"]:
                    claim_id = f"{record['canonical_concept_id']}:claim:{claim['kind']}"
                    for evidence in claim["evidence"]:
                        page_id = f"{record['document_id']}:page:{evidence['page_number']}"
                        session.run("""
                            MATCH (claim:TeachingClaim {id:$claim_id}), (p:Page {id:$page_id})
                            MERGE (claim)-[:SUPPORTED_BY {evidence_version:$version}]->(p)
                        """, claim_id=claim_id, page_id=page_id, version=KQ2_EVIDENCE_VERSION)
                        links += 1
    finally:
        driver.close()
    return {"dry_run": False, "concepts": len(manifest["records"]), "claim_evidence_links": links, "chunk_refs": len(chunk_context), "evidence_version": KQ2_EVIDENCE_VERSION}


def audit_evidence_chain() -> dict[str, Any]:
    """Read back 5/5 concept coverage and page/chunk evidence from Neo4j."""
    from neo4j import GraphDatabase
    uri, user, password, database = _settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            rows = []
            for name in GOLDEN_PATH:
                profile = teaching_profile(name)
                row = session.run("""
                    MATCH (c:CanonicalConcept {id:$id})-[:HAS_TEACHING_CLAIM]->(claim:TeachingClaim)
                    OPTIONAL MATCH (claim)-[:SUPPORTED_BY]->(p:Page)-[:HAS_CHUNK_REF]->(chunk:ChunkRef)
                    RETURN count(DISTINCT claim) AS claims, count(DISTINCT p) AS pages, count(DISTINCT chunk) AS chunks
                """, id=profile["canonical_id"]).single()
                rows.append({"concept_name": name, "claims": int(row["claims"]), "pages": int(row["pages"]), "chunks": int(row["chunks"]), "passed": int(row["claims"]) >= 5 and int(row["pages"]) > 0 and int(row["chunks"]) > 0})
        return {"evidence_version": KQ2_EVIDENCE_VERSION, "passed": all(row["passed"] for row in rows), "concepts": rows}
    finally:
        driver.close()
