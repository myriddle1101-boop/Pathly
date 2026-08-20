"""Approved goal-scoped chains for the New Learner experience."""
from __future__ import annotations
import re
from typing import Any

GOAL_CHAIN_CATALOG_VERSION = "full-experience-goal-catalog-v1"

GOAL_CHAINS: dict[str, dict[str, Any]] = {
    "word_embeddings": {"goal_keywords": ("word embedding", "semantic similarity"), "canonical_path": ["experience:text-representation", "experience:word-embeddings", "experience:cosine-similarity", "experience:semantic-similarity"], "display_names": ["Text Representation", "Word Embeddings", "Cosine Similarity", "Semantic Similarity"], "concept_pages": [8, 10, 17, 41], "asset_scope": "goal:word_embeddings", "source_id": "source:word-embeddings:cs224n-2026-wordvecs", "source_version": "word-embeddings-source-v1"},
    "self_attention": {"goal_keywords": ("self-attention", "self attention", "transformer", "model context"), "canonical_path": ["experience:token-representations", "experience:query-key-value", "experience:self-attention", "experience:contextual-representations"], "display_names": ["Token Representations", "Queries, Keys, and Values", "Self-Attention", "Contextual Representations"], "concept_pages": [40, 42, 42, 56], "tiered_concept_pages": {"foundation": [40, 42, 42, 57], "advanced": [3, 4, 4, 5]}, "asset_scope": "goal:self_attention", "source_id": "source:self-attention:cs224n-2026-transformers", "tiered_source_ids": {"foundation": "source:self-attention:gold-foundation-v1", "advanced": "source:self-attention:gold-advanced-v1", "shared": "source:self-attention:gold-foundation-v1"}, "source_version": "self-attention-gold-v1"},
    "rag": {"goal_keywords": ("retrieval-augmented generation", "rag", "retrieved evidence"), "canonical_path": ["experience:document-collection", "experience:retrieval", "experience:retrieved-evidence", "experience:retrieval-augmented-generation"], "display_names": ["Document Collection and Chunks", "Retrieval", "Retrieved Evidence", "Retrieval-Augmented Generation"], "concept_pages": [13, 15, 17, 21], "asset_scope": "goal:rag", "source_id": "source:rag:cs224n-2026-rag-agents", "source_version": "rag-source-v1"},
}

def resolve_goal_chain(goal: str) -> tuple[str, dict[str, Any]] | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(goal).lower()).strip()
    # Accept both the full natural-language goal and the short labels shown
    # on verified goal cards (for example ``rag``).  The previous resolver
    # only checked the first, long-form keyword, so a valid alias fell through
    # to a one-node plan and later failed source linking with no_reliable_source.
    matches = []
    for goal_id, spec in GOAL_CHAINS.items():
        if any(
            keyword in normalized or keyword.replace("-", " ") in normalized
            for keyword in spec["goal_keywords"]
        ):
            matches.append((goal_id, spec))
    return matches[0] if len(matches) == 1 else None
