from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import networkx as nx

from infra.config import GLOBAL_KG_JSON


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if (stripped.startswith("[") and stripped.endswith("]")) or (
        stripped.startswith("{") and stripped.endswith("}")
    ):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


@dataclass
class TopicMatch:
    name: str
    score: float
    reason: str


class KGRepository:
    def __init__(self, graph: nx.DiGraph, source_path: Path):
        self.graph = graph
        self.source_path = source_path

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "KGRepository":
        graph_path = Path(path) if path else GLOBAL_KG_JSON
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph = cls._build_graph(data)
        return cls(graph=graph, source_path=graph_path)

    @staticmethod
    def _build_graph(data: dict) -> nx.DiGraph:
        graph = nx.DiGraph()
        for node in data.get("nodes", []):
            node_id = node.get("id")
            if not node_id:
                continue
            attrs = {k: _maybe_json(v) for k, v in node.items() if k != "id"}
            graph.add_node(node_id, **attrs)
        for edge in data.get("edges", []):
            source = edge.get("from")
            target = edge.get("to")
            if not source or not target:
                continue
            attrs = {k: _maybe_json(v) for k, v in edge.items() if k not in {"from", "to"}}
            graph.add_edge(source, target, **attrs)
        return graph

    def node_names(self) -> list[str]:
        return sorted(self.graph.nodes())

    def topic_text(self, name: str) -> str:
        topic = self.get_topic(name) or {"id": name}
        description = str(topic.get("description", ""))
        return f"{topic['id']}. {description}".strip()

    def topic_texts(self) -> list[str]:
        return [self.topic_text(name) for name in self.node_names()]

    def get_topic(self, name: str) -> dict[str, Any] | None:
        if name in self.graph.nodes:
            attrs = dict(self.graph.nodes[name])
            attrs["id"] = name
            return attrs
        for existing in self.graph.nodes:
            if existing.lower() == name.lower():
                attrs = dict(self.graph.nodes[existing])
                attrs["id"] = existing
                return attrs
        return None

    def search_topics(self, query: str, limit: int = 5) -> list[TopicMatch]:
        query_norm = query.strip().lower()
        matches: list[TopicMatch] = []
        if not query_norm:
            return matches

        for name, attrs in self.graph.nodes(data=True):
            description = str(attrs.get("description", ""))
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
        if node not in self.graph:
            return []
        prerequisites = []
        for predecessor in self.graph.predecessors(node):
            edge = self.graph.get_edge_data(predecessor, node, default={})
            if edge.get("relation") == "prerequisite":
                prerequisites.append(predecessor)
        return sorted(prerequisites)

    def get_dependents(self, node: str) -> list[str]:
        if node not in self.graph:
            return []
        dependents = []
        for successor in self.graph.successors(node):
            edge = self.graph.get_edge_data(node, successor, default={})
            if edge.get("relation") == "prerequisite":
                dependents.append(successor)
        return sorted(dependents)

    def get_similar(self, node: str, limit: int = 5) -> list[dict[str, Any]]:
        neighbors: list[dict[str, Any]] = []
        for source, target, edge in self.graph.edges(data=True):
            if edge.get("relation") != "similarity":
                continue
            if source == node:
                neighbors.append({"name": target, "score": float(edge.get("score", edge.get("similarity", 0.0)))})
            elif target == node:
                neighbors.append({"name": source, "score": float(edge.get("score", edge.get("similarity", 0.0)))})
        neighbors.sort(key=lambda item: item["score"], reverse=True)
        return neighbors[:limit]

    def _difficulty(self, node: str) -> float:
        attrs = self.get_topic(node) or {}
        value = attrs.get("difficulty_level", 3)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 3.0
        return 3.0

    def _resource_difficulty(self, resource_node: str) -> float:
        difficulties = []
        for predecessor in self.graph.predecessors(resource_node):
            edge = self.graph.get_edge_data(predecessor, resource_node, default={})
            if edge.get("relation") == "has_resource":
                difficulties.append(self._difficulty(predecessor))
        if not difficulties:
            return 3.0
        return round(sum(difficulties) / len(difficulties), 4)

    def get_concept_context(self, node: str, similar_limit: int = 5) -> dict[str, Any]:
        topic = self.get_topic(node)
        resources = []
        if node in self.graph.nodes:
            for successor in self.graph.successors(node):
                edge = self.graph.get_edge_data(node, successor, default={})
                if edge.get("relation") == "has_resource":
                    resource = self.get_topic(successor) or {"id": successor}
                    resource["relevance"] = edge.get("relevance")
                    resource["resource_difficulty"] = self._resource_difficulty(successor)
                    resource["difficulty_source"] = "linked_concept_average"
                    resources.append(resource)
        return {
            "concept": topic,
            "prerequisites": self.get_prerequisites(node),
            "similar": self.get_similar(node, limit=similar_limit),
            "resources": resources,
        }

    def prerequisite_subgraph(self) -> nx.DiGraph:
        subgraph = nx.DiGraph()
        for node, attrs in self.graph.nodes(data=True):
            subgraph.add_node(node, **attrs)
        for source, target, edge in self.graph.edges(data=True):
            if edge.get("relation") == "prerequisite":
                subgraph.add_edge(source, target, **edge)
        return subgraph

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
