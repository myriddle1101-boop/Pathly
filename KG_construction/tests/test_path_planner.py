import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.path_planner import PathPlanner
from infra.kg_repository import KGRepository


class PathPlannerTest(unittest.TestCase):
    def test_path_planner_returns_topological_order(self):
        graph_data = {
            "nodes": [
                {"id": "Linear Algebra", "difficulty_level": 1},
                {"id": "Backpropagation", "difficulty_level": 3},
                {"id": "Neural Networks", "difficulty_level": 3},
            ],
            "edges": [
                {"from": "Linear Algebra", "to": "Backpropagation", "relation": "prerequisite"},
                {"from": "Backpropagation", "to": "Neural Networks", "relation": "prerequisite"},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        planner = PathPlanner(KGRepository.from_json(temp_path))
        result = planner.plan(targets=["Neural Networks"], known_topics=[], algorithm="bfs")
        self.assertEqual(result["ordered_topics"], ["Linear Algebra", "Backpropagation", "Neural Networks"])


if __name__ == "__main__":
    unittest.main()
