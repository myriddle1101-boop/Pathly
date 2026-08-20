import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.agent_context_smoke import run_agent_context_smoke
from infra.kg_repository import KGRepository


def _repository() -> KGRepository:
    graph_data = {
        "nodes": [
            {"id": "Linear Algebra", "description": "Math prerequisite."},
            {"id": "Neural Networks", "description": "Layered models."},
            {"id": "Backpropagation", "description": "Training algorithm."},
        ],
        "edges": [
            {"from": "Linear Algebra", "to": "Neural Networks", "relation": "prerequisite"},
            {"from": "Neural Networks", "to": "Backpropagation", "relation": "similarity", "score": 0.8},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(graph_data, f)
        graph_path = f.name
    return KGRepository.from_json(graph_path)


class AgentContextSmokeTest(unittest.TestCase):
    def test_agent_context_smoke_passes_for_json_repository(self):
        with patch("infra.agent_context_smoke.create_kg_repository", return_value=_repository()):
            result = run_agent_context_smoke("Neural Networks", backend="json", top_k=2)

        self.assertTrue(result["passed"])
        self.assertTrue(result["content_context"]["concept_found"])
        self.assertEqual(result["content_context"]["prerequisites"], ["Linear Algebra"])
        self.assertEqual(result["adaptation_candidates"]["candidate_count"], 1)
        self.assertEqual(result["adaptation_candidates"]["candidates"][0]["concept_id"], "Backpropagation")
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_agent_context_smoke_fails_when_concept_is_missing(self):
        with patch("infra.agent_context_smoke.create_kg_repository", return_value=_repository()):
            result = run_agent_context_smoke("Missing Concept", backend="json", top_k=2)

        self.assertFalse(result["passed"])
        self.assertFalse(result["content_context"]["concept_found"])
        self.assertFalse(result["adaptation_candidates"]["concept_found"])

    def test_agent_context_smoke_reports_backend_errors(self):
        with patch("infra.agent_context_smoke.create_kg_repository", side_effect=RuntimeError("Neo4j unavailable")):
            result = run_agent_context_smoke("Neural Networks", backend="neo4j", top_k=2)

        self.assertFalse(result["passed"])
        self.assertEqual(result["error"], "Neo4j unavailable")


if __name__ == "__main__":
    unittest.main()
