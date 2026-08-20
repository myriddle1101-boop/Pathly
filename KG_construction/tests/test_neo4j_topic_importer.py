import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.neo4j_topic_importer import assign_topic, build_topic_plan, import_topics
from infra.neo4j_verify import verify_graph


class Neo4jTopicImporterTest(unittest.TestCase):
    def test_assign_topic_prefers_domain_keywords(self):
        node = {
            "id": "Attention Mechanisms",
            "description": "Attention and transformer layers for neural sequence modeling.",
            "key_sub_concepts": ["transformer", "embedding", "sequence"],
        }

        topic = assign_topic(node)

        self.assertEqual(topic["id"], "topic_deep_learning")
        self.assertEqual(topic["name"], "Deep Learning")

    def test_build_topic_plan_assigns_every_concept_once(self):
        graph_data = {
            "nodes": [
                {"id": "Neural Networks", "description": "Deep neural models with backpropagation."},
                {"id": "Machine Translation", "description": "Natural language translation with text tokens."},
                {"id": "Gradient Descent", "description": "Optimization with gradient-based updates."},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = Path(f.name)

        plan = build_topic_plan(temp_path)

        self.assertEqual(plan["summary"]["concepts_seen"], 3)
        self.assertEqual(plan["summary"]["belongs_to_edges"], 3)
        self.assertEqual(len(plan["assignments"]), 3)
        self.assertEqual(sorted(item["concept_id"] for item in plan["assignments"]), [
            "Gradient Descent",
            "Machine Translation",
            "Neural Networks",
        ])
        topic_counts = plan["summary"]["topic_counts"]
        self.assertEqual(topic_counts["Deep Learning"], 1)
        self.assertEqual(topic_counts["Natural Language Processing"], 1)
        self.assertEqual(topic_counts["Optimization"], 1)

    def test_verify_graph_dry_run_includes_topic_expectations(self):
        graph_data = {
            "nodes": [
                {"id": "Neural Networks", "description": "Deep neural models."},
                {"id": "Machine Translation", "description": "Language translation task."},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = Path(f.name)

        result = verify_graph(temp_path, live=False, include_topics=True)

        self.assertTrue(result["passed"])
        self.assertEqual(result["expected"]["topics"], 8)
        self.assertEqual(result["expected"]["belongs_to_edges"], 2)
        self.assertIn("dry_run_topic_plan_available", result["checks"])

    def test_verify_graph_live_compares_topic_distribution_against_dry_run(self):
        graph_data = {
            "nodes": [
                {"id": "Neural Networks", "description": "Deep neural models."},
                {"id": "Machine Translation", "description": "Language translation task."},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = Path(f.name)

        live_counts = {
            "total_nodes": 10,
            "concepts": 2,
            "prerequisite_edges": 0,
            "similarity_edges": 0,
            "forbidden_learner_state_nodes": 0,
            "forbidden_learner_state_examples": [],
            "topics": 8,
            "belongs_to_edges": 2,
            "topic_distribution": [
                {"id": "topic_deep_learning", "name": "Deep Learning", "concept_count": 1},
                {"id": "topic_natural_language_processing", "name": "Natural Language Processing", "concept_count": 1},
            ],
        }

        with patch("infra.neo4j_verify._live_counts", return_value=live_counts):
            result = verify_graph(temp_path, live=True, include_topics=True)

        self.assertFalse(result["passed"])
        distribution_check = next(check for check in result["checks"] if check["name"] == "topic_distribution")
        self.assertFalse(distribution_check["passed"])
        self.assertEqual(distribution_check["actual"], {
            "Deep Learning": 1,
            "Natural Language Processing": 1,
        })

    def test_import_topics_replace_existing_deletes_old_belongs_to_edges_before_write(self):
        graph_data = {
            "nodes": [
                {"id": "Neural Networks", "description": "Deep neural models."},
            ],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = Path(f.name)

        class FakeSession:
            def __init__(self):
                self.calls = []

            def run(self, query, **params):
                self.calls.append((query, params))
                return self

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeDriver:
            def __init__(self, session):
                self._session = session
                self.closed = False

            def session(self, database=None):
                return self._session

            def close(self):
                self.closed = True

        fake_session = FakeSession()
        fake_driver = FakeDriver(fake_session)

        with patch("infra.neo4j_topic_importer.load_project_env"), \
             patch("infra.neo4j_topic_importer._apply_schema"), \
             patch("infra.neo4j_topic_importer._driver", return_value=fake_driver):
            result = import_topics(temp_path, write=True, replace_existing=True)

        self.assertTrue(result["replace_existing"])
        self.assertTrue(any("DELETE r" in query for query, _ in fake_session.calls))
        self.assertTrue(any("MERGE (c)-[r:BELONGS_TO]->(t)" in query for query, _ in fake_session.calls))
        self.assertTrue(fake_driver.closed)


if __name__ == "__main__":
    unittest.main()
