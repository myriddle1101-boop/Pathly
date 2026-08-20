import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.goal_parser import GoalParser


class GoalParserTest(unittest.TestCase):
    def test_rule_parser_extracts_days_minutes_and_chinese_target(self):
        parser = GoalParser()
        request = parser._parse_with_rules(
            "我想在 7 天内学习神经网络基础，每天 90 分钟",
            default_days=5,
            default_daily_minutes=60,
        )
        self.assertEqual(request.requested_days, 7)
        self.assertEqual(request.daily_minutes, 90)
        self.assertEqual(request.target_concepts, ["Neural Networks"])


    def test_parse_keeps_known_user_goal_as_one_canonical_concept(self):
        parser = GoalParser()
        cases = {
            "machine learning": "Machine Learning",
            "我想学 transformer": "Transformers",
            "我想学 RAG": "Retrieval-Augmented Generation (RAG)",
        }
        for goal, expected in cases.items():
            with self.subTest(goal=goal):
                request = parser.parse(goal, default_days=30, default_daily_minutes=90)
                self.assertEqual(request.target_concepts, [expected])
                self.assertEqual(request.constraints, [])
                self.assertEqual(request.learning_style_hints, [])


if __name__ == "__main__":
    unittest.main()
