from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from agents.topic_mapper import TopicMapper


class FakeRepository:
    def __init__(self, exact=None, candidates=None):
        self.exact = exact or {}
        self.candidates = candidates or []

    def node_names(self):
        return ["Latent Dynamics Models", "Retrieval Models"]

    def topic_texts(self):
        return ["latent system dynamics", "information retrieval"]

    def get_topic(self, name):
        return {"id": name} if name in self.exact else None

    def search_topics(self, query, limit=3):
        return self.candidates[:limit]


def mapper(repo):
    with patch.object(TopicMapper, "_embed", return_value=np.array([[1.0, 0.0], [0.0, 1.0]])):
        return TopicMapper(repo)


def test_rag_alias_resolves_to_canonical_exact_topic():
    canonical = "Retrieval-Augmented Generation (RAG)"
    result = mapper(FakeRepository(exact={canonical})).map_targets(["RAG"])
    match = result["matched_targets"][0]
    assert match["matched_name"] == canonical
    assert match["normalized_term"] == canonical
    assert match["method"] == "alias_exact"


def test_canonical_rag_exact_match_does_not_load_embeddings():
    canonical = "Retrieval-Augmented Generation (RAG)"
    instance = mapper(FakeRepository(exact={canonical}))
    with patch.object(instance, "_embed", side_effect=AssertionError("embedding should not run")):
        result = instance.map_targets([canonical])
    assert result["matched_targets"][0]["matched_name"] == canonical
    assert result["matched_targets"][0]["method"] == "exact_match"

def test_unrelated_rag_candidate_is_rejected_not_forced():
    repo = FakeRepository(candidates=[SimpleNamespace(name="Latent Dynamics Models", score=0.55, reason="fuzzy_match")])
    instance = mapper(repo)
    with patch.object(instance, "_embedding_candidates", return_value=[]):
        result = instance.map_targets(["RAG"])
    assert result["matched_targets"] == []
    assert result["unmatched_terms"] == ["RAG"]
    assert result["mapping_explanations"][0] == "RAG -> unmatched"


def test_medium_confidence_requires_confirmation():
    repo = FakeRepository(candidates=[SimpleNamespace(name="Retrieval Models", score=0.70, reason="fuzzy_match")])
    instance = mapper(repo)
    with patch.object(instance, "_embedding_candidates", return_value=[]):
        result = instance.map_targets(["unknown retrieval concept"])
    assert result["matched_targets"] == []
    assert result["confirmation_required"][0]["best_score"] == 0.70


def test_high_confidence_candidate_is_accepted():
    repo = FakeRepository(candidates=[SimpleNamespace(name="Retrieval Models", score=0.82, reason="fuzzy_match")])
    instance = mapper(repo)
    with patch.object(instance, "_embedding_candidates", return_value=[]):
        result = instance.map_targets(["retrieval model"])
    assert result["matched_targets"][0]["matched_name"] == "Retrieval Models"
    assert result["confirmation_required"] == []

def test_user_confirmed_mapping_is_accepted_and_auditable():
    repo = FakeRepository(exact={"Retrieval Models"})
    result = mapper(repo).map_targets(
        ["unknown retrieval concept"],
        confirmed_mappings={"unknown retrieval concept": "Retrieval Models"},
    )
    match = result["matched_targets"][0]
    assert match["matched_name"] == "Retrieval Models"
    assert match["method"] == "user_confirmed"
    assert result["confirmation_required"] == []


def test_rag_compound_term_rejects_high_scoring_generic_application():
    repo = FakeRepository(candidates=[SimpleNamespace(name="AI Applications", score=0.91, reason="fuzzy_match")])
    instance = mapper(repo)
    with patch.object(instance, "_embedding_candidates", return_value=[]):
        result = instance.map_targets(["RAG applications"])
    assert result["matched_targets"] == []
    assert result["unmatched_terms"] == ["RAG applications"]


def test_rag_compound_term_keeps_candidates_with_canonical_anchor():
    repo = FakeRepository(candidates=[SimpleNamespace(name="Retrieval Augmented Generation Systems", score=0.91, reason="fuzzy_match")])
    instance = mapper(repo)
    with patch.object(instance, "_embedding_candidates", return_value=[]):
        result = instance.map_targets(["RAG applications"])
    assert result["matched_targets"][0]["matched_name"] == "Retrieval Augmented Generation Systems"