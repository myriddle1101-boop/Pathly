from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import GLOBAL_KG_JSON
from infra.difficulty_calibration import calibrate_graph


AUDIT_FIELDS = [
    "description",
    "difficulty_level",
    "estimated_learning_time",
    "target_audience",
    "prerequisites_summary",
    "key_sub_concepts",
    "common_misconceptions",
    "practical_applications",
]


def _load_graph(graph_path: Path) -> dict[str, Any]:
    return json.loads(graph_path.read_text(encoding="utf-8"))


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _difficulty(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed in {1, 2, 3} else None


def _entropy(distribution: dict[str, float]) -> float:
    value = 0.0
    for ratio in distribution.values():
        if ratio > 0:
            value -= ratio * math.log2(ratio)
    return round(value, 4)


def _audit_graph(graph: dict[str, Any], *, graph_path: Path, difficulty_field: str) -> dict[str, Any]:
    nodes = [node for node in graph.get("nodes", []) if node.get("id")]
    total = len(nodes)
    warnings: list[str] = []

    missing_counts = {
        field: sum(1 for node in nodes if not _present(node.get(field)))
        for field in AUDIT_FIELDS
    }
    field_coverage = {
        field: round((total - missing_counts[field]) / total, 4) if total else 0.0
        for field in AUDIT_FIELDS
    }

    difficulty_values = [_difficulty(node.get(difficulty_field)) for node in nodes]
    invalid_difficulty_count = sum(1 for value in difficulty_values if value is None)
    counter = Counter(str(value) for value in difficulty_values if value is not None)
    difficulty_distribution = {
        level: round(counter.get(level, 0) / total, 4) if total else 0.0
        for level in ["1", "2", "3"]
    }
    concentration_level = max(difficulty_distribution, key=lambda key: difficulty_distribution[key]) if total else None
    concentration_ratio = difficulty_distribution.get(concentration_level, 0.0) if concentration_level else 0.0
    if difficulty_distribution.get("2", 0.0) > 0.75:
        warnings.append("difficulty_level is overly concentrated at level 2")
    if invalid_difficulty_count:
        warnings.append("invalid difficulty_level values detected")

    return {
        "graph_path": str(graph_path),
        "difficulty_field": difficulty_field,
        "total_concepts": total,
        "field_coverage": field_coverage,
        "missing_description_count": missing_counts["description"],
        "missing_difficulty_count": missing_counts["difficulty_level"],
        "missing_estimated_time_count": missing_counts["estimated_learning_time"],
        "missing_prerequisites_summary_count": missing_counts["prerequisites_summary"],
        "missing_common_misconceptions_count": missing_counts["common_misconceptions"],
        "missing_practical_applications_count": missing_counts["practical_applications"],
        "invalid_difficulty_count": invalid_difficulty_count,
        "difficulty_distribution": difficulty_distribution,
        "difficulty_entropy": _entropy(difficulty_distribution),
        "difficulty_concentration_level": concentration_level,
        "difficulty_concentration_ratio": concentration_ratio,
        "difficulty_concentration_warning": difficulty_distribution.get("2", 0.0) > 0.75,
        "llm_generated_field_coverage": {
            "key_sub_concepts": field_coverage["key_sub_concepts"],
            "common_misconceptions": field_coverage["common_misconceptions"],
            "practical_applications": field_coverage["practical_applications"],
        },
        "warnings": warnings,
        "status": "warning" if warnings else "success",
    }


def audit_node_details(graph_path: Path = GLOBAL_KG_JSON, *, difficulty_field: str = "difficulty_level") -> dict[str, Any]:
    graph = _load_graph(graph_path)
    return _audit_graph(graph, graph_path=graph_path, difficulty_field=difficulty_field)


def audit_calibrated_node_details(graph_path: Path = GLOBAL_KG_JSON) -> dict[str, Any]:
    calibration = calibrate_graph(graph_path)
    audit = _audit_graph(
        calibration["graph"],
        graph_path=graph_path,
        difficulty_field="calibrated_difficulty_level",
    )
    audit["raw_difficulty_field"] = "difficulty_level"
    audit["calibration_status"] = calibration["status"]
    audit["updated_concepts"] = calibration["updated_concepts"]
    audit["unchanged_concepts"] = calibration["unchanged_concepts"]
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Concept node details for planning/content readiness.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge graph JSON")
    parser.add_argument(
        "--difficulty-field",
        default="difficulty_level",
        choices=["difficulty_level", "calibrated_difficulty_level"],
        help="Node field used for difficulty distribution audit",
    )
    parser.add_argument(
        "--calibrated",
        action="store_true",
        help="Run deterministic calibration in memory and audit calibrated_difficulty_level",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph_path = Path(args.graph).resolve()
    result = audit_calibrated_node_details(graph_path) if args.calibrated else audit_node_details(
        graph_path,
        difficulty_field=args.difficulty_field,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
