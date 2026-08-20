import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.kg_repository import KGRepository
from infra.kg_repository_factory import create_kg_repository
from infra.neo4j_importer import _concept_params, _resolve_auto_resource_path, _resource_params, import_graph
from infra.neo4j_repository import Neo4jKGRepository
from infra.neo4j_verify import verify_graph


class Neo4jMigrationTest(unittest.TestCase):
    def test_repository_factory_keeps_json_backend_as_default(self):
        graph_data = {
            "nodes": [{"id": "Topic A", "description": "A test topic."}],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        repository = create_kg_repository(graph_path=temp_path, backend="json")
        self.assertIsInstance(repository, KGRepository)
        self.assertEqual(repository.node_names(), ["Topic A"])
        self.assertEqual(repository.topic_texts(), ["Topic A. A test topic."])

    def test_repository_factory_uses_neo4j_backend_when_requested(self):
        fake_repository = object()
        with patch("infra.neo4j_repository.Neo4jKGRepository", return_value=fake_repository) as constructor:
            repository = create_kg_repository(backend="neo4j")

        constructor.assert_called_once_with()
        self.assertIs(repository, fake_repository)

    def test_repository_factory_rejects_unknown_backend(self):
        with self.assertRaises(ValueError):
            create_kg_repository(backend="unknown")

    def test_json_repository_returns_concept_context(self):
        graph_data = {
            "nodes": [
                {"id": "A", "description": "Prerequisite."},
                {"id": "B", "description": "Target."},
                {"id": "C", "description": "Similar."},
            ],
            "edges": [
                {"from": "A", "to": "B", "relation": "prerequisite"},
                {"from": "B", "to": "C", "relation": "similarity", "score": 0.8},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        repository = KGRepository.from_json(temp_path)
        context = repository.get_concept_context("B")

        self.assertEqual(context["concept"]["id"], "B")
        self.assertEqual(context["prerequisites"], ["A"])
        self.assertEqual(context["similar"], [{"name": "C", "score": 0.8}])
        self.assertEqual(context["resources"], [])

    def test_concept_params_preserve_graph_node_fields(self):
        params = _concept_params(
            {
                "id": "Neural Networks",
                "description": "Layered models.",
                "difficulty_level": 3,
                "estimated_learning_time": "1-2 hours",
                "target_audience": "Undergraduate",
                "key_sub_concepts": ["Activation", "Backpropagation"],
            }
        )

        self.assertEqual(params["id"], "Neural Networks")
        self.assertEqual(params["name"], "Neural Networks")
        self.assertEqual(params["description"], "Layered models.")
        self.assertEqual(params["difficulty_level"], 3)
        self.assertEqual(params["key_sub_concepts"], '["Activation", "Backpropagation"]')

    def test_resource_params_use_file_sha256_as_stable_id(self):
        with tempfile.NamedTemporaryFile("w", suffix=".pdf", delete=False, encoding="utf-8") as f:
            f.write("resource")
            temp_path = f.name

        params = _resource_params(Path(temp_path))

        self.assertEqual(params["filename"], Path(temp_path).name)
        self.assertEqual(params["doc_type"], "pdf")
        self.assertEqual(params["source_type"], "pdf")
        self.assertTrue(params["sha256"])
        self.assertEqual(params["id"], params["sha256"])

    def test_importer_dry_run_counts_concepts_and_edges(self):
        graph_data = {
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            "edges": [
                {"from": "A", "to": "B", "relation": "prerequisite"},
                {"from": "B", "to": "C", "relation": "similarity"},
                {"from": "", "to": "C", "relation": "similarity"},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        stats = import_graph(Path(temp_path), dry_run=True)

        self.assertTrue(stats["dry_run"])
        self.assertEqual(stats["concepts"], 3)
        self.assertEqual(stats["prerequisite_edges"], 1)
        self.assertEqual(stats["similarity_edges"], 1)
        self.assertEqual(stats["resources"], 0)
        self.assertEqual(stats["has_resource_edges"], 0)
        self.assertEqual(stats["skipped_edges"], 1)

    def test_importer_dry_run_counts_optional_resource_mapping(self):
        graph_data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            graph_path = f.name
        with tempfile.NamedTemporaryFile("w", suffix=".pdf", delete=False, encoding="utf-8") as f:
            f.write("pdf")
            resource_path = f.name

        stats = import_graph(Path(graph_path), dry_run=True, resource_path=Path(resource_path))

        self.assertEqual(stats["concepts"], 2)
        self.assertEqual(stats["resources"], 1)
        self.assertEqual(stats["has_resource_edges"], 2)

    def test_auto_resource_path_uses_single_sibling_pdf_for_run_graph(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            graph_path = run_dir / "knowledge_graph.json"
            graph_path.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
            pdf_path = run_dir / "lecture.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")

            self.assertEqual(_resolve_auto_resource_path(graph_path), pdf_path)

    def test_auto_resource_path_is_conservative_for_multiple_pdfs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            graph_path = run_dir / "knowledge_graph.json"
            graph_path.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
            (run_dir / "one.pdf").write_text("pdf", encoding="utf-8")
            (run_dir / "two.pdf").write_text("pdf", encoding="utf-8")

            self.assertIsNone(_resolve_auto_resource_path(graph_path))

    def test_importer_dry_run_can_auto_bind_single_run_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            graph_path = run_dir / "knowledge_graph.json"
            graph_path.write_text(json.dumps({"nodes": [{"id": "A"}, {"id": "B"}], "edges": []}), encoding="utf-8")
            pdf_path = run_dir / "lecture.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")

            stats = import_graph(graph_path, dry_run=True, auto_resource=True)

        self.assertEqual(stats["concepts"], 2)
        self.assertEqual(stats["resources"], 1)
        self.assertEqual(stats["has_resource_edges"], 2)
        self.assertEqual(stats["resource_path"], str(pdf_path))

    def test_explicit_resource_path_overrides_auto_resource(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            graph_path = run_dir / "knowledge_graph.json"
            graph_path.write_text(json.dumps({"nodes": [{"id": "A"}], "edges": []}), encoding="utf-8")
            (run_dir / "auto.pdf").write_text("pdf", encoding="utf-8")
            explicit_path = run_dir / "explicit.txt"
            explicit_path.write_text("resource", encoding="utf-8")

            stats = import_graph(graph_path, dry_run=True, resource_path=explicit_path, auto_resource=True)

        self.assertEqual(stats["resources"], 1)
        self.assertEqual(stats["has_resource_edges"], 1)
        self.assertEqual(stats["resource_path"], str(explicit_path))

    def test_verify_graph_dry_run_reports_expected_counts(self):
        graph_data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"from": "A", "to": "B", "relation": "prerequisite"}],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        result = verify_graph(Path(temp_path), live=False)

        self.assertTrue(result["passed"])
        self.assertEqual(result["mode"], "dry_run")
        self.assertEqual(result["expected"]["concepts"], 2)
        self.assertEqual(result["expected"]["prerequisite_edges"], 1)
        self.assertIsNone(result["actual"])

    def test_verify_graph_live_compares_expected_and_actual_counts(self):
        graph_data = {
            "nodes": [{"id": "A"}],
            "edges": [{"from": "A", "to": "A", "relation": "similarity"}],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        with patch(
            "infra.neo4j_verify._live_counts",
            return_value={
                "concepts": 1,
                "prerequisite_edges": 0,
                "similarity_edges": 1,
                "forbidden_learner_state_nodes": 0,
                "forbidden_learner_state_examples": [],
            },
        ):
            result = verify_graph(Path(temp_path), live=True)

        self.assertTrue(result["passed"])
        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["actual"]["similarity_edges"], 1)
        self.assertTrue(result["checks"][-1]["passed"])
        self.assertEqual(result["checks"][-1]["name"], "forbidden_learner_state_nodes")

    def test_verify_graph_live_can_validate_resource_coverage(self):
        graph_data = {"nodes": [{"id": "A"}], "edges": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        with patch(
            "infra.neo4j_verify._live_counts",
            return_value={
                "concepts": 1,
                "prerequisite_edges": 0,
                "similarity_edges": 0,
                "forbidden_learner_state_nodes": 0,
                "forbidden_learner_state_examples": [],
                "resources": 9,
                "has_resource_edges": 87,
                "incomplete_resources": [],
            },
        ):
            result = verify_graph(
                Path(temp_path),
                live=True,
                include_resources=True,
                min_resources=9,
                min_has_resource_edges=87,
            )

        self.assertTrue(result["passed"])
        self.assertEqual(result["checks"][-3]["name"], "resources")
        self.assertEqual(result["checks"][-2]["name"], "has_resource_edges")
        self.assertEqual(result["checks"][-1]["name"], "resource_required_fields")

    def test_verify_graph_live_fails_for_incomplete_resources(self):
        graph_data = {"nodes": [{"id": "A"}], "edges": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        with patch(
            "infra.neo4j_verify._live_counts",
            return_value={
                "concepts": 1,
                "prerequisite_edges": 0,
                "similarity_edges": 0,
                "forbidden_learner_state_nodes": 0,
                "forbidden_learner_state_examples": [],
                "resources": 1,
                "has_resource_edges": 1,
                "incomplete_resources": [{"id": "r1", "missing_fields": ["sha256"]}],
            },
        ):
            result = verify_graph(Path(temp_path), live=True, include_resources=True)

        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"][-1]["name"], "resource_required_fields")
        self.assertEqual(result["checks"][-1]["examples"][0]["missing_fields"], ["sha256"])

    def test_verify_graph_live_fails_when_learner_state_is_in_neo4j(self):
        graph_data = {"nodes": [{"id": "A"}], "edges": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            temp_path = f.name

        with patch(
            "infra.neo4j_verify._live_counts",
            return_value={
                "concepts": 1,
                "prerequisite_edges": 0,
                "similarity_edges": 0,
                "forbidden_learner_state_nodes": 1,
                "forbidden_learner_state_examples": [
                    {"labels": ["Concept"], "id": "A", "fields": ["mastery_vector"]}
                ],
            },
        ):
            result = verify_graph(Path(temp_path), live=True)

        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"][-1]["name"], "forbidden_learner_state_nodes")
        self.assertEqual(result["checks"][-1]["actual"], 1)
        self.assertEqual(result["checks"][-1]["examples"][0]["fields"], ["mastery_vector"])

    def test_neo4j_repository_context_shapes_rows(self):
        repository = object.__new__(Neo4jKGRepository)

        def fake_run(query, **params):
            return [
                {
                    "concept": {"id": "B", "description": "Target."},
                    "prerequisites": ["A"],
                    "similar": [{"name": "C", "score": 0.8}, {"name": None, "score": 0.0}],
                    "resources": [
                        {
                            "id": "r1",
                            "title": "Doc",
                            "filename": "doc.pdf",
                            "path": "doc.pdf",
                            "sha256": "abc",
                            "doc_type": "pdf",
                            "source_type": "pdf",
                            "relevance": None,
                            "resource_difficulty": 2.5,
                            "difficulty_source": "linked_concept_average",
                        },
                        {"id": None},
                    ],
                }
            ]

        repository._run = fake_run
        context = repository.get_concept_context("B")

        self.assertEqual(context["concept"]["id"], "B")
        self.assertEqual(context["prerequisites"], ["A"])
        self.assertEqual(context["similar"], [{"name": "C", "score": 0.8}])
        self.assertEqual(context["resources"][0]["id"], "r1")
        self.assertEqual(context["resources"][0]["resource_difficulty"], 2.5)
        self.assertEqual(context["resources"][0]["difficulty_source"], "linked_concept_average")

    def test_neo4j_repository_basic_neighbor_methods_shape_rows(self):
        repository = object.__new__(Neo4jKGRepository)

        def fake_run(query, **params):
            if "PREREQUISITE_OF]->(c:Concept" in query:
                return [{"id": "A"}, {"id": "B"}]
            if "-[:PREREQUISITE_OF]->(dep:Concept)" in query:
                return [{"id": "D"}]
            if "SIMILAR_TO" in query:
                return [{"name": "S", "score": 0.75}]
            return []

        repository._run = fake_run

        self.assertEqual(repository.get_prerequisites("C"), ["A", "B"])
        self.assertEqual(repository.get_dependents("C"), ["D"])
        self.assertEqual(repository.get_similar("C"), [{"name": "S", "score": 0.75}])

    def test_neo4j_repository_prerequisite_subgraph_builds_networkx_graph(self):
        repository = object.__new__(Neo4jKGRepository)

        def fake_run(query, **params):
            if "RETURN properties(c) AS props" in query:
                return [
                    {"props": {"id": "A", "difficulty_level": 1}},
                    {"props": {"id": "B", "difficulty_level": 2}},
                ]
            if "RETURN pre.id AS source" in query:
                return [{"source": "A", "target": "B", "props": {"reason": "A before B"}}]
            return []

        repository._run = fake_run
        graph = repository.prerequisite_subgraph()

        self.assertEqual(sorted(graph.nodes()), ["A", "B"])
        self.assertTrue(graph.has_edge("A", "B"))
        self.assertEqual(graph["A"]["B"]["relation"], "prerequisite")
        self.assertEqual(repository.get_topological_learning_order(["B"]), ["A", "B"])


if __name__ == "__main__":
    unittest.main()
