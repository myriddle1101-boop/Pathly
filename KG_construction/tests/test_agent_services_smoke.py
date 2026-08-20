import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.adaptation_candidate_service import AdaptationCandidateService
from agents.content_context_service import ContentContextService
from agents.planning_agent import PlanningAgent
from agents.planning_schema import PlanningRequest
from infra.kg_repository import KGRepository
from infra.profile_schema import LearnerProfile


class FakeRAGRepository:
    def get_chunks_by_topic(self, topic_name: str, top_k: int = 5):
        return [{"id": "chunk-1", "text": f"Evidence for {topic_name}.", "metadata": {}, "distance": 0.1}]


class FakeKGRepository:
    graph = None

    def node_names(self):
        return ["Neural Networks"]

    def topic_texts(self):
        return ["Neural Networks. Layered models."]

    def get_topic(self, name: str):
        if name.lower() == "neural networks":
            return {"id": "Neural Networks", "description": "Layered models.", "difficulty_level": 2}
        return None

    def search_topics(self, query: str, limit: int = 5):
        return []

    def prerequisite_subgraph(self):
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_node("Neural Networks", difficulty_level=2)
        return graph

    def get_prerequisites(self, node: str):
        return []


def _graph_path() -> str:
    graph_data = {
        "nodes": [
            {"id": "Linear Algebra", "description": "Math prerequisite.", "difficulty_level": 1, "estimated_learning_time": "30 min"},
            {"id": "Neural Networks", "description": "Layered models.", "difficulty_level": 2, "estimated_learning_time": "1 hour"},
            {"id": "Backpropagation", "description": "Training algorithm.", "difficulty_level": 3, "estimated_learning_time": "1 hour"},
        ],
        "edges": [
            {"from": "Linear Algebra", "to": "Neural Networks", "relation": "prerequisite"},
            {"from": "Neural Networks", "to": "Backpropagation", "relation": "prerequisite"},
            {"from": "Backpropagation", "to": "Neural Networks", "relation": "similarity", "score": 0.9},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(graph_data, f)
        return f.name


def _profile() -> LearnerProfile:
    return LearnerProfile(
        user_id="u1",
        name="Test",
        academic_level="undergraduate",
        domain="ml",
        goal_text="learn neural networks",
        target_days=2,
        daily_minutes=120,
        prior_knowledge_level=1,
        math_foundation=2,
        programming_foundation=2,
        self_regulation=3,
    )


class AgentServicesSmokeTest(unittest.TestCase):
    def test_planning_content_and_adaptation_share_same_kg_repository(self):
        graph_path = _graph_path()
        repository = KGRepository.from_json(graph_path)

        fake_embeddings = np.eye(3)
        request = PlanningRequest(
            goal_text="learn neural networks",
            target_concepts=["Neural Networks"],
            requested_days=2,
            daily_minutes=120,
        )

        with patch("agents.topic_mapper.TopicMapper._embed", side_effect=[fake_embeddings, np.array([[0.0, 1.0, 0.0]])]):
            agent = PlanningAgent(graph_path=graph_path, kg_backend="json")
            with patch.object(agent.goal_parser, "parse", return_value=request):
                plan = agent.generate_plan("learn neural networks", _profile())

        content_context = ContentContextService(repository, rag_repository=FakeRAGRepository()).build_context("Neural Networks")
        adaptation = AdaptationCandidateService(repository).suggest_candidates("Neural Networks")

        self.assertEqual(plan["target_topics"], ["Neural Networks"])
        self.assertIn("Linear Algebra", plan["ordered_topics"])
        self.assertTrue(content_context["generation_ready"])
        self.assertEqual(content_context["kg_context"]["prerequisites"], ["Linear Algebra"])
        self.assertEqual(adaptation["candidates"][0]["concept_id"], "Backpropagation")
        self.assertEqual(adaptation["candidates"][0]["source"], "similarity")

    def test_planning_agent_uses_neo4j_backend_parameter_without_live_connection(self):
        fake_repository = FakeKGRepository()
        fake_embeddings = np.array([[1.0, 0.0]])
        request = PlanningRequest(
            goal_text="learn neural networks",
            target_concepts=["Neural Networks"],
            requested_days=1,
            daily_minutes=60,
        )

        with patch("agents.planning_agent.create_kg_repository", return_value=fake_repository) as factory:
            with patch("agents.topic_mapper.TopicMapper._embed", side_effect=[fake_embeddings]):
                agent = PlanningAgent(kg_backend="neo4j")
            with patch.object(agent.goal_parser, "parse", return_value=request):
                plan = agent.generate_plan("learn neural networks", _profile())

        factory.assert_called_once_with(graph_path=None, backend="neo4j")
        self.assertIs(agent.repository, fake_repository)
        self.assertEqual(plan["target_topics"], ["Neural Networks"])


if __name__ == "__main__":
    unittest.main()
