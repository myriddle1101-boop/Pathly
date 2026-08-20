import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.planning_agent import PlanningAgent
from infra.profile_schema import LearnerProfile


class FakeRepository:
    def __init__(self):
        self.topics = {
            "Probability": {"id": "Probability", "difficulty_level": 2},
            "Linear Algebra": {"id": "Linear Algebra", "difficulty_level": 3},
            "Neural Networks": {"id": "Neural Networks", "difficulty_level": 4},
            "Backpropagation": {"id": "Backpropagation", "difficulty_level": 3},
        }

    def get_topic(self, name):
        if name in self.topics:
            return self.topics[name]
        for key, value in self.topics.items():
            if key.lower() == str(name).lower():
                return value
        return None


class PlanningAgentTest(unittest.TestCase):
    @patch("agents.planning_agent.TimeAllocator")
    @patch("agents.planning_agent.PathPlanner")
    @patch("agents.planning_agent.TopicMapper")
    @patch("agents.planning_agent.GoalParser")
    @patch("agents.planning_agent.create_kg_repository")
    def test_generate_plan_uses_skill_tree_priority_and_reasoning_trace(
        self,
        mock_factory,
        mock_goal_parser_cls,
        mock_topic_mapper_cls,
        mock_path_planner_cls,
        mock_time_allocator_cls,
    ):
        repository = FakeRepository()
        mock_factory.return_value = repository

        mock_goal_parser = MagicMock()
        mock_goal_parser.parse.return_value = MagicMock(
            target_concepts=["Neural Networks"],
            requested_days=7,
            daily_minutes=90,
            constraints=[],
            learning_style_hints=[],
            to_dict=lambda: {
                "goal_text": "learn neural networks",
                "target_concepts": ["Neural Networks"],
                "requested_days": 7,
                "daily_minutes": 90,
                "constraints": [],
                "learning_style_hints": [],
            },
        )
        mock_goal_parser_cls.return_value = mock_goal_parser

        mock_topic_mapper = MagicMock()
        mock_topic_mapper.map_targets.return_value = {
            "matched_targets": [
                {
                    "query": "Neural Networks",
                    "matched_name": "Neural Networks",
                    "score": 1.0,
                    "method": "exact_match",
                }
            ],
            "unmatched_terms": [],
            "mapping_explanations": ["Neural Networks -> Neural Networks (exact_match)"],
        }
        mock_topic_mapper_cls.return_value = mock_topic_mapper

        mock_path_planner = MagicMock()
        mock_path_planner.plan.return_value = {
            "algorithm": "astar",
            "known_topics": ["Backpropagation"],
            "ordered_topics": ["Linear Algebra", "Probability", "Neural Networks"],
            "prerequisite_paths": {"Neural Networks": ["Linear Algebra", "Probability", "Neural Networks"]},
            "covered_prerequisites": {
                "Linear Algebra": [],
                "Probability": [],
                "Neural Networks": ["Linear Algebra", "Probability"],
            },
        }
        mock_path_planner_cls.return_value = mock_path_planner

        mock_time_allocator = MagicMock()
        mock_time_allocator.allocate.return_value = {
            "days": [
                {
                    "day": 1,
                    "focus_topics": ["Probability", "Linear Algebra"],
                    "prerequisite_bridge": [],
                    "estimated_minutes": 110,
                    "difficulty_mix": [2, 3],
                    "reason": "Allocated within 90 minutes based on prerequisite order and learner-adjusted workload.",
                },
                {
                    "day": 2,
                    "focus_topics": ["Neural Networks"],
                    "prerequisite_bridge": ["Linear Algebra", "Probability"],
                    "estimated_minutes": 95,
                    "difficulty_mix": [4],
                    "reason": "Allocated within 90 minutes based on prerequisite order and learner-adjusted workload.",
                },
            ],
            "total_estimated_minutes": 205,
            "overflow_topics": [],
            "feasibility_warning": None,
            "topic_adjustments": [
                {"topic": "Probability", "mastery_score": 0.2, "skill_tree_score": 0.1, "adjusted_minutes": 70},
                {"topic": "Linear Algebra", "mastery_score": 0.7, "skill_tree_score": 0.9, "adjusted_minutes": 40},
                {"topic": "Neural Networks", "mastery_score": None, "skill_tree_score": 0.3, "adjusted_minutes": 95},
            ],
        }
        mock_time_allocator_cls.return_value = mock_time_allocator

        profile = LearnerProfile(
            user_id="u1",
            name="Test User",
            academic_level="undergraduate",
            domain="machine learning",
            goal_text="learn neural networks",
            target_days=7,
            daily_minutes=90,
            prior_knowledge_level=1,
            math_foundation=2,
            programming_foundation=2,
            self_regulation=3,
            known_topics=["Backpropagation"],
            skill_tree={"Probability": 0.1, "Linear Algebra": 0.9, "Neural Networks": 0.3},
            mastery_vector={"Probability": 0.2, "Linear Algebra": 0.7, "Backpropagation": 0.95},
        )

        agent = PlanningAgent()
        plan = agent.generate_plan("learn neural networks", profile)

        mock_path_planner.plan.assert_called_once_with(
            targets=["Neural Networks"],
            known_topics=["Backpropagation"],
            algorithm="astar",
        )
        mock_time_allocator.allocate.assert_called_once_with(
            ordered_topics=["Probability", "Linear Algebra", "Neural Networks"],
            profile=profile,
            requested_days=7,
            daily_minutes=90,
        )
        self.assertEqual(plan["learner_state"]["excluded_topics"], ["Backpropagation"])
        self.assertEqual(plan["learner_state"]["skill_tree_scores"]["Probability"], 0.1)
        self.assertEqual(plan["ordered_topics"], ["Probability", "Linear Algebra", "Neural Networks"])
        self.assertEqual(plan["topic_priorities"][0]["topic"], "Probability")
        self.assertEqual(plan["topic_priorities"][0]["skill_tree_score"], 0.1)
        self.assertEqual(plan["reasoning_trace"]["presentation_summary"]["headline"], "Learner-aware planning with prerequisite-safe prioritization")
        self.assertEqual(plan["reasoning_trace"]["topic_prioritization"]["ordered_topics_after_priority"], ["Probability", "Linear Algebra", "Neural Networks"])
        self.assertEqual(plan["reasoning_trace"]["time_allocation"]["topic_adjustments"][0]["topic"], "Probability")
        self.assertEqual(plan["planning_method"]["learner_prioritization"], "prerequisite_safe_readiness_gap_then_difficulty")


if __name__ == "__main__":
    unittest.main()
