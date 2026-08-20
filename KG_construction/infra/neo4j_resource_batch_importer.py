from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import RUN_DIR
from infra.neo4j_importer import import_graph


def _run_status(run_dir: Path) -> dict[str, Any]:
    graph_path = run_dir / "knowledge_graph.json"
    pdfs = sorted(path for path in run_dir.glob("*.pdf") if path.is_file())
    reasons = []
    if not graph_path.exists():
        reasons.append("missing_knowledge_graph")
    if len(pdfs) == 0:
        reasons.append("missing_pdf")
    elif len(pdfs) > 1:
        reasons.append("multiple_pdfs")
    return {
        "run_dir": str(run_dir),
        "name": run_dir.name,
        "graph_path": str(graph_path) if graph_path.exists() else None,
        "pdf_count": len(pdfs),
        "pdf_path": str(pdfs[0]) if len(pdfs) == 1 else None,
        "eligible": not reasons,
        "skip_reasons": reasons,
    }


def discover_runs(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        raise FileNotFoundError(f"runs_dir does not exist: {runs_dir}")
    statuses = []
    for path in sorted((item for item in runs_dir.rglob("*") if item.is_dir()), key=lambda item: str(item)):
        if path.name == "logs":
            continue
        has_direct_run_files = (path / "knowledge_graph.json").exists() or any(path.glob("*.pdf"))
        has_nested_run = any(child.name == "knowledge_graph.json" for child in path.rglob("knowledge_graph.json"))
        if has_direct_run_files:
            statuses.append(_run_status(path))
        elif not has_nested_run and path.parent == runs_dir:
            statuses.append(_run_status(path))
    return statuses


def import_resources_batch(runs_dir: Path, dry_run: bool = False, fail_on_skip: bool = False) -> dict[str, Any]:
    run_statuses = discover_runs(runs_dir)
    processed = []
    skipped = []
    totals = {
        "concept_import_attempts": 0,
        "prerequisite_edges": 0,
        "similarity_edges": 0,
        "resources": 0,
        "has_resource_edges": 0,
        "skipped_edges": 0,
    }

    for status in run_statuses:
        if not status["eligible"]:
            skipped.append(status)
            continue
        stats = import_graph(Path(status["graph_path"]), dry_run=dry_run, auto_resource=True)
        item = {**status, "stats": stats}
        processed.append(item)
        totals["concept_import_attempts"] += int(stats.get("concepts", 0))
        totals["prerequisite_edges"] += int(stats.get("prerequisite_edges", 0))
        totals["similarity_edges"] += int(stats.get("similarity_edges", 0))
        totals["resources"] += int(stats.get("resources", 0))
        totals["has_resource_edges"] += int(stats.get("has_resource_edges", 0))
        totals["skipped_edges"] += int(stats.get("skipped_edges", 0))

    passed = not (fail_on_skip and skipped)
    return {
        "runs_dir": str(runs_dir),
        "dry_run": dry_run,
        "fail_on_skip": fail_on_skip,
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "totals": totals,
        "processed": processed,
        "skipped": skipped,
        "passed": passed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch import run-level Resource/HAS_RESOURCE mappings into Neo4j.")
    parser.add_argument("--runs-dir", default=str(RUN_DIR), help="Directory containing run subdirectories")
    parser.add_argument("--dry-run", action="store_true", help="Inspect eligible runs without connecting to Neo4j")
    parser.add_argument("--fail-on-skip", action="store_true", help="Exit non-zero when any run is skipped")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_resources_batch(
        runs_dir=Path(args.runs_dir).resolve(),
        dry_run=args.dry_run,
        fail_on_skip=args.fail_on_skip,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
