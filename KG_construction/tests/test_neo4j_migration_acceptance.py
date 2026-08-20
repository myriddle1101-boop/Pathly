import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.neo4j_migration_acceptance import run_acceptance


class Neo4jMigrationAcceptanceTest(unittest.TestCase):
    def test_acceptance_runs_read_only_gates_by_default(self):
        calls = []

        def ok(name):
            def inner(*args, **kwargs):
                calls.append(name)
                return {"passed": True, "name": name}

            return inner

        with patch("infra.neo4j_migration_acceptance.run_diagnostics", side_effect=ok("diagnostics")):
            with patch("infra.neo4j_migration_acceptance.verify_graph", side_effect=ok("verify")):
                with patch("infra.neo4j_migration_acceptance.compare_planning_backends", side_effect=ok("planning")):
                    with patch("infra.neo4j_migration_acceptance.run_agent_context_smoke", side_effect=ok("context")):
                        with patch("infra.neo4j_migration_acceptance.import_graph") as importer:
                            result = run_acceptance(
                                graph_path=Path("graph.json"),
                                concept_id="Neural Networks",
                                goal_text="learn neural networks",
                                target_concepts=["Neural Networks"],
                            )

        self.assertTrue(result["passed"])
        self.assertEqual(calls, ["diagnostics", "verify", "planning", "context"])
        importer.assert_not_called()
        self.assertEqual([gate["name"] for gate in result["gates"]], [
            "diagnostics_live",
            "verify_live_counts_and_boundaries",
            "planning_backend_comparison",
            "content_adaptation_context_smoke",
        ])

    def test_acceptance_can_import_first_when_explicitly_requested(self):
        calls = []

        def ok(name):
            def inner(*args, **kwargs):
                calls.append(name)
                return {"passed": True}

            return inner

        with patch("infra.neo4j_migration_acceptance.run_diagnostics", side_effect=ok("diagnostics")):
            with patch("infra.neo4j_migration_acceptance.verify_graph", side_effect=ok("verify")):
                with patch("infra.neo4j_migration_acceptance.compare_planning_backends", side_effect=ok("planning")):
                    with patch("infra.neo4j_migration_acceptance.run_agent_context_smoke", side_effect=ok("context")):
                        with patch("infra.neo4j_migration_acceptance.import_graph", side_effect=ok("import")) as importer:
                            result = run_acceptance(
                                graph_path=Path("graph.json"),
                                concept_id="Neural Networks",
                                goal_text="learn neural networks",
                                target_concepts=["Neural Networks"],
                                import_first=True,
                            )

        self.assertTrue(result["passed"])
        importer.assert_called_once()
        self.assertEqual(calls, ["import", "diagnostics", "verify", "planning", "context"])
        self.assertEqual([gate["name"] for gate in result["gates"]], [
            "import_graph",
            "diagnostics_live",
            "verify_live_counts_and_boundaries",
            "planning_backend_comparison",
            "content_adaptation_context_smoke",
        ])

    def test_acceptance_fails_when_any_gate_fails(self):
        with patch("infra.neo4j_migration_acceptance.run_diagnostics", return_value={"passed": True}):
            with patch("infra.neo4j_migration_acceptance.verify_graph", return_value={"passed": False, "error": "count mismatch"}):
                with patch("infra.neo4j_migration_acceptance.compare_planning_backends", return_value={"passed": True}):
                    with patch("infra.neo4j_migration_acceptance.run_agent_context_smoke", return_value={"passed": True}):
                        result = run_acceptance(
                            graph_path=Path("graph.json"),
                            concept_id="Neural Networks",
                            goal_text="learn neural networks",
                            target_concepts=["Neural Networks"],
                        )

        self.assertFalse(result["passed"])
        failed = [gate for gate in result["gates"] if not gate["passed"]]
        self.assertEqual(failed[0]["name"], "verify_live_counts_and_boundaries")
        self.assertEqual(failed[0]["error"], "count mismatch")


if __name__ == "__main__":
    unittest.main()
