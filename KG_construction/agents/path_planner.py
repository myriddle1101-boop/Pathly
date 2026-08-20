from __future__ import annotations

from typing import Any

import networkx as nx

from infra.kg_repository import KGRepository


class PathPlanner:
    def __init__(self, repository: KGRepository):
        self.repository = repository
        self.graph = self._make_acyclic(repository.prerequisite_subgraph())

    def plan(
        self,
        targets: list[str],
        known_topics: list[str] | None = None,
        algorithm: str = "astar",
    ) -> dict[str, Any]:
        known = {topic for topic in (known_topics or []) if topic in self.graph.nodes}
        target_paths = {}
        required_nodes = set()
        for target in targets:
            if target not in self.graph.nodes:
                continue
            path = self._best_path_to_target(target, known, algorithm)
            target_paths[target] = path
            required_nodes.update(path)

        required_nodes -= known
        if not required_nodes:
            ordered_topics = []
        else:
            ordered_topics = list(nx.topological_sort(self.graph.subgraph(required_nodes).copy()))

        return {
            "algorithm": algorithm,
            "known_topics": sorted(known),
            "ordered_topics": ordered_topics,
            "prerequisite_paths": target_paths,
            "covered_prerequisites": {
                topic: self.repository.get_prerequisites(topic)
                for topic in ordered_topics
            },
        }

    def _best_path_to_target(self, target: str, known_topics: set[str], algorithm: str) -> list[str]:
        candidate_starts = self._candidate_start_nodes(target, known_topics)
        best_path = [target]
        best_len = float("inf")
        for start in candidate_starts:
            try:
                if algorithm == "bfs":
                    path = nx.shortest_path(self.graph, start, target)
                else:
                    path = nx.astar_path(
                        self.graph,
                        start,
                        target,
                        heuristic=lambda current, goal: self._heuristic(current, goal),
                    )
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if len(path) < best_len:
                best_len = len(path)
                best_path = path
        return [node for node in best_path if node not in known_topics]

    def _candidate_start_nodes(self, target: str, known_topics: set[str]) -> list[str]:
        roots = [node for node in self.graph.nodes if self.graph.in_degree(node) == 0]
        candidates = []
        for node in sorted(known_topics) + roots:
            if node == target:
                candidates.append(node)
            elif node in self.graph and nx.has_path(self.graph, node, target):
                candidates.append(node)
        return candidates or [target]

    def _heuristic(self, current: str, goal: str) -> float:
        current_difficulty = self._difficulty(current)
        goal_difficulty = self._difficulty(goal)
        gap = max(goal_difficulty - current_difficulty, 0)
        return gap * 0.1

    def _difficulty(self, node: str) -> int:
        attrs = self.repository.get_topic(node) or {}
        value = attrs.get("difficulty_level", 3)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return 3

    def _make_acyclic(self, graph: nx.DiGraph) -> nx.DiGraph:
        dag = graph.copy()
        while True:
            try:
                cycle = next(nx.simple_cycles(dag))
            except StopIteration:
                break
            if len(cycle) < 2:
                break
            edges = list(zip(cycle, cycle[1:] + [cycle[0]]))
            edge_to_remove = max(edges, key=lambda pair: self._difficulty(pair[0]) - self._difficulty(pair[1]))
            if dag.has_edge(*edge_to_remove):
                dag.remove_edge(*edge_to_remove)
        return dag
