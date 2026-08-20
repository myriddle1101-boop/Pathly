import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluation.kg_quality_eval import metric_breakdown, normalize_edge_set, normalize_topic_set


class KgQualityEvalTest(unittest.TestCase):
    def test_normalize_topic_set_uses_lowercase_names(self):
        values = normalize_topic_set([{"name": " Model Training "}, {"name": "MODEL TRAINING"}, {"name": ""}])
        self.assertEqual(values, {"model training"})

    def test_normalize_edge_set_deduplicates_pairs(self):
        values = normalize_edge_set(
            [
                {"from": "A", "to": "B"},
                {"from": " a ", "to": "b"},
                {"from": "", "to": "C"},
            ]
        )
        self.assertEqual(values, {("a", "b")})

    def test_metric_breakdown_returns_precision_recall_and_f1(self):
        metrics = metric_breakdown({"a", "b", "c"}, {"b", "c", "d"})
        self.assertEqual(metrics["tp"], 2)
        self.assertEqual(metrics["fp"], 1)
        self.assertEqual(metrics["fn"], 1)
        self.assertEqual(metrics["precision"], 0.6667)
        self.assertEqual(metrics["recall"], 0.6667)
        self.assertEqual(metrics["f1"], 0.6667)


if __name__ == "__main__":
    unittest.main()
