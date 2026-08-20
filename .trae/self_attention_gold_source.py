"""Curate and publish the Self-Attention gold-source pilot.

This is intentionally scoped to one approved goal. It does not enter the 8501
candidate-review queue; it creates an auditable, versioned source batch for the
normal V4 source resolver, Chroma retrieval, Neo4j resource links, and tiered
teaching assets.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pdfplumber

PROJECT = Path(__file__).resolve().parent
KG_CONSTRUCTION = PROJECT.parent / "KG_construction"
sys.path.insert(0, str(KG_CONSTRUCTION))

from experience_source_store import ExperienceSourceStore
from teaching_asset_store import TeachingAssetStore
from infra.rag_repository import RAGRepository


GOLD_ROOT = PROJECT.parent.parent / "gold source" / "self_attention"
SOURCE_DB = PROJECT / "pathly_experience_sources.db"
ASSET_DB = PROJECT / "pathly_teaching_assets.db"
GOAL_ID = "self_attention"
VERSION = "self-attention-gold-v1"

SOURCES = {
    "foundation": {
        "source_id": "source:self-attention:gold-foundation-v1",
        "path": GOLD_ROOT / "foundational" / "stanford-cs224n-lecture05-transformers.pdf",
        "url": "https://web.stanford.edu/class/cs224n/slides_w26/cs224n-2026-lecture05-transformers.pdf",
        "title": "Stanford CS224N Lecture 5: Attention and Transformers",
        "license_status": "public_course_lecture",
        "pages": {"experience:token-representations": 40, "experience:query-key-value": 42, "experience:self-attention": 42, "experience:contextual-representations": 57},
    },
    "advanced": {
        "source_id": "source:self-attention:gold-advanced-v1",
        "path": GOLD_ROOT / "advanced" / "vaswani-attention-is-all-you-need.pdf",
        "url": "https://arxiv.org/pdf/1706.03762",
        "title": "Attention Is All You Need",
        "license_status": "arxiv_open_access_with_attribution",
        "pages": {"experience:token-representations": 3, "experience:query-key-value": 4, "experience:self-attention": 4, "experience:contextual-representations": 5},
    },
}

PATH = [
    ("experience:token-representations", "Token Representations", "representation"),
    ("experience:query-key-value", "Queries, Keys, and Values", "qkv_mechanism"),
    ("experience:self-attention", "Self-Attention", "attention_mechanism"),
    ("experience:contextual-representations", "Contextual Representations", "contextual_output"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pages(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            rows.append({
                "page_number": page_number,
                "content_role": "source_page",
                "text": text,
                "chunk_id": f"self-attention-{path.stem}-{page_number}",
            })
    if not rows:
        raise ValueError(f"No extractable pages: {path}")
    return rows


def _asset(*, tier: str, concept_id: str, name: str, asset_type: str, pages: list[int], text: str, document_id: str, chunk_prefix: str) -> dict[str, Any]:
    return {
        "asset_id": f"gold:self-attention:{tier}:{concept_id.split(':')[-1]}:{asset_type}",
        "canonical_concept_id": concept_id,
        "asset_type": asset_type,
        "learner_tier": tier,
        "content": {"title": name, "instruction": text, "source_role": "curated_gold_source"},
        "assessment_targets": [f"assessment:self-attention:{concept_id.split(':')[-1]}:mechanism"],
        "misconception_ids": [f"misconception:self-attention:{concept_id.split(':')[-1]}"],
        "knowledge_version": VERSION,
        "review_status": "approved",
        "evidence_refs": [{"document_id": document_id, "page_number": p, "chunk_id": f"{chunk_prefix}-{p}"} for p in pages],
    }


def publish() -> dict[str, Any]:
    source_store = ExperienceSourceStore(SOURCE_DB)
    asset_store = TeachingAssetStore(ASSET_DB)
    manifest: dict[str, Any] = {"manifest_version": VERSION, "goal_id": GOAL_ID, "sources": [], "assets": [], "path": [cid for cid, _, _ in PATH]}
    scoped_asset_ids: list[str] = []
    rag_rows: list[dict[str, Any]] = []

    for tier, spec in SOURCES.items():
        path = spec["path"]
        if not path.exists():
            raise FileNotFoundError(path)
        pages = _pages(path)
        digest = _sha256(path)
        document_id = f"public:{digest}"
        source = {
            "source_id": spec["source_id"], "goal_id": GOAL_ID,
            "canonical_concept_id": "experience:self-attention",
            "resource_id": digest, "document_id": document_id,
            "document_title": spec["title"], "source_url": spec["url"],
            "license_status": spec["license_status"], "learner_tier": tier,
            "review_status": "approved", "source_version": VERSION,
        }
        source_store.upsert(source, pages)
        rag_rows.extend({
            "id": f"gold-self-attention-{tier}-{row['chunk_id']}",
            "doc_name": path.name, "chunk_id": row["page_number"], "doc_type": "pdf",
            "resource_id": digest, "resource_filename": path.name,
            "concept_id": "experience:self-attention", "concept_name": "Self-Attention",
            "topic_id": GOAL_ID, "topic_name": "Self-Attention",
            "word_count": len(row["text"].split()), "text": row["text"],
            "document_id": document_id, "page_number": row["page_number"],
            "content_role": row["content_role"], "source_version": VERSION,
            "review_status": "verified", "source_id": spec["source_id"],
            "goal_id": GOAL_ID, "learner_tier": tier,
        } for row in pages)
        manifest["sources"].append({**source, "sha256": digest, "page_count": len(pages), "concept_pages": spec["pages"]})
        page_by_number = {row["page_number"]: row for row in pages}
        for concept_id, concept_name, role in PATH:
            page_number = spec["pages"][concept_id]
            if page_number not in page_by_number:
                raise ValueError(f"{tier}: missing mapped page {page_number} for {concept_id}")
            for asset_type, text in (("foundation_intuition" if tier == "foundation" else "advanced_derivation", f"Teach {concept_name} through the {role} evidence on page {page_number}. Preserve the canonical mechanism and make the learner trace the representation, operation, and resulting context."), ("contextual_example_variant", f"Use a concrete sequence example to apply {concept_name}; distinguish the mechanism from nearby concepts and state the relevant boundary.")):
                asset = _asset(tier=tier, concept_id=concept_id, name=concept_name, asset_type=asset_type, pages=[page_number], text=text, document_id=document_id, chunk_prefix=f"self-attention-{path.stem}")
                asset_store.upsert(asset)
                scoped_asset_ids.append(asset["asset_id"])
                manifest["assets"].append({"asset_id": asset["asset_id"], "tier": tier, "concept_id": concept_id, "evidence": asset["evidence_refs"]})

    asset_store.publish_scoped_bundle(scope_id="goal:self_attention", manifest_version=VERSION, asset_ids=scoped_asset_ids)
    rag = RAGRepository(collection_name="kg_chunks")
    rag_report = {"inserted": rag.upsert_chunks(rag_rows), "rows": len(rag_rows), "collection": "kg_chunks"}
    output = GOLD_ROOT / "gold-source-manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    graph = {
        "nodes": [{"id": cid, "name": name, "description": f"Self-Attention teaching concept: {name}", "difficulty_level": 2 if i < 2 else 3, "estimated_learning_time": 20, "target_audience": "foundation_and_advanced", "prerequisites_summary": "", "key_sub_concepts": [], "common_misconceptions": []} for i, (cid, name, _) in enumerate(PATH)],
        "edges": [{"from": PATH[i][0], "to": PATH[i + 1][0], "relation": "prerequisite", "reason": "The earlier representation/mechanism is required before the next attention operation.", "confidence": 1.0, "source": VERSION} for i in range(len(PATH) - 1)],
    }
    graph_path = GOLD_ROOT / "self_attention_gold_graph.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(output), "graph": str(graph_path), "source_count": len(manifest["sources"]), "asset_count": len(manifest["assets"]), "rag": rag_report, "version": VERSION}


if __name__ == "__main__":
    print(json.dumps(publish(), ensure_ascii=False, indent=2))
