from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.agent_context_smoke import run_agent_context_smoke
from infra.config import GLOBAL_KG_JSON
from infra.neo4j_diagnostics import run_diagnostics
from infra.neo4j_importer import import_graph
from infra.neo4j_verify import verify_graph
from infra.planning_backend_compare import compare_planning_backends


def _gate(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        result = fn()
        return {
            "name": name,
            "passed": bool(result.get("passed")),
            "result": result,
            "error": result.get("error"),
        }
    except Exception as exc:
        return {
            "name": name,
            "passed": False,
            "result": None,
            "error": str(exc),
        }


def run_acceptance(
    graph_path: Path,
    concept_id: str,
    goal_text: str,
    target_concepts: list[str],
    days: int = 7,
    daily_minutes: int = 60,
    import_first: bool = False,
) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []

    if import_first:
        gates.append(_gate("import_graph", lambda: _import_gate(graph_path)))

    gates.append(_gate("diagnostics_live", lambda: run_diagnostics(graph_path, live=True)))
    gates.append(_gate("verify_live_counts_and_boundaries", lambda: verify_graph(graph_path, live=True)))
    gates.append(
        _gate(
            "planning_backend_comparison",
            lambda: compare_planning_backends(
                goal_text=goal_text,
                graph_path=graph_path,
                target_concepts=target_concepts,
                days=days,
                daily_minutes=daily_minutes,
            ),
        )
    )
    gates.append(
        _gate(
            "content_adaptation_context_smoke",
            lambda: run_agent_context_smoke(
                concept_id=concept_id,
                backend="neo4j",
                graph_path=graph_path,
            ),
        )
    )

    return {
        "graph_path": str(graph_path),
        "concept_id": concept_id,
        "goal_text": goal_text,
        "target_concepts": target_concepts,
        "import_first": import_first,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates),
    }


def _import_gate(graph_path: Path) -> dict[str, Any]:
    stats = import_graph(graph_path, dry_run=False)
    return {
        "passed": True,
        "stats": stats,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Neo4j migration acceptance gates.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge_graph.json")
    parser.add_argument("--concept", required=True, help="Concept id for Content/Adaptation smoke")
    parser.add_argument("--goal", required=True, help="Goal text for Planning comparison")
    parser.add_argument(
        "--target-concept",
        action="append",
        required=True,
        help="Target concept for deterministic Planning comparison. Can be passed multiple times.",
    )
    parser.add_argument("--days", type=int, default=7, help="Requested days for Planning comparison")
    parser.add_argument("--daily-minutes", type=int, default=60, help="Daily minutes for Planning comparison")
    parser.add_argument(
        "--import-first",
        action="store_true",
        help="Import the graph before validation. This writes to Neo4j; omit for read-only validation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_acceptance(
        graph_path=Path(args.graph).resolve(),
        concept_id=args.concept,
        goal_text=args.goal,
        target_concepts=args.target_concept,
        days=args.days,
        daily_minutes=args.daily_minutes,
        import_first=args.import_first,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
