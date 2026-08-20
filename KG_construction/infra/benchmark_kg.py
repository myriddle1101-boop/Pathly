from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import GLOBAL_KG_JSON
from infra.node_details_audit import audit_calibrated_node_details


def benchmark_kg(graph_path: Path = GLOBAL_KG_JSON) -> dict[str, Any]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = [node for node in graph.get("nodes", []) if node.get("id")]
    ids = [node["id"] for node in nodes]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    edges = graph.get("edges", [])
    connected = set()
    relation_counts = Counter()
    for edge in edges:
        relation = edge.get("relation", "unknown")
        relation_counts[relation] += 1
        if edge.get("from"):
            connected.add(edge["from"])
        if edge.get("to"):
            connected.add(edge["to"])
    isolated = [concept_id for concept_id in ids if concept_id not in connected]
    audit = audit_calibrated_node_details(graph_path)
    return {
        "graph_path": str(graph_path),
        "status": "success",
        "structural_metrics": {
            "concept_count": len(ids),
            "edge_count": len(edges),
            "prerequisite_edges": relation_counts.get("prerequisite", 0),
            "similarity_edges": relation_counts.get("similarity", 0),
            "isolated_concept_count": len(isolated),
            "duplicate_concept_count": len(duplicates),
        },
        "node_details_metrics": {
            "field_coverage": audit["field_coverage"],
            "difficulty_distribution": audit["difficulty_distribution"],
            "difficulty_entropy": audit["difficulty_entropy"],
            "difficulty_concentration_ratio": audit["difficulty_concentration_ratio"],
            "warnings": audit["warnings"],
        },
        "planning_readiness": {
            "usable_difficulty_ratio": audit["field_coverage"].get("difficulty_level", 0.0),
            "estimated_time_ratio": audit["field_coverage"].get("estimated_learning_time", 0.0),
            "prerequisites_summary_ratio": audit["field_coverage"].get("prerequisites_summary", 0.0),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark KG structural and node-details readiness metrics.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge graph JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(benchmark_kg(Path(args.graph).resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
