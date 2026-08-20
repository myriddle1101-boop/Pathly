"""Reconcile page-aware Chroma metadata for the V4 golden five.

This is intentionally scoped to the verified public resources used by the
golden path. It does not rebuild the broader KG or touch v1/v2/v3 data.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
KG_DIR = PROJECT_ROOT / "KG_construction"


def _tokens(value: str) -> set[str]:
    return {x for x in re.sub(r"[^a-z0-9]+", " ", value.lower()).split() if len(x) > 2}


def _page_for_chunk(text: str, pages: list[str]) -> tuple[int, float]:
    chunk_tokens = _tokens(text)
    if not chunk_tokens:
        return 0, 0.0
    ranked = []
    for index, page in enumerate(pages, 1):
        page_tokens = _tokens(page)
        score = len(chunk_tokens & page_tokens) / max(1, len(chunk_tokens))
        ranked.append((score, index))
    score, page = max(ranked, default=(0.0, 0))
    return page, score


def _load_env() -> None:
    sys.path.insert(0, str(KG_DIR))
    from env_loader import load_project_env
    load_project_env()


def reconcile() -> dict[str, Any]:
    _load_env()
    import chromadb
    import pdfplumber
    from golden_teaching_semantics import GOLDEN_PATH
    from verified_golden_sources import VerifiedGoldenSourceRegistry

    from infra.config import CHROMA_PATH

    registry = VerifiedGoldenSourceRegistry(KG_DIR)
    verified = {row["concept_name"]: row["source"] for row in registry.audit()}
    collection = chromadb.PersistentClient(path=str(CHROMA_PATH)).get_collection("kg_chunks")
    manifest_paths = list((KG_DIR / "web_data" / "runs").glob("*/*/manifest.json"))
    updated = 0
    resources: dict[str, dict[str, Any]] = {}
    for concept in GOLDEN_PATH:
        source = verified[concept]
        resource_id = str(source["resource_id"])
        resources.setdefault(resource_id, {"concepts": [], "source": source})["concepts"].append(concept)

    for resource_id, item in resources.items():
        chunks = collection.get(where={"resource_id": resource_id}, include=["documents", "metadatas"])
        rows = list(zip(chunks.get("ids") or [], chunks.get("documents") or [], chunks.get("metadatas") or []))
        pdf_path = None
        for manifest_path in manifest_paths:
            try:
                document = json.loads(manifest_path.read_text(encoding="utf-8")).get("document") or {}
                if str(document.get("sha256") or "") == resource_id or str(document.get("resource_id") or "") == resource_id:
                    candidate = Path(str(document.get("pdf_path") or ""))
                    if candidate.is_file():
                        pdf_path = candidate
                        break
            except Exception:
                continue
        if pdf_path is None:
            continue
        with pdfplumber.open(pdf_path) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages]
        page_sequences = {name: {int(p["page_number"]): p for p in verified[name].get("page_sequence") or []} for name in item["concepts"]}
        for chunk_id, text, metadata in rows:
            page_number, score = _page_for_chunk(text or "", pages)
            if not page_number or score < 0.08:
                continue
            roles = []
            concepts = []
            for concept, sequence in page_sequences.items():
                if page_number in sequence:
                    concepts.append(concept)
                    roles.append(str(sequence[page_number].get("role") or "supporting"))
            metadata = dict(metadata or {})
            metadata.update({
                "page_number": page_number,
                "page_start": page_number,
                "page_end": page_number,
                "content_role": ",".join(sorted(set(roles))) or "supporting",
                "canonical_concept_id": ",".join(f"golden:{concept.lower().replace(' ', '-')}" for concept in concepts),
                "source_version": "source-grounded-golden-s2-v1",
                "review_status": "verified",
                "page_match_score": round(score, 4),
            })
            collection.update(ids=[str(chunk_id)], metadatas=[metadata])
            updated += 1
    return {"updated_chunks": updated, "resources": len(resources), "golden_concepts": len(GOLDEN_PATH)}


if __name__ == "__main__":
    print(json.dumps(reconcile(), ensure_ascii=False))
