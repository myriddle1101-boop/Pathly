"""Read-only evidence audit for N2's three new candidate goal chains."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
KG_ROOT = ROOT.parent / "KG_construction"
RUNS_ROOT = KG_ROOT / "web_data" / "runs"
DEFAULT_OUTPUT = ROOT / "artifacts" / "n2_multigoal_source_audit.json"
AUDIT_VERSION = "n2-multigoal-source-audit-v1"

CANDIDATES = {
    "word_embeddings": {
        "target_concept": "Word Vectors",
        "candidate_paths": [
            ("02-understanding-embeddings", "2a611584541b"),
            ("cs224n-2026-lecture02-wordvecs", "fd0b4ad8af88"),
        ],
    },
    "self_attention": {
        "target_concept": "Attention Mechanisms",
        "candidate_paths": [("cs224n-2026-lecture05-transformers", "0e9017f9dbd8")],
    },
    "rag": {
        "target_concept": "Retrieval-Augmented Generation (RAG)",
        "candidate_paths": [
            ("cs224n-2026-lecture10-rag-agents", "2e97edb678d2"),
            ("01-introduction-to-rag", "7cfd7fd31611"),
            ("05-building-simple-rag", "35ec62f5ee2b"),
            ("06-advanced-rag-techniques", "a65350c7ccf6"),
        ],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_source(run_name: str, digest: str) -> dict[str, Any]:
    directory = RUNS_ROOT / run_name / digest
    manifest_path = directory / "manifest.json"
    chunks_path = directory / "stage1_chunks.json"
    if not manifest_path.exists() or not chunks_path.exists():
        return {"run": run_name, "digest": digest, "available": False, "reason": "missing_manifest_or_stage1_chunks"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    page_fields = {"page", "page_number", "page_start", "page_end"}
    chunk_ids = [str(item.get("chunk_id")) for item in chunks if item.get("chunk_id") is not None]
    chunks_with_pages = sum(any(item.get(field) not in (None, "") for field in page_fields) for item in chunks)
    document = dict(manifest.get("document") or {})
    stages = dict(manifest.get("stages") or {})
    return {
        "run": run_name,
        "digest": digest,
        "available": bool(document.get("pdf_path")) and bool(chunks),
        "pipeline_status": manifest.get("status"),
        "resource_id": document.get("sha256"),
        "document_name": document.get("file_name"),
        "pdf_path_exists": Path(str(document.get("pdf_path") or "")).exists(),
        "chunk_count": len(chunks),
        "chunk_id_examples": chunk_ids[:3],
        "chunks_with_page_metadata": chunks_with_pages,
        "page_level_grounding_ready": chunks_with_pages == len(chunks) and bool(chunks),
        "stage1_output_verified": (stages.get("stage1") or {}).get("status") == "success",
        "license_or_review_status": "not_recorded",
        "reason": (
            "Candidate source is present, but its stage-1 chunks lack page metadata and no review/license approval is recorded."
            if chunks_with_pages != len(chunks) else "Candidate source has page metadata; separate review is still required."
        ),
    }


def build_audit() -> dict[str, Any]:
    goals = []
    for goal_id, spec in CANDIDATES.items():
        sources = [audit_source(name, digest) for name, digest in spec["candidate_paths"]]
        usable = [item for item in sources if item["available"] and item["page_level_grounding_ready"] and item["license_or_review_status"] == "approved"]
        goals.append({
            "goal_id": goal_id,
            "target_concept_candidate": spec["target_concept"],
            "candidate_sources": sources,
            "admission_readiness": "ready_for_curation" if any(item["available"] for item in sources) else "missing_source",
            "eligible_source_coverage": bool(usable),
            "blocking_gaps": [
                "page_chunk_backfill_required",
                "human_source_review_required",
                "canonical_prerequisite_chain_required",
                "teaching_assets_required",
            ],
        })
    return {
        "audit_version": AUDIT_VERSION,
        "generated_at": _now(),
        "read_only": True,
        "goals": goals,
        "summary": {
            "candidate_goals": len(goals),
            "candidate_sources": sum(len(item["candidate_sources"]) for item in goals),
            "page_grounding_ready_sources": sum(
                source["page_level_grounding_ready"]
                for item in goals for source in item["candidate_sources"]
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
