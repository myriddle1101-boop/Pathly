from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import GLOBAL_KG_JSON
from infra.difficulty_calibration import calibrate_graph
from infra.node_details_audit import audit_calibrated_node_details


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reproducibility_check(graph_path: Path = GLOBAL_KG_JSON) -> dict[str, Any]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    audit = audit_calibrated_node_details(graph_path)
    first = calibrate_graph(graph_path)["graph"]
    second = calibrate_graph(graph_path)["graph"]
    first_hash = _stable_hash(first)
    second_hash = _stable_hash(second)
    relation_counts = {}
    for edge in graph.get("edges", []):
        relation = edge.get("relation", "unknown")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    passed = first_hash == second_hash
    return {
        "graph_path": str(graph_path),
        "status": "success" if passed else "failed",
        "passed": passed,
        "concept_count": len([node for node in graph.get("nodes", []) if node.get("id")]),
        "edge_count": len(graph.get("edges", [])),
        "relation_counts": relation_counts,
        "node_details_field_coverage": audit["field_coverage"],
        "difficulty_field": audit["difficulty_field"],
        "difficulty_distribution": audit["difficulty_distribution"],
        "calibrated_difficulty_hash_first": first_hash,
        "calibrated_difficulty_hash_second": second_hash,
        "calibration_deterministic": passed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reproducibility checks for graph counts and deterministic calibration.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge graph JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = reproducibility_check(Path(args.graph).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
