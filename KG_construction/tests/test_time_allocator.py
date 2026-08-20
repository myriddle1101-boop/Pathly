import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.time_allocator import TimeAllocator
from infra.kg_repository import KGRepository
from infra.profile_schema import LearnerProfile


class TimeAllocatorTest(unittest.TestCase):
    def test_time_allocator_creates_requested_days(self):
        graph_data = {
            "nodes": [
                {"id": "Topic A", "difficulty_level": 2, "estimated_learning_time": "1 hour"},
                {"id": "Topic B", "difficulty_level": 3, "estimated_learning_time": "1 hour"},
            ],
            "edges": [
                {"from": "Topic A", "to": "Topic B", "relation": "prerequisite"},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        allocator = TimeAllocator(KGRepository.from_json(temp_path))
        profile = LearnerProfile(
            user_id="u1",
            name="Test",
            academic_level="undergraduate",
            domain="ml",
            goal_text="learn topic b",
            target_days=2,
            daily_minutes=120,
            prior_knowledge_level=1,
            math_foundation=2,
            programming_foundation=2,
            self_regulation=3,
        )
        result = allocator.allocate(["Topic A", "Topic B"], profile, requested_days=2, daily_minutes=120)
        self.assertEqual(len(result["days"]), 2)
        self.assertEqual(result["days"][0]["focus_topics"], ["Topic A"])

    def test_time_allocator_uses_mastery_and_skill_tree_to_adjust_minutes(self):
        graph_data = {
            "nodes": [
                {"id": "Topic A", "difficulty_level": 2, "estimated_learning_time": "60 min"},
                {"id": "Topic B", "difficulty_level": 2, "estimated_learning_time": "60 min"},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        allocator = TimeAllocator(KGRepository.from_json(temp_path))
        profile = LearnerProfile(
            user_id="u2",
            name="Test",
            academic_level="undergraduate",
            domain="ml",
            goal_text="learn topics",
            target_days=1,
            daily_minutes=240,
            prior_knowledge_level=1,
            math_foundation=2,
            programming_foundation=2,
            self_regulation=3,
            mastery_vector={"Topic A": 0.2, "Topic B": 0.7},
            skill_tree={"Topic A": 0.1, "Topic B": 0.9},
        )
        result = allocator.allocate(["Topic A", "Topic B"], profile, requested_days=1, daily_minutes=240)
        adjustments = {item["topic"]: item for item in result["topic_adjustments"]}
        self.assertGreater(adjustments["Topic A"]["adjusted_minutes"], adjustments["Topic B"]["adjusted_minutes"])
        self.assertEqual(adjustments["Topic A"]["mastery_score"], 0.2)
        self.assertEqual(adjustments["Topic B"]["mastery_score"], 0.7)
        self.assertEqual(adjustments["Topic A"]["skill_tree_score"], 0.1)
        self.assertEqual(adjustments["Topic B"]["skill_tree_score"], 0.9)

    def test_time_allocator_uses_profile_factors_to_adjust_minutes(self):
        graph_data = {
            "nodes": [
                {"id": "Topic A", "difficulty_level": 4, "estimated_learning_time": "60 min"},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        allocator = TimeAllocator(KGRepository.from_json(temp_path))
        base = dict(
            user_id="ux",
            name="Test",
            academic_level="undergraduate",
            domain="ml",
            goal_text="learn topic a",
            target_days=1,
            daily_minutes=240,
            prior_knowledge_level=1,
            mastery_vector={"Topic A": 0.4},
            skill_tree={"Topic A": 0.4},
        )
        low_support = LearnerProfile(
            **base,
            math_foundation=1,
            programming_foundation=1,
            self_regulation=2,
            confidence_level=1,
            anxiety_level=5,
            motivation_level=2,
        )
        high_support = LearnerProfile(
            **base,
            math_foundation=4,
            programming_foundation=4,
            self_regulation=5,
            confidence_level=5,
            anxiety_level=1,
            motivation_level=5,
        )
        low_result = allocator.allocate(["Topic A"], low_support, requested_days=1, daily_minutes=240)
        high_result = allocator.allocate(["Topic A"], high_support, requested_days=1, daily_minutes=240)
        low_adjustment = low_result["topic_adjustments"][0]
        high_adjustment = high_result["topic_adjustments"][0]
        self.assertGreater(low_adjustment["adjusted_minutes"], high_adjustment["adjusted_minutes"])
        self.assertGreater(low_adjustment["profile_factor"], high_adjustment["profile_factor"])


if __name__ == "__main__":
    unittest.main()
