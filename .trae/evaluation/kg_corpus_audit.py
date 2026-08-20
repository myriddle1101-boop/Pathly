"""Read-only structural and provenance audit over all persisted KG pipeline runs.

This is deliberately a corpus-health audit, not an accuracy evaluation.
Semantic correctness is reported only through separately annotated gold data.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "KG_construction" / "web_data" / "runs"
DEFAULT_OUTPUT = ROOT / "evaluation" / "results" / "kg_corpus_audit.json"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _normal(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").split())


def _topics(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    return list(data.get("topics") or [])


def _edges(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    return list(data.get("prerequisites") or [])


def _has_cycle(adjacency: dict[str, set[str]]) -> bool:
    visiting, visited = set(), set()
    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in adjacency.get(node, set()):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False
    return any(visit(node) for node in list(adjacency))


def audit_runs(runs_dir: Path = RUNS) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    global_names: Counter[str] = Counter()
    manifests = sorted(runs_dir.glob("**/manifest.json"))
    for manifest_path in manifests:
        run_dir = manifest_path.parent
        manifest = _read(manifest_path) or {}
        topic_data = _read(run_dir / "stage2a_topics_hybrid.json")
        prereq_data = _read(run_dir / "stage2b_prerequisites.json")
        summary_data = _read(run_dir / "stage3_topics_with_summary.json")
        topics = _topics(summary_data) or _topics(topic_data)
        names = [_normal(item.get("name")) for item in topics if _normal(item.get("name"))]
        global_names.update(set(names))
        name_set = set(names)
        edges = _edges(prereq_data)
        edge_pairs = [(_normal(edge.get("from")), _normal(edge.get("to"))) for edge in edges]
        valid_pairs = [(a, b) for a, b in edge_pairs if a and b]
        dangling = [(a, b) for a, b in valid_pairs if a not in name_set or b not in name_set]
        adjacency: dict[str, set[str]] = defaultdict(set)
        for source, target in valid_pairs:
            adjacency[source].add(target)
        document = manifest.get("document") or {}
        source_path = Path(str(document.get("pdf_path") or ""))
        summaries = [item.get("summary") for item in topics]
        rows.append({
            "run_id": str(run_dir.relative_to(runs_dir)).replace("\\", "/"),
            "manifest_present": bool(manifest),
            "source_path_present": bool(document.get("pdf_path")),
            "source_file_exists": source_path.exists() if str(source_path) else False,
            "source_hash_present": bool(document.get("sha256")),
            "topics": len(names),
            "blank_topic_names": len(topics) - len(names),
            "duplicate_topic_names": len(names) - len(set(names)),
            "topics_with_description": sum(bool(str(item.get("description") or "").strip()) for item in topics),
            "topics_with_summary": sum(isinstance(item, dict) and bool(item) for item in summaries),
            "prerequisite_edges": len(edges),
            "malformed_edges": len(edges) - len(valid_pairs),
            "dangling_prerequisite_edges": len(dangling),
            "self_loops": sum(a == b for a, b in valid_pairs),
            "duplicate_prerequisite_edges": len(valid_pairs) - len(set(valid_pairs)),
            "has_prerequisite_cycle": _has_cycle(adjacency),
            "stage2a_present": topic_data is not None,
            "stage2b_present": prereq_data is not None,
            "stage3_present": summary_data is not None,
        })
    totals = {
        "run_count": len(rows),
        "runs_with_topics": sum(row["topics"] > 0 for row in rows),
        "topic_instances": sum(row["topics"] for row in rows),
        "prerequisite_edges": sum(row["prerequisite_edges"] for row in rows),
        "runs_with_missing_source_file": sum(not row["source_file_exists"] for row in rows),
        "runs_with_dangling_edges": sum(row["dangling_prerequisite_edges"] > 0 for row in rows),
        "runs_with_cycles": sum(bool(row["has_prerequisite_cycle"]) for row in rows),
        "runs_with_duplicate_topics": sum(row["duplicate_topic_names"] > 0 for row in rows),
        "cross_run_reused_topic_names": sum(count > 1 for count in global_names.values()),
    }
    return {
        "audit_version": "kg-corpus-health-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "persisted pipeline run artifacts, not a direct semantic audit of live Neo4j",
        "interpretation": "Structural/provenance health only. Do not infer topic or prerequisite correctness from these counts.",
        "totals": totals,
        "runs": rows,
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = output.with_suffix(".csv")
    fields = list(result["runs"][0]) if result["runs"] else ["run_id"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(result["runs"])
    summary_path = output.with_name("kg_corpus_audit_summary.csv")
    with summary_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows({"metric": key, "value": value} for key, value in result["totals"].items())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = audit_runs(args.runs_dir)
    write_outputs(result, args.output)
    print(json.dumps(result["totals"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
