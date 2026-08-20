from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.benchmark_kg import benchmark_kg
from infra import config as infra_config
from infra.difficulty_calibration import calibrate_graph
from infra.neo4j_verify import verify_graph
from infra.node_details_audit import audit_calibrated_node_details
from infra.planning_backend_compare import compare_planning_backends
from infra.profile_verify import verify_profiles
from infra.rag_verify import verify_rag
from infra.reproducibility_check import reproducibility_check


GLOBAL_DIR = infra_config.GLOBAL_DIR
GLOBAL_KG_JSON = infra_config.GLOBAL_KG_JSON
MANIFEST_DIR = getattr(infra_config, "MANIFEST_DIR", infra_config.DATA_DIR / "manifests")
ensure_data_dirs = infra_config.ensure_data_dirs


def _now_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _stage_result(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = datetime.now().isoformat(timespec="seconds")
    try:
        result = fn()
        status = result.get("status") or ("success" if result.get("passed", True) else "failed")
        if result.get("warnings"):
            status = "warning"
        return {
            "status": status,
            "started_at": started,
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "result": result,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "started_at": started,
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "error": str(exc),
        }


def _write_manifest(manifest: dict[str, Any], output_path: Path | None = None) -> Path:
    ensure_data_dirs()
    path = output_path or MANIFEST_DIR / f"{manifest['run_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_harness(
    *,
    stage: str,
    graph_path: Path = GLOBAL_KG_JSON,
    manifest_path: Path | None = None,
    live_neo4j: bool = False,
    rag_collection: str = "kg_chunks",
    rag_resource_id: str | None = None,
    planning_goal: str = "learn neural networks",
    planning_target_concepts: list[str] | None = None,
) -> dict[str, Any]:
    ensure_data_dirs()
    run_id = f"harness_{_now_id()}"
    stages: dict[str, dict[str, Any]] = {}

    def audit_stage() -> dict[str, Any]:
        return audit_calibrated_node_details(graph_path)

    def calibrate_stage() -> dict[str, Any]:
        output = GLOBAL_DIR / "global_knowledge_graph_calibrated.json"
        result = calibrate_graph(graph_path)
        output.write_text(json.dumps(result["graph"], ensure_ascii=False, indent=2), encoding="utf-8")
        summary = {key: value for key, value in result.items() if key != "graph"}
        summary["output"] = str(output)
        return summary

    def neo4j_stage() -> dict[str, Any]:
        return verify_graph(
            graph_path,
            live=live_neo4j,
            include_resources=live_neo4j,
            include_topics=live_neo4j,
        )

    def rag_stage() -> dict[str, Any]:
        result = verify_rag(
            collection_name=rag_collection,
            resource_id=rag_resource_id,
            min_chunks=1,
        )
        result["status"] = "success" if result.get("passed") else "failed"
        return result

    def planning_stage() -> dict[str, Any]:
        result = compare_planning_backends(
            goal_text=planning_goal,
            graph_path=graph_path,
            target_concepts=planning_target_concepts or ["Neural Networks"],
            days=7,
            daily_minutes=60,
        )
        result["status"] = "success" if result.get("passed") else "failed"
        return result

    selectable = {
        "audit": audit_stage,
        "calibrate": calibrate_stage,
        "kg_benchmark": lambda: benchmark_kg(graph_path),
        "profile": verify_profiles,
        "rag": rag_stage,
        "planning": planning_stage,
        "reproducibility": lambda: reproducibility_check(graph_path),
        "neo4j": neo4j_stage,
    }
    order = ["audit", "calibrate", "kg_benchmark", "profile", "rag", "reproducibility", "neo4j"]
    selected = order if stage == "all" else [stage]
    for item in selected:
        if item not in selectable:
            raise ValueError(f"Unsupported harness stage: {item}")
        stages[item] = _stage_result(item, selectable[item])

    status = "success"
    if any(entry["status"] == "failed" for entry in stages.values()):
        status = "failed"
    elif any(entry["status"] == "warning" for entry in stages.values()):
        status = "warning"

    manifest = {
        "run_id": run_id,
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "graph_path": str(graph_path),
        "live_neo4j": live_neo4j,
        "rag_collection": rag_collection,
        "rag_resource_id": rag_resource_id,
        "planning_goal": planning_goal,
        "planning_target_concepts": planning_target_concepts or ["Neural Networks"],
        "stages": stages,
    }
    output = _write_manifest(manifest, manifest_path)
    manifest["manifest_path"] = str(output)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime harness for reproducible KG quality checks.")
    parser.add_argument(
        "--stage",
        default="all",
        choices=["audit", "calibrate", "kg_benchmark", "profile", "rag", "reproducibility", "neo4j", "all"],
        help="Harness stage to run",
    )
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge graph JSON")
    parser.add_argument("--manifest", default=None, help="Optional manifest output path")
    parser.add_argument("--live-neo4j", action="store_true", help="Connect to Neo4j during neo4j/all stage")
    parser.add_argument("--rag-collection", default="kg_chunks", help="ChromaDB collection for rag stage")
    parser.add_argument("--rag-resource-id", default=None, help="Optional Resource.id for rag stage")
    parser.add_argument("--planning-goal", default="learn neural networks", help="Goal text for planning stage")
    parser.add_argument(
        "--planning-target-concept",
        action="append",
        default=[],
        help="Stable target concept for planning stage. Can be passed multiple times.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_harness(
        stage=args.stage,
        graph_path=Path(args.graph).resolve(),
        manifest_path=Path(args.manifest).resolve() if args.manifest else None,
        live_neo4j=args.live_neo4j,
        rag_collection=args.rag_collection,
        rag_resource_id=args.rag_resource_id,
        planning_goal=args.planning_goal,
        planning_target_concepts=args.planning_target_concept or None,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
