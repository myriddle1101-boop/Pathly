import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.adaptation_candidate_service import AdaptationCandidateService
from infra.kg_repository import KGRepository


def _repository(graph_data: dict) -> KGRepository:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(graph_data, f)
        temp_path = f.name
    return KGRepository.from_json(temp_path)


class AdaptationCandidateServiceTest(unittest.TestCase):
    def test_suggest_candidates_prefers_similarity_edges(self):
        repository = _repository(
            {
                "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                "edges": [
                    {"from": "C", "to": "A", "relation": "prerequisite"},
                    {"from": "A", "to": "B", "relation": "similarity", "score": 0.9},
                ],
            }
        )
        service = AdaptationCandidateService(repository)

        result = service.suggest_candidates("A")

        self.assertTrue(result["concept_found"])
        self.assertEqual(result["decision_policy"], "similarity_first_then_prerequisite_bridge")
        self.assertEqual(result["candidates"][0]["concept_id"], "B")
        self.assertEqual(result["candidates"][0]["source"], "similarity")
        self.assertEqual(result["boundaries"]["profile_store"], "not updated")
        self.assertEqual(result["boundaries"]["planning_calendar"], "not reallocated")

    def test_suggest_candidates_falls_back_to_prerequisites(self):
        repository = _repository(
            {
                "nodes": [{"id": "A"}, {"id": "Prereq 1"}, {"id": "Prereq 2"}],
                "edges": [
                    {"from": "Prereq 2", "to": "A", "relation": "prerequisite"},
                    {"from": "Prereq 1", "to": "A", "relation": "prerequisite"},
                ],
            }
        )
        service = AdaptationCandidateService(repository)

        result = service.suggest_candidates("A", limit=1)

        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["concept_id"], "Prereq 1")
        self.assertEqual(result["candidates"][0]["source"], "prerequisite")


if __name__ == "__main__":
    unittest.main()
