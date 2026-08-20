"""Curate page-level CS224N evidence for the Word Embeddings candidate chain."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from experience_source_store import ExperienceSourceStore


ROOT = Path(__file__).resolve().parent
KG_ROOT = ROOT.parent / "KG_construction"
PDF_PATH = KG_ROOT / "web_data" / "runs" / "cs224n-2026-lecture02-wordvecs" / "fd0b4ad8af88" / "cs224n-2026-lecture02-wordvecs.pdf"
STORE_PATH = ROOT / "pathly_experience_sources.db"
SOURCE_ID = "source:word-embeddings:cs224n-2026-wordvecs"
RESOURCE_ID = "fd0b4ad8af88732a64ce947e044b827ef8e05c8dcb808878b4762958ac078c29"
DOCUMENT_ID = RESOURCE_ID
SOURCE_VERSION = "word-embeddings-source-v1"
PAGES = {
    8: "motivation",
    10: "definition_and_distributional_mechanism",
    17: "similarity_scoring_mechanism",
    24: "geometric_consequence",
    41: "semantic_similarity_evaluation",
}


def _extract_pages() -> list[dict[str, str | int]]:
    import pdfplumber

    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)
    rows = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page_number, role in PAGES.items():
            text = " ".join((pdf.pages[page_number - 1].extract_text() or "").split())
            if len(text.split()) < 12:
                raise ValueError(f"page {page_number} has insufficient extractable text")
            rows.append({
                "chunk_id": f"we-wordvecs-p{page_number}",
                "page_number": page_number,
                "content_role": role,
                "text": text,
            })
    return rows


def seed(*, ingest_chroma: bool = False) -> dict[str, object]:
    pages = _extract_pages()
    source = {
        "source_id": SOURCE_ID,
        "goal_id": "word_embeddings",
        "canonical_concept_id": "experience:word-embeddings",
        "resource_id": RESOURCE_ID,
        "document_id": DOCUMENT_ID,
        "document_title": "CS224N Lecture 2: Word Vectors",
        "source_url": "https://web.stanford.edu/class/cs224n/slides_w26/cs224n-2026-lecture02-wordvecs.pdf",
        "license_status": "public_course_material; redistribution_terms_not_asserted",
        "review_status": "approved",
        "source_version": SOURCE_VERSION,
    }
    stored = ExperienceSourceStore(STORE_PATH).upsert(source, pages)
    inserted = 0
    if ingest_chroma:
        sys.path.insert(0, str(KG_ROOT))
        from infra.rag_repository import RAGRepository

        rows = [{
            "id": item["chunk_id"], "text": item["text"], "doc_name": source["document_title"],
            "chunk_id": item["page_number"], "doc_type": "slides", "resource_id": RESOURCE_ID,
            "resource_filename": PDF_PATH.name, "document_id": DOCUMENT_ID, "page_number": item["page_number"],
            "content_role": item["content_role"], "source_version": SOURCE_VERSION, "review_status": "approved",
            "concept_id": source["canonical_concept_id"], "concept_name": "Word Embeddings", "topic_id": "Word Vectors",
            "topic_name": "Word Vectors", "word_count": len(str(item["text"]).split()),
        } for item in pages]
        repository = RAGRepository(collection_name="kg_chunks", force_device="cpu")
        inserted = repository.upsert_chunks(rows)
    return {"source_id": stored["source_id"], "pages": [item["page_number"] for item in stored["pages"]], "chroma_inserted": inserted, "source_version": SOURCE_VERSION}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest-chroma", action="store_true")
    args = parser.parse_args()
    print(json.dumps(seed(ingest_chroma=args.ingest_chroma), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
