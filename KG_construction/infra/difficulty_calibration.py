from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import GLOBAL_DIR, GLOBAL_KG_JSON


def _load_graph(graph_path: Path) -> dict[str, Any]:
    return json.loads(graph_path.read_text(encoding="utf-8"))


def _raw_difficulty(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 2
    return parsed if parsed in {1, 2, 3} else 2


def _estimated_hours(value: Any) -> float:
    text = str(value or "").lower()
    numbers = []
    current = ""
    for char in text:
        if char.isdigit() or char == ".":
            current += char
        elif current:
            try:
                numbers.append(float(current))
            except ValueError:
                pass
            current = ""
    if current:
        try:
            numbers.append(float(current))
        except ValueError:
            pass
    if not numbers:
        return 1.0
    return sum(numbers) / len(numbers)


def _prerequisite_depth(target: str, reverse_edges: dict[str, list[str]]) -> int:
    max_depth = 0
    queue = deque([(target, 0)])
    seen = {target}
    while queue:
        node, depth = queue.popleft()
        max_depth = max(max_depth, depth)
        for pre in reverse_edges.get(node, []):
            if pre not in seen:
                seen.add(pre)
                queue.append((pre, depth + 1))
    return max_depth


def calibrate_graph(graph_path: Path = GLOBAL_KG_JSON) -> dict[str, Any]:
    graph = _load_graph(graph_path)
    prereq_incoming: dict[str, list[str]] = defaultdict(list)
    prereq_outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        if edge.get("relation") != "prerequisite":
            continue
        source = edge.get("from")
        target = edge.get("to")
        if source and target:
            prereq_incoming[target].append(source)
            prereq_outgoing[source].append(target)

    updated = []
    changed = 0
    for node in graph.get("nodes", []):
        concept_id = node.get("id")
        if not concept_id:
            updated.append(node)
            continue
        raw = _raw_difficulty(node.get("difficulty_level"))
        incoming = len(prereq_incoming.get(concept_id, []))
        outgoing = len(prereq_outgoing.get(concept_id, []))
        depth = _prerequisite_depth(concept_id, prereq_incoming)
        hours = _estimated_hours(node.get("estimated_learning_time"))

        calibrated = raw
        reasons = [f"raw={raw}", f"prerequisite_depth={depth}", f"incoming_prerequisites={incoming}", f"outgoing_dependents={outgoing}", f"estimated_hours={hours:.2f}"]
        if incoming == 0 and depth == 0 and raw <= 2 and hours <= 1.5:
            calibrated = 1
            reasons.append("foundation concept with little prerequisite burden")
        if depth >= 2 or incoming >= 2 or hours >= 2.0:
            calibrated = max(calibrated, 2)
            reasons.append("non-trivial prerequisite or time signal")
        if depth >= 3 or incoming >= 3 or (incoming >= 2 and outgoing >= 2):
            calibrated = 3
            reasons.append("graph structure indicates advanced concept")

        calibrated = max(1, min(3, calibrated))
        if calibrated != raw:
            changed += 1

        copied = dict(node)
        copied["raw_difficulty_level"] = raw
        copied["calibrated_difficulty_level"] = calibrated
        copied["difficulty_calibration_reason"] = "; ".join(reasons)
        copied["difficulty_source"] = copied.get("difficulty_source", "llm_node_summary")
        copied["difficulty_confidence"] = copied.get("difficulty_confidence", 0.75)
        copied["estimated_time_source"] = copied.get("estimated_time_source", "llm_node_summary")
        copied["details_generated_by"] = copied.get("details_generated_by", "stage3_node_summary_hybrid")
        copied["details_generated_at"] = copied.get("details_generated_at", "")
        updated.append(copied)

    result_graph = {"nodes": updated, "edges": graph.get("edges", [])}
    return {
        "graph_path": str(graph_path),
        "status": "success",
        "total_concepts": sum(1 for node in updated if node.get("id")),
        "updated_concepts": changed,
        "unchanged_concepts": sum(1 for node in updated if node.get("id")) - changed,
        "graph": result_graph,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic calibrated difficulty fields.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge graph JSON")
    parser.add_argument(
        "--output",
        default=str(GLOBAL_DIR / "global_knowledge_graph_calibrated.json"),
        help="Output path for calibrated graph JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = calibrate_graph(Path(args.graph).resolve())
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result["graph"], ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: value for key, value in result.items() if key != "graph"}
    summary["output"] = str(output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
