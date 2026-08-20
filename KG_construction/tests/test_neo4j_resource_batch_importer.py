import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.neo4j_resource_batch_importer import discover_runs, import_resources_batch


def _write_graph(path: Path, nodes: int = 2) -> None:
    data = {
        "nodes": [{"id": f"C{i}"} for i in range(nodes)],
        "edges": [{"from": "C0", "to": "C1", "relation": "prerequisite"}] if nodes >= 2 else [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


class Neo4jResourceBatchImporterTest(unittest.TestCase):
    def test_discover_runs_marks_only_single_pdf_graph_dirs_as_eligible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eligible = root / "eligible"
            eligible.mkdir()
            _write_graph(eligible / "knowledge_graph.json")
            (eligible / "doc.pdf").write_text("pdf", encoding="utf-8")

            no_graph = root / "no_graph"
            no_graph.mkdir()
            (no_graph / "doc.pdf").write_text("pdf", encoding="utf-8")

            no_pdf = root / "no_pdf"
            no_pdf.mkdir()
            _write_graph(no_pdf / "knowledge_graph.json")

            multi_pdf = root / "multi_pdf"
            multi_pdf.mkdir()
            _write_graph(multi_pdf / "knowledge_graph.json")
            (multi_pdf / "one.pdf").write_text("pdf", encoding="utf-8")
            (multi_pdf / "two.pdf").write_text("pdf", encoding="utf-8")

            statuses = {item["name"]: item for item in discover_runs(root)}

        self.assertTrue(statuses["eligible"]["eligible"])
        self.assertFalse(statuses["no_graph"]["eligible"])
        self.assertEqual(statuses["no_graph"]["skip_reasons"], ["missing_knowledge_graph"])
        self.assertEqual(statuses["no_pdf"]["skip_reasons"], ["missing_pdf"])
        self.assertEqual(statuses["multi_pdf"]["skip_reasons"], ["multiple_pdfs"])

    def test_import_resources_batch_aggregates_dry_run_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name, nodes in [("run_a", 2), ("run_b", 3)]:
                run_dir = root / name
                run_dir.mkdir()
                _write_graph(run_dir / "knowledge_graph.json", nodes=nodes)
                (run_dir / f"{name}.pdf").write_text("pdf", encoding="utf-8")

            result = import_resources_batch(root, dry_run=True)

        self.assertTrue(result["passed"])
        self.assertEqual(result["processed_count"], 2)
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["totals"]["concept_import_attempts"], 5)
        self.assertEqual(result["totals"]["resources"], 2)
        self.assertEqual(result["totals"]["has_resource_edges"], 5)

    def test_discover_runs_supports_app_nested_hash_run_dirs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parent = root / "uploaded_doc"
            nested = parent / "abc123"
            nested.mkdir(parents=True)
            _write_graph(nested / "knowledge_graph.json")
            (nested / "uploaded_doc.pdf").write_text("pdf", encoding="utf-8")

            statuses = discover_runs(root)

        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["name"], "abc123")
        self.assertTrue(statuses[0]["eligible"])

    def test_import_resources_batch_fail_on_skip_marks_result_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skipped = root / "skipped"
            skipped.mkdir()
            _write_graph(skipped / "knowledge_graph.json")

            result = import_resources_batch(root, dry_run=True, fail_on_skip=True)

        self.assertFalse(result["passed"])
        self.assertEqual(result["processed_count"], 0)
        self.assertEqual(result["skipped_count"], 1)

    def test_import_resources_batch_delegates_live_import_to_existing_importer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            run_dir.mkdir()
            _write_graph(run_dir / "knowledge_graph.json")
            (run_dir / "doc.pdf").write_text("pdf", encoding="utf-8")

            with patch(
                "infra.neo4j_resource_batch_importer.import_graph",
                return_value={
                    "concepts": 2,
                    "prerequisite_edges": 1,
                    "similarity_edges": 0,
                    "resources": 1,
                    "has_resource_edges": 2,
                    "skipped_edges": 0,
                },
            ) as importer:
                result = import_resources_batch(root, dry_run=False)

        self.assertTrue(result["passed"])
        importer.assert_called_once_with(run_dir / "knowledge_graph.json", dry_run=False, auto_resource=True)
        self.assertEqual(result["totals"]["resources"], 1)


if __name__ == "__main__":
    unittest.main()
