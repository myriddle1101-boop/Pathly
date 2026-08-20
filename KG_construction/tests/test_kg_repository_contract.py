import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.kg_repository import KGRepository
from infra.neo4j_repository import Neo4jKGRepository


GRAPH_DATA = {
    "nodes": [
        {"id": "Linear Algebra", "description": "Math prerequisite.", "difficulty_level": 1},
        {"id": "Neural Networks", "description": "Layered models.", "difficulty_level": 2},
        {"id": "Backpropagation", "description": "Training algorithm.", "difficulty_level": 3},
    ],
    "edges": [
        {"from": "Linear Algebra", "to": "Neural Networks", "relation": "prerequisite", "reason": "math"},
        {"from": "Neural Networks", "to": "Backpropagation", "relation": "prerequisite", "reason": "training"},
        {"from": "Backpropagation", "to": "Neural Networks", "relation": "similarity", "score": 0.9},
    ],
}


class FakeNeo4jRepository(Neo4jKGRepository):
    def __init__(self):
        self.nodes = {node["id"]: node for node in GRAPH_DATA["nodes"]}
        self.edges = GRAPH_DATA["edges"]

    def _run(self, query: str, **params):
        if "RETURN c.id AS id ORDER BY id" in query:
            return [{"id": node_id} for node_id in sorted(self.nodes)]

        if "WHERE c.id = $name OR toLower(c.id) = toLower($name)" in query:
            name = params["name"]
            for node_id, props in self.nodes.items():
                if node_id == name or node_id.lower() == name.lower():
                    return [{"props": dict(props)}]
            return []

        if "RETURN c.id AS id, coalesce(c.description" in query:
            return [{"id": node_id, "description": props.get("description", "")} for node_id, props in self.nodes.items()]

        if "MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c:Concept {id: $node})" in query:
            node = params["node"]
            rows = [
                {"id": edge["from"]}
                for edge in self.edges
                if edge["relation"] == "prerequisite" and edge["to"] == node
            ]
            return sorted(rows, key=lambda row: row["id"])

        if "MATCH (c:Concept {id: $node})-[:PREREQUISITE_OF]->(dep:Concept)" in query:
            node = params["node"]
            rows = [
                {"id": edge["to"]}
                for edge in self.edges
                if edge["relation"] == "prerequisite" and edge["from"] == node
            ]
            return sorted(rows, key=lambda row: row["id"])

        if "MATCH (c:Concept {id: $node})-[r:SIMILAR_TO]-(sim:Concept)" in query:
            node = params["node"]
            rows = []
            for edge in self.edges:
                if edge["relation"] != "similarity":
                    continue
                if edge["from"] == node:
                    rows.append({"name": edge["to"], "score": edge["score"]})
                elif edge["to"] == node:
                    rows.append({"name": edge["from"], "score": edge["score"]})
            return sorted(rows, key=lambda row: (-row["score"], row["name"]))[: params["limit"]]

        if "MATCH (c:Concept {id: $node})" in query and "OPTIONAL MATCH" in query:
            node = params["node"]
            if node not in self.nodes:
                return []
            similar = []
            for edge in self.edges:
                if edge["relation"] != "similarity":
                    continue
                if edge["from"] == node:
                    similar.append({"name": edge["to"], "score": edge["score"]})
                elif edge["to"] == node:
                    similar.append({"name": edge["from"], "score": edge["score"]})
            return [
                {
                    "concept": dict(self.nodes[node]),
                    "prerequisites": [row["id"] for row in self._run("MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c:Concept {id: $node})", node=node)],
                    "similar": similar,
                    "resources": [],
                }
            ]

        if "MATCH (c:Concept) RETURN properties(c) AS props" in query:
            return [{"props": dict(props)} for props in self.nodes.values()]

        if "MATCH (pre:Concept)-[r:PREREQUISITE_OF]->(dep:Concept)" in query:
            return [
                {
                    "source": edge["from"],
                    "target": edge["to"],
                    "props": {"reason": edge.get("reason", "")},
                }
                for edge in self.edges
                if edge["relation"] == "prerequisite"
            ]

        return []


def _json_repository() -> KGRepository:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(GRAPH_DATA, f)
        graph_path = f.name
    return KGRepository.from_json(graph_path)


class KGRepositoryContractTest(unittest.TestCase):
    def test_json_and_neo4j_repositories_expose_same_agent_contract(self):
        json_repository = _json_repository()
        neo4j_repository = FakeNeo4jRepository()

        self.assertEqual(json_repository.node_names(), neo4j_repository.node_names())
        self.assertEqual(json_repository.topic_texts(), neo4j_repository.topic_texts())
        self.assertEqual(
            json_repository.get_prerequisites("Neural Networks"),
            neo4j_repository.get_prerequisites("Neural Networks"),
        )
        self.assertEqual(
            json_repository.get_dependents("Neural Networks"),
            neo4j_repository.get_dependents("Neural Networks"),
        )
        self.assertEqual(
            json_repository.get_similar("Neural Networks"),
            neo4j_repository.get_similar("Neural Networks"),
        )
        self.assertEqual(
            json_repository.get_topological_learning_order(["Backpropagation"]),
            neo4j_repository.get_topological_learning_order(["Backpropagation"]),
        )

        json_context = json_repository.get_concept_context("Neural Networks")
        neo4j_context = neo4j_repository.get_concept_context("Neural Networks")

        self.assertEqual(json_context["concept"], neo4j_context["concept"])
        self.assertEqual(json_context["prerequisites"], neo4j_context["prerequisites"])
        self.assertEqual(json_context["similar"], neo4j_context["similar"])
        self.assertEqual(json_context["resources"], neo4j_context["resources"])

    def test_json_repository_derives_resource_difficulty_from_linked_concepts(self):
        graph_data = {
            "nodes": [
                {"id": "Easy Concept", "difficulty_level": 1},
                {"id": "Target Concept", "difficulty_level": 3},
                {"id": "Shared Resource", "title": "Shared", "filename": "shared.pdf"},
            ],
            "edges": [
                {"from": "Easy Concept", "to": "Shared Resource", "relation": "has_resource"},
                {"from": "Target Concept", "to": "Shared Resource", "relation": "has_resource"},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(graph_data, f)
            graph_path = f.name
        repository = KGRepository.from_json(graph_path)

        context = repository.get_concept_context("Target Concept")

        self.assertEqual(context["resources"][0]["id"], "Shared Resource")
        self.assertEqual(context["resources"][0]["resource_difficulty"], 2.0)
        self.assertEqual(context["resources"][0]["difficulty_source"], "linked_concept_average")


if __name__ == "__main__":
    unittest.main()
