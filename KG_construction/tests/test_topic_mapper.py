import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.topic_mapper import TopicMapper
from infra.kg_repository import KGRepository


class TopicMapperTest(unittest.TestCase):
    def test_topic_mapper_returns_ranked_candidates(self):
        graph_data = {
            "nodes": [
                {"id": "Neural Networks", "description": "Models built from layered neurons."},
                {"id": "Backpropagation", "description": "Gradient-based training algorithm."},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        repository = KGRepository.from_json(temp_path)
        fake_embeddings = np.array([[1.0, 0.0], [0.2, 0.8]])
        with patch.object(TopicMapper, "_embed", side_effect=[fake_embeddings, np.array([[1.0, 0.0]])]):
            mapper = TopicMapper(repository)
            result = mapper.map_targets(["neural networks"])

        self.assertEqual(result["matched_targets"][0]["matched_name"], "Neural Networks")


if __name__ == "__main__":
    unittest.main()
