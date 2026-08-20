"""Read-only Resource -> Chroma -> PDF page recovery for S1."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

STOPWORDS = {
    "about", "after", "also", "been", "being", "between", "from", "have",
    "into", "more", "other", "than", "that", "their", "then", "there",
    "these", "they", "this", "through", "using", "were", "what", "when",
    "where", "which", "with", "would",
}


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in _normal(value).split() if len(token) > 2 and token not in STOPWORDS}


class SourceProvenanceBackfill:
    """Recover true PDF pages without writing to KG, Chroma, or documents."""

    def __init__(
        self,
        kg_dir: str | Path,
        json_graph_path: str | Path,
        *,
        kg_factory: Callable[..., Any] | None = None,
        chroma_collection: Any | None = None,
        page_loader: Callable[[Path], list[str]] | None = None,
    ):
        self.kg_dir = Path(kg_dir)
        self.json_graph_path = Path(json_graph_path)
        self._kg_factory = kg_factory
        self._collection = chroma_collection
        self._page_loader = page_loader or self._load_pdf_pages
        self._manifest_cache: list[dict[str, Any]] | None = None

    def _factory(self):
        if self._kg_factory is not None:
            return self._kg_factory
        if str(self.kg_dir) not in sys.path:
            sys.path.insert(0, str(self.kg_dir))
        from infra.kg_repository_factory import create_kg_repository
        return create_kg_repository

    def _resource_candidates(self, concept_id: str, concept_name: str) -> tuple[list[dict[str, Any]], str]:
        factory = self._factory()
        attempts: list[tuple[str, dict[str, Any]]] = []
        if os.getenv("NEO4J_PASSWORD"):
            attempts.append(("neo4j", {"backend": "neo4j"}))
        attempts.append(("json", {"backend": "json", "graph_path": str(self.json_graph_path)}))
        for source, kwargs in attempts:
            repository = None
            try:
                repository = factory(**kwargs)
                context = repository.get_concept_context(concept_id)
                if not context.get("concept") and concept_name != concept_id:
                    context = repository.get_concept_context(concept_name)
                resources = [item for item in context.get("resources", []) if item and item.get("id")]
                if resources:
                    return resources, source
            except Exception:
                pass
            finally:
                close = getattr(repository, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
        return [], "daily"

    def _public_collection(self):
        if self._collection is not None:
            return self._collection
        import chromadb
        if str(self.kg_dir) not in sys.path:
            sys.path.insert(0, str(self.kg_dir))
        from infra.config import CHROMA_PATH
        self._collection = chromadb.PersistentClient(path=str(CHROMA_PATH)).get_collection("kg_chunks")
        return self._collection

    def _chunks(self, resource_id: str) -> list[dict[str, Any]]:
        try:
            result = self._public_collection().get(
                where={"resource_id": resource_id},
                include=["documents", "metadatas"],
            )
        except Exception:
            return []
        return [
            {"id": str(chunk_id), "text": text or "", "metadata": metadata or {}}
            for chunk_id, text, metadata in zip(
                result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or []
            )
        ]

    def _manifests(self) -> list[dict[str, Any]]:
        if self._manifest_cache is None:
            rows: list[dict[str, Any]] = []
            for path in (self.kg_dir / "web_data" / "runs").glob("*/*/manifest.json"):
                try:
                    document = (json.loads(path.read_text(encoding="utf-8")).get("document") or {})
                    pdf_path = Path(str(document.get("pdf_path") or ""))
                    if pdf_path.exists():
                        rows.append({**document, "pdf_path": str(pdf_path)})
                except Exception:
                    continue
            self._manifest_cache = rows
        return self._manifest_cache

    def _pdf_for(self, resource: dict[str, Any], chunks: list[dict[str, Any]]) -> Path | None:
        resource_id = str(resource.get("id") or "")
        sha = str(resource.get("sha256") or resource_id)
        filenames = {
            str(resource.get("filename") or "").lower(),
            *(str(row.get("metadata", {}).get("resource_filename") or "").lower() for row in chunks),
        }
        direct = Path(str(resource.get("path") or ""))
        if direct.is_file() and direct.suffix.lower() == ".pdf":
            return direct
        for manifest in self._manifests():
            manifest_sha = str(manifest.get("sha256") or "")
            if (sha and manifest_sha == sha) or (resource_id and manifest_sha == resource_id):
                return Path(manifest["pdf_path"])
            if str(manifest.get("file_name") or "").lower() in filenames:
                return Path(manifest["pdf_path"])
        return None

    @staticmethod
    def _load_pdf_pages(path: Path) -> list[str]:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return [(page.extract_text() or "") for page in pdf.pages]

    @staticmethod
    def _contiguous_best(scored: list[tuple[int, float, str]]) -> list[tuple[int, float, str]]:
        eligible = sorted((item for item in scored if item[1] >= 0.52), key=lambda item: item[0])
        runs: list[list[tuple[int, float, str]]] = []
        for item in eligible:
            if not runs or item[0] != runs[-1][-1][0] + 1:
                runs.append([item])
            else:
                runs[-1].append(item)
        if not runs:
            return []
        return max(runs, key=lambda run: (sum(item[1] for item in run), len(run)))[:4]

    def resolve(
        self,
        *,
        concept_id: str,
        concept_name: str,
        resource_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        resources, kg_source = self._resource_candidates(concept_id, concept_name)
        known = {str(item.get("id")): dict(item) for item in resources if item.get("id")}
        for resource_id in resource_ids or []:
            known.setdefault(str(resource_id), {"id": str(resource_id)})

        concept_tokens = _tokens(f"{concept_id} {concept_name}")
        if not concept_tokens:
            return []
        candidates: list[dict[str, Any]] = []
        for resource_id, resource in known.items():
            chunks = self._chunks(resource_id)
            relevant_chunks = []
            for chunk in chunks:
                overlap = len(concept_tokens & _tokens(chunk["text"])) / len(concept_tokens)
                metadata_text = f"{chunk['metadata'].get('concept_name', '')} {chunk['metadata'].get('topic_name', '')}"
                metadata_overlap = len(concept_tokens & _tokens(metadata_text)) / len(concept_tokens)
                if max(overlap, metadata_overlap) >= 0.5:
                    relevant_chunks.append(chunk)
            if not relevant_chunks:
                continue
            pdf_path = self._pdf_for(resource, relevant_chunks)
            if pdf_path is None:
                continue
            try:
                pages = self._page_loader(pdf_path)
            except Exception:
                continue
            scored_pages: list[tuple[int, float, str]] = []
            for page_number, page_text in enumerate(pages, 1):
                page_tokens = _tokens(page_text)
                concept_score = len(concept_tokens & page_tokens) / len(concept_tokens)
                best_containment, best_chunk_id = 0.0, ""
                for chunk in relevant_chunks:
                    if not page_tokens:
                        continue
                    containment = len(page_tokens & _tokens(chunk["text"])) / len(page_tokens)
                    if containment > best_containment:
                        best_containment, best_chunk_id = containment, chunk["id"]
                combined = 0.55 * concept_score + 0.45 * best_containment
                if concept_score >= 0.5 and best_containment >= 0.35:
                    combined = max(combined, 0.58)
                scored_pages.append((page_number, combined, best_chunk_id))
            run = self._contiguous_best(scored_pages)
            if not run:
                continue
            page_sequence = []
            for index, (page_number, _, chunk_id) in enumerate(run):
                role = "introduction" if index == 0 else ("worked_example" if index == len(run) - 1 else "mechanism")
                page_sequence.append({"page_number": page_number, "role": role, "chunk_ids": [chunk_id] if chunk_id else []})
            candidates.append({
                "resource_id": resource_id,
                "document_id": f"public:{resource_id}",
                "document_title": resource.get("title") or resource.get("filename") or pdf_path.name,
                "source_scope": "public",
                "page_sequence": page_sequence,
                "chunk_ids": list(dict.fromkeys(item[2] for item in run if item[2])),
                "relevance_score": max(0.78, min(0.95, max(item[1] for item in run) + 0.2)),
                "coverage_score": min(1.0, 0.62 + 0.1 * min(len(run), 3)),
                "match_method": f"{kg_source}_resource_chroma_pdf_backfill",
                "match_reason": f"The {kg_source.upper()} resource link and indexed Chroma evidence align {concept_name} with PDF pages {run[0][0]}-{run[-1][0]}.",
            })
        return sorted(candidates, key=lambda item: (item["relevance_score"], item["coverage_score"]), reverse=True)
    def page_evidence(self, link: dict[str, Any]) -> list[dict[str, Any]]:
        """Read only the PDF pages approved by the sidecar source-link index."""
        resource_id = str(link.get("resource_id") or "")
        if not resource_id:
            return []
        resources, _ = self._resource_candidates(str(link.get("concept_id") or ""), str(link.get("concept_name") or ""))
        resource = next((item for item in resources if str(item.get("id") or "") == resource_id), {"id": resource_id})
        chunks = self._chunks(resource_id)
        pdf_path = self._pdf_for(resource, chunks)
        if pdf_path is None:
            return []
        try:
            pages = self._page_loader(pdf_path)
        except Exception:
            return []
        return [
            {"page_number": number, "text": pages[number - 1]}
            for number in [int(item.get("page_number") or 0) for item in link.get("page_sequence") or []]
            if 0 < number <= len(pages)
        ]
