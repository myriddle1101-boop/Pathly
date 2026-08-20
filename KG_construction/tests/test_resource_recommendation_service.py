import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.resource_recommendation_service import ResourceRecommendationService
from infra.profile_schema import LearnerProfile


def _profile(**overrides) -> LearnerProfile:
    values = {
        "user_id": "u1",
        "name": "Test",
        "academic_level": "undergraduate",
        "domain": "ml",
        "goal_text": "learn neural networks",
        "target_days": 3,
        "daily_minutes": 60,
        "prior_knowledge_level": 1,
        "math_foundation": 1,
        "programming_foundation": 1,
        "self_regulation": 3,
        "known_topics": [],
        "confidence_level": 1,
        "anxiety_level": 5,
        "motivation_level": 1,
    }
    values.update(overrides)
    return LearnerProfile(**values)


def _context() -> dict:
    return {
        "concept": {"id": "Neural Networks", "difficulty_level": 3},
        "prerequisites": ["Linear Algebra"],
        "similar": [],
        "resources": [
            {"id": "r-low", "title": "Low", "filename": "b-low.pdf", "resource_difficulty": 2},
            {"id": "r-mid", "title": "Mid", "filename": "a-mid.pdf", "resource_difficulty": 3},
            {"id": "r-high", "title": "High", "filename": "c-high.pdf", "resource_difficulty": 4},
        ],
    }


class ResourceRecommendationServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ResourceRecommendationService()

    def test_no_prerequisite_knowledge_prefers_foundational_resource(self):
        ranked = self.service.rank_resources("Neural Networks", _profile(), _context())

        self.assertEqual(ranked[0]["id"], "r-low")
        self.assertEqual(ranked[0]["target_resource_difficulty"], 2)
        self.assertIn("foundational", ranked[0]["match_reason"])

    def test_known_prerequisite_prefers_matching_resource(self):
        ranked = self.service.rank_resources(
            "Neural Networks",
            _profile(known_topics=["Linear Algebra"]),
            _context(),
        )

        self.assertEqual(ranked[0]["id"], "r-mid")
        self.assertEqual(ranked[0]["target_resource_difficulty"], 3)

    def test_known_target_prefers_slightly_advanced_resource(self):
        ranked = self.service.rank_resources(
            "Neural Networks",
            _profile(known_topics=["Neural Networks"]),
            _context(),
        )

        self.assertEqual(ranked[0]["id"], "r-high")
        self.assertEqual(ranked[0]["target_resource_difficulty"], 4)

    def test_affective_fields_do_not_change_ranking(self):
        base = self.service.rank_resources(
            "Neural Networks",
            _profile(known_topics=["Linear Algebra"], confidence_level=1, anxiety_level=5, motivation_level=1),
            _context(),
        )
        changed = self.service.rank_resources(
            "Neural Networks",
            _profile(known_topics=["Linear Algebra"], confidence_level=5, anxiety_level=1, motivation_level=5),
            _context(),
        )

        self.assertEqual([item["id"] for item in base], [item["id"] for item in changed])

    def test_same_input_produces_stable_order(self):
        profile = _profile(known_topics=["Linear Algebra"])

        first = self.service.rank_resources("Neural Networks", profile, _context())
        second = self.service.rank_resources("Neural Networks", profile, _context())

        self.assertEqual([item["id"] for item in first], [item["id"] for item in second])

    def test_high_prior_knowledge_fallback_matches_concept_difficulty(self):
        ranked = self.service.rank_resources(
            "Neural Networks",
            _profile(prior_knowledge_level=4),
            _context(),
        )

        self.assertEqual(ranked[0]["id"], "r-mid")


if __name__ == "__main__":
    unittest.main()
