import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.content_context_service import ContentContextService
from infra.kg_repository import KGRepository
from infra.profile_schema import LearnerProfile


class FakeRAGRepository:
    def __init__(self, resource_chunks=None):
        self.calls = []
        self.resource_calls = []
        self.resource_chunks = resource_chunks if resource_chunks is not None else []

    def get_chunks_by_topic(self, topic_name: str, top_k: int = 5):
        self.calls.append({"topic_name": topic_name, "top_k": top_k})
        return [
            {
                "id": "chunk-1",
                "text": "Neural networks are layered models.",
                "metadata": {"doc_name": "demo", "chunk_id": 1},
                "distance": 0.1,
            }
        ]

    def get_chunks_by_resource_and_topic(self, resource_id: str, topic_name: str, top_k: int = 5):
        self.resource_calls.append({"resource_id": resource_id, "topic_name": topic_name, "top_k": top_k})
        return self.resource_chunks


def _repository() -> KGRepository:
    graph_data = {
        "nodes": [
            {"id": "Linear Algebra", "description": "Prerequisite math.", "difficulty_level": 2},
            {"id": "Neural Networks", "description": "Layered models.", "difficulty_level": 3},
            {"id": "Backpropagation", "description": "Training algorithm.", "difficulty_level": 4},
            {"id": "Resource Low", "title": "Low", "filename": "low.pdf"},
            {"id": "Resource Mid", "title": "Mid", "filename": "mid.pdf"},
        ],
        "edges": [
            {"from": "Linear Algebra", "to": "Neural Networks", "relation": "prerequisite"},
            {"from": "Neural Networks", "to": "Backpropagation", "relation": "similarity", "score": 0.7},
            {"from": "Linear Algebra", "to": "Resource Low", "relation": "has_resource"},
            {"from": "Neural Networks", "to": "Resource Mid", "relation": "has_resource"},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(graph_data, f)
        temp_path = f.name
    return KGRepository.from_json(temp_path)


def _profile(**overrides) -> LearnerProfile:
    values = {
        "user_id": "u1",
        "name": "Test",
        "academic_level": "undergraduate",
        "domain": "ml",
        "goal_text": "learn neural networks",
        "target_days": 2,
        "daily_minutes": 60,
        "prior_knowledge_level": 1,
        "math_foundation": 1,
        "programming_foundation": 1,
        "self_regulation": 3,
        "known_topics": [],
    }
    values.update(overrides)
    return LearnerProfile(**values)


class ContentContextServiceTest(unittest.TestCase):
    def test_build_context_without_rag_keeps_generation_not_ready(self):
        service = ContentContextService(kg_repository=_repository())

        context = service.build_context("Neural Networks", top_k=3)

        self.assertEqual(context["concept_id"], "Neural Networks")
        self.assertEqual(context["kg_context"]["prerequisites"], ["Linear Algebra"])
        self.assertEqual(context["rag_chunks"], [])
        self.assertEqual(context["recommended_resources"], [])
        self.assertFalse(context["generation_ready"])
        self.assertEqual(context["boundaries"]["profile_store"], "not accessed")
        self.assertEqual(context["boundaries"]["llm_generation"], "not executed")

    def test_build_context_with_rag_returns_retrieved_chunks(self):
        rag = FakeRAGRepository()
        service = ContentContextService(kg_repository=_repository(), rag_repository=rag)

        context = service.build_context("Neural Networks", top_k=2)

        self.assertTrue(context["generation_ready"])
        self.assertEqual(context["rag_chunks"][0]["id"], "chunk-1")
        self.assertEqual(rag.calls, [{"topic_name": "Neural Networks", "top_k": 2}])
        self.assertEqual(rag.resource_calls, [])

    def test_build_context_with_profile_returns_ranked_resources_and_uses_resource_filter(self):
        rag = FakeRAGRepository(
            resource_chunks=[
                {
                    "id": "resource-chunk",
                    "text": "Resource-specific evidence.",
                    "metadata": {"resource_id": "Resource Mid"},
                    "distance": 0.05,
                }
            ]
        )
        service = ContentContextService(kg_repository=_repository(), rag_repository=rag)

        context = service.build_context(
            "Neural Networks",
            top_k=2,
            learner_profile=_profile(known_topics=["Linear Algebra"]),
        )

        self.assertEqual(context["recommended_resources"][0]["id"], "Resource Mid")
        self.assertEqual(context["recommended_resources"][0]["match_reason"], "Related prerequisite knowledge detected; matching concept difficulty.")
        self.assertEqual(context["rag_chunks"][0]["id"], "resource-chunk")
        self.assertEqual(rag.resource_calls, [{"resource_id": "Resource Mid", "topic_name": "Neural Networks", "top_k": 2}])
        self.assertEqual(rag.calls, [])

    def test_build_context_falls_back_to_topic_chunks_when_resource_filter_misses(self):
        rag = FakeRAGRepository(resource_chunks=[])
        service = ContentContextService(kg_repository=_repository(), rag_repository=rag)

        context = service.build_context(
            "Neural Networks",
            top_k=2,
            learner_profile=_profile(known_topics=["Linear Algebra"]),
        )

        self.assertEqual(context["rag_chunks"][0]["id"], "chunk-1")
        self.assertEqual(rag.resource_calls, [{"resource_id": "Resource Mid", "topic_name": "Neural Networks", "top_k": 2}])
        self.assertEqual(rag.calls, [{"topic_name": "Neural Networks", "top_k": 2}])


if __name__ == "__main__":
    unittest.main()
