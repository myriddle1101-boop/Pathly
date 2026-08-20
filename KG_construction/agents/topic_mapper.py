from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from infra.config import DEFAULT_EMBEDDING_MODEL
from infra.device_manager import get_embedding_batch_size, resolve_torch_device


@lru_cache(maxsize=1)
def _embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL) -> SentenceTransformer:
    return SentenceTransformer(model_name, device=resolve_torch_device())


class TopicMapper:
    _topic_embedding_cache: dict[tuple[str, tuple[str, ...]], np.ndarray] = {}

    DEFAULT_ALIASES = {
        "rag": "Retrieval-Augmented Generation (RAG)",
        "retrieval augmented generation": "Retrieval-Augmented Generation (RAG)",
        "检索增强生成": "Retrieval-Augmented Generation (RAG)",
        "transformer": "Transformers",
        "变换器模型": "Transformers",
        "ml": "Machine Learning",
        "机器学习": "Machine Learning",
        "llm": "Large Language Models",
        "大语言模型": "Large Language Models",
        "vector db": "Vector Databases",
        "向量数据库": "Vector Databases",
    }

    def __init__(
        self,
        repository,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        auto_accept_threshold: float = 0.78,
        confirmation_threshold: float = 0.60,
        aliases: dict[str, str] | None = None,
    ):
        self.repository = repository
        self.model_name = model_name
        self.auto_accept_threshold = auto_accept_threshold
        self.confirmation_threshold = confirmation_threshold
        self.aliases = {**self.DEFAULT_ALIASES, **(aliases or {})}
        self._topic_names = repository.node_names()
        self._topic_texts = repository.topic_texts()
        self._topic_embeddings: np.ndarray | None = None

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = _embedding_model(self.model_name)
        embeddings = model.encode(
            texts,
            batch_size=get_embedding_batch_size(),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.array(embeddings)

    @staticmethod
    def normalize_term(term: str) -> str:
        normalized = re.sub(r"[-_]+", " ", term.strip().casefold())
        normalized = re.sub(r"[^\w\s\u4e00-\u9fff]", "", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def expand_aliases(self, normalized: str, original: str) -> tuple[str, str | None]:
        for alias, canonical in sorted(self.aliases.items(), key=lambda item: len(item[0]), reverse=True):
            pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
            if re.search(pattern, normalized):
                if normalized == alias:
                    return canonical, canonical
                return re.sub(pattern, canonical, normalized, count=1), canonical
        return original, None

    def candidate_respects_alias(self, candidate_name: str, canonical: str) -> bool:
        anchor_tokens = {token for token in self.normalize_term(canonical).split() if len(token) >= 4}
        candidate_tokens = set(self.normalize_term(candidate_name).split())
        required = min(2, len(anchor_tokens))
        return required > 0 and len(anchor_tokens & candidate_tokens) >= required
    def map_targets(
        self,
        target_concepts: list[str],
        limit: int = 3,
        confirmed_mappings: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        matched_targets = []
        unmatched_terms = []
        confirmation_required = []
        explanations = []
        confirmations = confirmed_mappings or {}
        for concept in target_concepts:
            confirmed_name = confirmations.get(concept)
            if confirmed_name:
                confirmed = self.repository.get_topic(confirmed_name)
                if confirmed:
                    matched_targets.append({
                        "query": concept,
                        "requested_term": concept,
                        "normalized_term": confirmed_name,
                        "matched_name": confirmed["id"],
                        "score": 1.0,
                        "method": "user_confirmed",
                        "requires_confirmation": False,
                    })
                    explanations.append(f"{concept} -> {confirmed['id']} (user_confirmed, 1.0)")
                    continue

            direct = self.repository.get_topic(concept.strip())
            if direct:
                matched_targets.append({
                    "query": concept,
                    "requested_term": concept,
                    "normalized_term": direct["id"],
                    "matched_name": direct["id"],
                    "score": 1.0,
                    "method": "exact_match",
                    "requires_confirmation": False,
                })
                explanations.append(f"{concept} -> {direct['id']} (exact_match, 1.0)")
                continue

            normalized = self.normalize_term(concept)
            canonical, alias_anchor = self.expand_aliases(normalized, concept.strip())
            exact = self.repository.get_topic(canonical)
            if exact:
                method = "alias_exact" if canonical != concept.strip() else "exact_match"
                matched_targets.append({
                    "query": concept,
                    "requested_term": concept,
                    "normalized_term": canonical,
                    "matched_name": exact["id"],
                    "score": 1.0,
                    "method": method,
                    "requires_confirmation": False,
                })
                explanations.append(f"{concept} -> {exact['id']} ({method}, 1.0)")
                continue

            fuzzy_candidates = self.repository.search_topics(canonical, limit=limit)
            embedding_candidates = self._embedding_candidates(canonical, limit=limit)
            combined = self._merge_candidates(fuzzy_candidates, embedding_candidates, limit)
            if alias_anchor:
                combined = [item for item in combined if self.candidate_respects_alias(item["name"], alias_anchor)]
            if combined and combined[0]["score"] >= self.auto_accept_threshold:
                best = combined[0]
                matched_targets.append({
                    "query": concept,
                    "requested_term": concept,
                    "normalized_term": canonical,
                    "matched_name": best["name"],
                    "score": best["score"],
                    "method": best["method"],
                    "candidates": combined,
                    "requires_confirmation": False,
                })
                explanations.append(f"{concept} -> {best['name']} ({best['method']}, {best['score']})")
            elif combined and combined[0]["score"] >= self.confirmation_threshold:
                confirmation_required.append({
                    "query": concept,
                    "requested_term": concept,
                    "normalized_term": canonical,
                    "candidates": combined,
                    "best_score": combined[0]["score"],
                    "requires_confirmation": True,
                })
                explanations.append(
                    f"{concept} -> confirmation_required ({combined[0]['name']}, {combined[0]['score']})"
                )
            else:
                unmatched_terms.append(concept)
                best = combined[0] if combined else None
                explanations.append(
                    f"{concept} -> unmatched"
                    + (f" (best={best['name']}, score={best['score']})" if best else "")
                )

        return {
            "matched_targets": matched_targets,
            "unmatched_terms": unmatched_terms,
            "confirmation_required": confirmation_required,
            "mapping_explanations": explanations,
        }

    def _embedding_candidates(self, concept: str, limit: int) -> list[dict[str, Any]]:
        if self._topic_embeddings is None:
            cache_key = (self.model_name, tuple(self._topic_texts))
            cached = self._topic_embedding_cache.get(cache_key)
            if cached is None:
                cached = self._embed(self._topic_texts)
                self._topic_embedding_cache[cache_key] = cached
            self._topic_embeddings = cached
        query_embedding = self._embed([concept])[0]
        scores = np.matmul(self._topic_embeddings, query_embedding)
        ranked_indices = np.argsort(scores)[::-1][:limit]
        candidates = []
        for index in ranked_indices:
            score = float(scores[index])
            if score < 0.35:
                continue
            candidates.append({
                "name": self._topic_names[index],
                "score": round(score, 4),
                "method": "embedding_similarity",
            })
        return candidates

    def _merge_candidates(self, fuzzy_candidates, embedding_candidates, limit: int) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for candidate in fuzzy_candidates:
            merged[candidate.name] = {
                "name": candidate.name,
                "score": candidate.score,
                "method": candidate.reason,
            }
        for candidate in embedding_candidates:
            existing = merged.get(candidate["name"])
            if existing is None or candidate["score"] > existing["score"]:
                merged[candidate["name"]] = candidate
        ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
        return ranked[:limit]