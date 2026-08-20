from __future__ import annotations

from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from infra.config import CHROMA_PATH, DEFAULT_EMBEDDING_MODEL
from infra.device_manager import get_embedding_batch_size, load_with_device_fallback


class RAGRepository:
    def __init__(
        self,
        collection_name: str = "kg_chunks",
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        force_device: str | None = None,
    ):
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.model_name = model_name
        self.force_device = force_device
        self.last_device_info: dict[str, Any] = {}

    def _get_embedding_model(self) -> tuple[SentenceTransformer, dict[str, Any]]:
        def _loader(device: str) -> SentenceTransformer:
            return SentenceTransformer(self.model_name, device=device)

        model, runtime_info = load_with_device_fallback(
            _loader,
            component="rag.embedding",
            force_device=self.force_device,
        )
        self.last_device_info = runtime_info
        return model, runtime_info

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model, runtime_info = self._get_embedding_model()
        embeddings = model.encode(
            texts,
            batch_size=get_embedding_batch_size(runtime_info["selected_device"]),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        ids = [str(row["id"]) for row in rows]
        documents = [row["text"] for row in rows]
        metadatas = []
        for row in rows:
            metadatas.append(
                {
                    "doc_name": str(row.get("doc_name", "")),
                    "chunk_id": int(row.get("chunk_id", 0)),
                    "doc_type": str(row.get("doc_type", "")),
                    "resource_id": str(row.get("resource_id", "")),
                    "resource_filename": str(row.get("resource_filename", "")),
                    "concept_id": str(row.get("concept_id", "")),
                    "concept_name": str(row.get("concept_name", "")),
                    "topic_id": str(row.get("topic_id", "")),
                    "topic_name": str(row.get("topic_name", "")),
                    "word_count": int(row.get("word_count", 0)),
                    # Page-level provenance is optional for historical chunks
                    # and required for newly curated full-experience sources.
                    "document_id": str(row.get("document_id", "")),
                    "page_number": int(row.get("page_number", 0)),
                    "content_role": str(row.get("content_role", "")),
                    "source_version": str(row.get("source_version", "")),
                    "review_status": str(row.get("review_status", "")),
                    "source_id": str(row.get("source_id", "")),
                    "goal_id": str(row.get("goal_id", "")),
                    "learner_tier": str(row.get("learner_tier", "shared")),
                }
            )

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=self._embed(documents),
        )
        return len(rows)

    def query_chunks(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = self.collection.query(
            query_embeddings=self._embed([query]),
            n_results=top_k,
            where=filters or None,
        )

        rows: list[dict[str, Any]] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for doc_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            rows.append(
                {
                    "id": doc_id,
                    "text": document,
                    "metadata": metadata,
                    "distance": distance,
                }
            )
        return rows

    def get_chunks_by_topic(self, topic_name: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self.query_chunks(query=topic_name, top_k=top_k)

    def get_chunks_by_resource_and_topic(
        self,
        resource_id: str,
        topic_name: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not resource_id:
            return []
        return self.query_chunks(
            query=topic_name,
            top_k=top_k,
            filters={"resource_id": resource_id},
        )
