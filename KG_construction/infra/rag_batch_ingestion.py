from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import RUN_DIR
from infra.neo4j_importer import _resolve_auto_resource_path, _resource_params
from infra.rag_ingestion import build_rag_rows, ingest_stage1_chunks_with_report


def discover_stage1_files(runs_dir: Path) -> list[Path]:
    return sorted(path for path in runs_dir.rglob("stage1_chunks.json") if path.is_file())


def inspect_stage1(stage1_path: Path) -> dict[str, Any]:
    graph_path = stage1_path.parent / "knowledge_graph.json"
    resource_path = _resolve_auto_resource_path(graph_path)
    reason = None
    if not graph_path.exists():
        reason = "missing_knowledge_graph_json"
    elif resource_path is None:
        reason = "missing_or_ambiguous_pdf_resource"

    rows: list[dict[str, Any]] = []
    error = None
    if reason is None:
        try:
            rows = build_rag_rows(stage1_path)
        except Exception as exc:
            error = str(exc)
            reason = "failed_to_build_rows"

    resource = _resource_params(resource_path) if resource_path else None
    return {
        "stage1_path": str(stage1_path),
        "graph_path": str(graph_path),
        "eligible": reason is None,
        "skip_reason": reason,
        "error": error,
        "resource": resource,
        "row_count": len(rows),
        "has_resource_id": bool(resource and resource.get("id")),
    }


def run_batch(
    runs_dir: Path,
    *,
    write: bool = False,
    collection_name: str = "kg_chunks",
    force_device: str | None = None,
) -> dict[str, Any]:
    inspected = [inspect_stage1(path) for path in discover_stage1_files(runs_dir)]
    eligible = [item for item in inspected if item["eligible"]]
    skipped = [item for item in inspected if not item["eligible"]]
    result: dict[str, Any] = {
        "mode": "write" if write else "dry_run",
        "runs_dir": str(runs_dir),
        "collection_name": collection_name,
        "stage1_files_seen": len(inspected),
        "eligible_count": len(eligible),
        "skipped_count": len(skipped),
        "total_candidate_rows": sum(int(item["row_count"]) for item in eligible),
        "eligible": eligible,
        "skipped": skipped,
        "reports": [],
    }
    if not write:
        return result

    reports = []
    for item in eligible:
        report = ingest_stage1_chunks_with_report(
            item["stage1_path"],
            collection_name=collection_name,
            force_device=force_device,
        )
        reports.append(report)
    result["reports"] = reports
    result["inserted_total"] = sum(int(report.get("inserted", 0)) for report in reports)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch ingest stage1 chunks into ChromaDB.")
    parser.add_argument("--runs-dir", default=str(RUN_DIR), help="Path to web_data/runs")
    parser.add_argument("--collection", default="kg_chunks", help="ChromaDB collection name")
    parser.add_argument("--write", action="store_true", help="Write chunks to ChromaDB. Omit for dry-run.")
    parser.add_argument("--force-device", default=None, choices=[None, "cpu", "cuda"], help="Embedding device override")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_batch(
        Path(args.runs_dir).resolve(),
        write=args.write,
        collection_name=args.collection,
        force_device=args.force_device,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
