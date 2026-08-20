"""Owner-scoped private PDF source links for Source-Grounded Lecture v4."""
from __future__ import annotations

import re
from typing import Any


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in _normal(value).split() if len(token) > 2}


def _continuous_pages(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages: dict[int, list[str]] = {}
    for chunk in chunks:
        start = int(chunk.get("page_start") or 0)
        end = int(chunk.get("page_end") or start or 0)
        if start <= 0:
            continue
        for page in range(start, min(end, start + 12) + 1):
            pages.setdefault(page, []).append(str(chunk.get("chunk_id") or ""))
    ordered = [
        {"page_number": page, "role": "continuation", "chunk_ids": list(dict.fromkeys(filter(None, ids)))}
        for page, ids in sorted(pages.items())
    ]
    runs: list[list[dict[str, Any]]] = []
    for page in ordered:
        if not runs or page["page_number"] != runs[-1][-1]["page_number"] + 1:
            runs.append([page])
        else:
            runs[-1].append(page)
    if not runs:
        return []
    best = max(runs, key=lambda run: (len(run), sum(len(item["chunk_ids"]) for item in run)))
    for index, page in enumerate(best):
        page["role"] = "introduction" if index == 0 else ("worked_example" if index == len(best) - 1 and index else "mechanism")
    return best


class PrivateSourceLinkResolver:
    """Build candidates only from accepted mappings and owner-readable documents."""

    def __init__(self, interpretations: Any, documents: Any):
        self.interpretations = interpretations
        self.documents = documents

    def resolve(
        self,
        *,
        user_id: str,
        document_ids: list[str],
        concept_id: str,
        concept_name: str,
    ) -> list[dict[str, Any]]:
        if not user_id or not document_ids:
            return []
        mappings = self.interpretations.accepted_evidence_for_documents(user_id, document_ids)
        concept_norm = _normal(concept_id)
        concept_tokens = _tokens(concept_name) | _tokens(concept_id)
        candidates: list[dict[str, Any]] = []
        for mapping in mappings:
            mapped_ids = {_normal(mapping.get("canonical_concept_id")), _normal(mapping.get("private_concept_id"))}
            term_tokens = _tokens(mapping.get("requested_term"))
            direct = bool(concept_norm and concept_norm in mapped_ids)
            overlap = len(concept_tokens & term_tokens) / max(1, len(concept_tokens))
            if not direct and overlap < 0.5:
                continue
            document_id = str(mapping.get("document_id") or "")
            document = self.documents.get_document(user_id, document_id)
            if not document or document.get("parse_status") != "ready":
                continue
            all_chunks = self.documents.get_chunks(user_id, document_id)
            mapped_chunk_ids = {str(value) for value in mapping.get("chunk_ids") or []}
            chunks = [chunk for chunk in all_chunks if not mapped_chunk_ids or str(chunk.get("chunk_id")) in mapped_chunk_ids]
            pages = _continuous_pages(chunks)
            if not pages:
                continue
            confidence = float(mapping.get("mapping_confidence") or 0)
            relevance = max(confidence, 0.88 if direct else 0.65 + 0.25 * overlap)
            coverage = min(1.0, 0.46 + 0.14 * min(len(pages), 3) + 0.06 * min(len(chunks), 2))
            if relevance < 0.75 or coverage < 0.60:
                continue
            page_label = f"page {pages[0]['page_number']}" if len(pages) == 1 else f"pages {pages[0]['page_number']}-{pages[-1]['page_number']}"
            candidates.append({
                "document_id": document_id,
                "document_title": document.get("original_filename") or document.get("filename") or "Private PDF",
                "resource_id": f"private-document:{document_id}",
                "source_scope": "private",
                "page_sequence": pages,
                "chunk_ids": list(dict.fromkeys(str(chunk.get("chunk_id")) for chunk in chunks if chunk.get("chunk_id"))),
                "relevance_score": relevance,
                "coverage_score": coverage,
                "match_method": "s3_private_canonical_mapping",
                "match_reason": f"Your confirmed document mapping connects {concept_name} to {page_label} in this private PDF.",
                "review_status": "usable",
                "source_readiness": "private_chroma",
                "canonical_concept_id": mapping.get("canonical_concept_id"),
            })
        return sorted(candidates, key=lambda item: (item["relevance_score"], item["coverage_score"], len(item["page_sequence"])), reverse=True)
