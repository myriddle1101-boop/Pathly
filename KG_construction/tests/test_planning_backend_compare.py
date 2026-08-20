import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.kg_repository import KGRepository
from infra.planning_backend_compare import compare_planning_backends, stable_planning_view


def _repository() -> KGRepository:
    graph_data = {
        "nodes": [
            {
                "id": "Linear Algebra",
                "description": "Math prerequisite.",
                "difficulty_level": 1,
                "estimated_learning_time": "30 min",
            },
            {
                "id": "Neural Networks",
                "description": "Layered models.",
                "difficulty_level": 2,
                "estimated_learning_time": "1 hour",
            },
        ],
        "edges": [
            {"from": "Linear Algebra", "to": "Neural Networks", "relation": "prerequisite"},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(graph_data, f)
        graph_path = f.name
    return KGRepository.from_json(graph_path)


def _factory(graph_path=None, backend=None):
    return _repository()


def _failing_factory(graph_path=None, backend=None):
    if backend == "neo4j":
        raise RuntimeError("Neo4j backend requested but NEO4J_PASSWORD is empty.")
    return _repository()


class PlanningBackendCompareTest(unittest.TestCase):
    def test_stable_planning_view_ignores_plan_id_and_reasons(self):
        plan = {
            "plan_id": "unstable",
            "goal": {"target_concepts": ["A"], "requested_days": 1, "daily_minutes": 60},
            "target_topics": ["A"],
            "ordered_topics": ["A"],
            "prerequisite_paths": {"A": ["A"]},
            "covered_prerequisites": {"A": []},
            "days": [
                {
                    "day": 1,
                    "focus_topics": ["A"],
                    "prerequisite_bridge": [],
                    "estimated_minutes": 60,
                    "difficulty_mix": [1],
                    "reason": "unstable text",
                }
            ],
            "overflow_topics": [],
        }

        stable = stable_planning_view(plan)

        self.assertNotIn("plan_id", stable)
        self.assertNotIn("reason", stable["days"][0])

    def test_compare_planning_backends_passes_when_stable_fields_match(self):
        with patch("infra.planning_backend_compare.create_kg_repository", side_effect=_factory):
            result = compare_planning_backends(
                goal_text="learn neural networks",
                target_concepts=["Neural Networks"],
                days=2,
                daily_minutes=90,
            )

        self.assertTrue(result["passed"])
        self.assertEqual(result["json"], result["neo4j"])
        self.assertEqual(result["json"]["target_topics"], ["Neural Networks"])
        self.assertEqual(result["json"]["ordered_topics"], ["Linear Algebra", "Neural Networks"])

    def test_compare_planning_backends_reports_neo4j_setup_error(self):
        with patch("infra.planning_backend_compare.create_kg_repository", side_effect=_failing_factory):
            result = compare_planning_backends(
                goal_text="learn neural networks",
                target_concepts=["Neural Networks"],
            )

        self.assertFalse(result["passed"])
        self.assertIn("NEO4J_PASSWORD", result["error"])


if __name__ == "__main__":
    unittest.main()
