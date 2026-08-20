"""Curate page-level CS224N evidence for the Self-Attention candidate chain."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experience_source_store import ExperienceSourceStore


ROOT = Path(__file__).resolve().parent
KG_ROOT = ROOT.parent / "KG_construction"
PDF_PATH = KG_ROOT / "web_data" / "runs" / "cs224n-2026-lecture05-transformers" / "0e9017f9dbd8" / "cs224n-2026-lecture05-transformers.pdf"
STORE_PATH = ROOT / "pathly_experience_sources.db"
SOURCE_ID = "source:self-attention:cs224n-2026-transformers"
RESOURCE_ID = "0e9017f9dbd8d3f995f32abac5951abd76d09cd78ed8fc5de20ebac32cbbe9e4"
DOCUMENT_ID = RESOURCE_ID
SOURCE_VERSION = "self-attention-source-v1"
PAGES = {40: "self_attention_overview", 42: "query_key_value_mechanism", 44: "position_boundary", 56: "matrix_computation"}


def _extract_pages():
    import pdfplumber
    with pdfplumber.open(PDF_PATH) as pdf:
        return [{"chunk_id": f"sa-transformers-p{page}", "page_number": page, "content_role": role, "text": " ".join((pdf.pages[page - 1].extract_text() or "").split())} for page, role in PAGES.items()]


def seed(*, ingest_chroma: bool = False):
    pages = _extract_pages()
    if any(len(item["text"].split()) < 12 for item in pages):
        raise ValueError("insufficient extracted text in selected self-attention evidence page")
    source = {"source_id": SOURCE_ID, "goal_id": "self_attention", "canonical_concept_id": "experience:self-attention", "resource_id": RESOURCE_ID, "document_id": DOCUMENT_ID, "document_title": "CS224N Lecture 5: Attention and Transformers", "source_url": "https://web.stanford.edu/class/cs224n/slides_w26/cs224n-2026-lecture05-transformers.pdf", "license_status": "public_course_material; redistribution_terms_not_asserted", "review_status": "approved", "source_version": SOURCE_VERSION}
    stored = ExperienceSourceStore(STORE_PATH).upsert(source, pages)
    inserted = 0
    if ingest_chroma:
        sys.path.insert(0, str(KG_ROOT))
        from infra.rag_repository import RAGRepository
        rows = [{"id": item["chunk_id"], "text": item["text"], "doc_name": source["document_title"], "chunk_id": item["page_number"], "doc_type": "slides", "resource_id": RESOURCE_ID, "resource_filename": PDF_PATH.name, "document_id": DOCUMENT_ID, "page_number": item["page_number"], "content_role": item["content_role"], "source_version": SOURCE_VERSION, "review_status": "approved", "concept_id": source["canonical_concept_id"], "concept_name": "Self-Attention", "topic_id": "Attention Mechanisms", "topic_name": "Attention Mechanisms", "word_count": len(item["text"].split())} for item in pages]
        inserted = RAGRepository(collection_name="kg_chunks", force_device="cpu").upsert_chunks(rows)
    return {"source_id": stored["source_id"], "pages": [item["page_number"] for item in stored["pages"]], "chroma_inserted": inserted, "source_version": SOURCE_VERSION}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--ingest-chroma", action="store_true")
    print(json.dumps(seed(ingest_chroma=parser.parse_args().ingest_chroma), ensure_ascii=False))


if __name__ == "__main__": main()
