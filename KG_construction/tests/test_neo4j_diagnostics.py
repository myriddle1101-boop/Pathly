import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.neo4j_diagnostics import _bolt_reachability, _env_keys_present, run_diagnostics


class Neo4jDiagnosticsTest(unittest.TestCase):
    def test_diagnostics_default_is_read_only_and_hides_password(self):
        graph_data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"from": "A", "to": "B", "relation": "prerequisite"}],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            graph_path = f.name

        result = run_diagnostics(Path(graph_path), live=False)

        self.assertTrue(result["passed"])
        self.assertEqual(result["dry_run_verification"]["expected"]["concepts"], 2)
        self.assertEqual(result["dry_run_verification"]["expected"]["prerequisite_edges"], 1)
        self.assertFalse(result["live_verification"]["attempted"])
        self.assertEqual(
            [item["scope"] for item in result["environment"]["env_files"]],
            ["project_root", "kg_construction"],
        )
        self.assertTrue(all("exists" in item for item in result["environment"]["env_files"]))
        self.assertTrue(all("keys_present" in item for item in result["environment"]["env_files"]))
        self.assertIn("neo4j_password_configured", result["environment"])
        self.assertIn("neo4j_bolt_reachability", result["environment"])
        self.assertNotIn("neo4j_password", result["environment"])

    def test_env_keys_present_reports_key_names_without_values(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write("# comment\n")
            f.write("KG_BACKEND=neo4j\n")
            f.write("NEO4J_PASSWORD=secret-value-that-should-not-be-returned\n")
            env_path = Path(f.name)

        result = _env_keys_present(env_path)

        self.assertTrue(result["KG_BACKEND"])
        self.assertTrue(result["NEO4J_PASSWORD"])
        self.assertFalse(result["NEO4J_URI"])
        self.assertNotIn("secret-value-that-should-not-be-returned", str(result))

    def test_bolt_reachability_reports_open_port(self):
        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("infra.neo4j_diagnostics.socket.create_connection", return_value=FakeConnection()) as connect:
            result = _bolt_reachability("bolt://localhost:7687")

        self.assertTrue(result["reachable"])
        self.assertEqual(result["host"], "localhost")
        self.assertEqual(result["port"], 7687)
        self.assertIsNone(result["error"])
        connect.assert_called_once_with(("localhost", 7687), timeout=1.0)

    def test_bolt_reachability_reports_closed_port(self):
        with patch("infra.neo4j_diagnostics.socket.create_connection", side_effect=OSError("connection refused")):
            result = _bolt_reachability("bolt://localhost:7687")

        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "connection refused")

    def test_diagnostics_live_captures_connection_errors(self):
        graph_data = {"nodes": [{"id": "A"}], "edges": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            graph_path = f.name

        def fake_verify(path, live=False):
            if live:
                raise RuntimeError("connection failed")
            return {
                "graph_path": str(path),
                "mode": "dry_run",
                "expected": {
                    "concepts": 1,
                    "prerequisite_edges": 0,
                    "similarity_edges": 0,
                    "skipped_edges": 0,
                },
                "actual": None,
                "passed": True,
                "checks": ["dry_run_mapping_count_available"],
            }

        with patch("infra.neo4j_diagnostics.verify_graph", side_effect=fake_verify):
            result = run_diagnostics(Path(graph_path), live=True)

        self.assertFalse(result["passed"])
        self.assertTrue(result["live_verification"]["attempted"])
        self.assertFalse(result["live_verification"]["passed"])
        self.assertEqual(result["live_verification"]["error"], "connection failed")


if __name__ == "__main__":
    unittest.main()
