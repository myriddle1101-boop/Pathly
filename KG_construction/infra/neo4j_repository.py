from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

import networkx as nx

from infra.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from infra.kg_repository import TopicMatch, _maybe_json


class Neo4jKGRepository:
    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
        database: str = NEO4J_DATABASE,
    ):
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError(
                "Neo4j backend requested but the neo4j Python driver is not installed. "
                "Install it with: pip install neo4j"
            ) from exc
        if not password:
            raise RuntimeError("Neo4j backend requested but NEO4J_PASSWORD is empty.")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self) -> None:
        self.driver.close()

    def _run(self, query: str, **params):
        with self.driver.session(database=self.database) as session:
            return list(session.run(query, **params))

    def node_names(self) -> list[str]:
        rows = self._run("MATCH (c:Concept) RETURN c.id AS id ORDER BY id")
        return [row["id"] for row in rows]

    def topic_text(self, name: str) -> str:
        topic = self.get_topic(name) or {"id": name}
        description = str(topic.get("description", ""))
        return f"{topic['id']}. {description}".strip()

    def topic_texts(self) -> list[str]:
        return [self.topic_text(name) for name in self.node_names()]

    def get_topic(self, name: str) -> dict[str, Any] | None:
        rows = self._run(
            """
            MATCH (c:Concept)
            WHERE c.id = $name OR toLower(c.id) = toLower($name)
            RETURN properties(c) AS props
            LIMIT 1
            """,
            name=name,
        )
        if not rows:
            return None
        return {key: _maybe_json(value) for key, value in dict(rows[0]["props"]).items()}

    def search_topics(self, query: str, limit: int = 5) -> list[TopicMatch]:
        query_norm = query.strip().lower()
        if not query_norm:
            return []
        rows = self._run(
            """
            MATCH (c:Concept)
            RETURN c.id AS id, coalesce(c.description, '') AS description
            """
        )
        matches: list[TopicMatch] = []
        for row in rows:
            name = row["id"]
            description = row["description"]
            haystack = f"{name} {description}".lower()
            if query_norm in haystack:
                score = 1.0 if query_norm == name.lower() else 0.9
                reason = "substring_match"
            else:
                score = SequenceMatcher(None, query_norm, name.lower()).ratio()
                reason = "fuzzy_match"
            if score >= 0.45:
                matches.append(TopicMatch(name=name, score=round(score, 4), reason=reason))
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:limit]

    def get_prerequisites(self, node: str) -> list[str]:
        rows = self._run(
            """
            MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c:Concept {id: $node})
            RETURN pre.id AS id
            ORDER BY id
            """,
            node=node,
        )
        return [row["id"] for row in rows]

    def get_dependents(self, node: str) -> list[str]:
        rows = self._run(
            """
            MATCH (c:Concept {id: $node})-[:PREREQUISITE_OF]->(dep:Concept)
            RETURN dep.id AS id
            ORDER BY id
            """,
            node=node,
        )
        return [row["id"] for row in rows]

    def get_similar(self, node: str, limit: int = 5) -> list[dict[str, Any]]:
        rows = self._run(
            """
            MATCH (c:Concept {id: $node})-[r:SIMILAR_TO]-(sim:Concept)
            RETURN sim.id AS name, coalesce(r.score, 0.0) AS score
            ORDER BY score DESC, name
            LIMIT $limit
            """,
            node=node,
            limit=limit,
        )
        return [{"name": row["name"], "score": float(row["score"])} for row in rows]

    def get_concept_context(self, node: str, similar_limit: int = 5) -> dict[str, Any]:
        rows = self._run(
            """
            MATCH (c:Concept {id: $node})
            OPTIONAL MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c)
            WITH c, collect(DISTINCT pre.id) AS prerequisites
            OPTIONAL MATCH (c)-[sim_rel:SIMILAR_TO]-(sim:Concept)
            WITH c, prerequisites, collect(DISTINCT {
                     name: sim.id,
                     score: coalesce(sim_rel.score, 0.0)
                   }) AS similar
            OPTIONAL MATCH (c)-[res_rel:HAS_RESOURCE]->(res:Resource)
            OPTIONAL MATCH (linked:Concept)-[:HAS_RESOURCE]->(res)
            WITH c, prerequisites, similar, res, res_rel,
                 avg(toFloat(coalesce(linked.difficulty_level, 3))) AS resource_difficulty
            RETURN properties(c) AS concept,
                   prerequisites,
                   similar,
                   collect(DISTINCT {
                     id: res.id,
                     title: res.title,
                     filename: res.filename,
                     path: res.path,
                     sha256: res.sha256,
                     doc_type: res.doc_type,
                     source_type: res.source_type,
                     relevance: properties(res_rel).relevance,
                     resource_difficulty: resource_difficulty,
                     difficulty_source: CASE
                       WHEN res.id IS NULL THEN null
                       ELSE "linked_concept_average"
                     END
                   }) AS resources
            """,
            node=node,
        )
        if not rows:
            return {"concept": None, "prerequisites": [], "similar": [], "resources": []}
        row = rows[0]
        similar = [item for item in row["similar"] if item.get("name")]
        similar.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        resources = [item for item in row["resources"] if item.get("id")]
        return {
            "concept": {key: _maybe_json(value) for key, value in dict(row["concept"]).items()},
            "prerequisites": sorted(row["prerequisites"]),
            "similar": similar[:similar_limit],
            "resources": resources,
        }

    def prerequisite_subgraph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        node_rows = self._run("MATCH (c:Concept) RETURN properties(c) AS props")
        for row in node_rows:
            props = {key: _maybe_json(value) for key, value in dict(row["props"]).items()}
            node_id = props.pop("id", None)
            if node_id:
                graph.add_node(node_id, **props)
        edge_rows = self._run(
            """
            MATCH (pre:Concept)-[r:PREREQUISITE_OF]->(dep:Concept)
            RETURN pre.id AS source, dep.id AS target, properties(r) AS props
            """
        )
        for row in edge_rows:
            props = dict(row["props"])
            props["relation"] = "prerequisite"
            graph.add_edge(row["source"], row["target"], **props)
        return graph

    def get_ancestors(self, node: str) -> list[str]:
        graph = self.prerequisite_subgraph()
        if node not in graph:
            return []
        return sorted(nx.ancestors(graph, node))

    def get_descendants(self, node: str) -> list[str]:
        graph = self.prerequisite_subgraph()
        if node not in graph:
            return []
        return sorted(nx.descendants(graph, node))

    def get_topological_learning_order(self, targets: list[str]) -> list[str]:
        graph = self.prerequisite_subgraph()
        required_nodes: set[str] = set()
        for target in targets:
            if target in graph:
                required_nodes.add(target)
                required_nodes.update(nx.ancestors(graph, target))
        if not required_nodes:
            return []
        subgraph = graph.subgraph(required_nodes).copy()
        return list(nx.topological_sort(subgraph))
