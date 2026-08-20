from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluation.kg_benchmark import run_benchmark
from evaluation.kg_quality_eval import evaluate_quality
from infra.config import BENCHMARK_DIR, PROJECT_DIR, ensure_data_dirs


DEFAULT_CONFIG_PATH = PROJECT_DIR / "evaluation" / "task4_experiment_manifest.json"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _resolve_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (PROJECT_DIR / path).resolve()


def _write_table_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_benchmark_table_rows(benchmark: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for stage in benchmark["stages"]:
        rows.append(
            {
                "sample_name": benchmark["sample_name"],
                "dimension": "benchmark",
                "metric_group": stage["stage"],
                "metric_name": "duration_seconds",
                "metric_value": stage["duration_seconds"],
                "unit": "seconds",
                "success": stage["success"],
                "source_file": benchmark["artifacts"]["benchmark_json"],
            }
        )
    rows.append(
        {
            "sample_name": benchmark["sample_name"],
            "dimension": "benchmark",
            "metric_group": "pipeline",
            "metric_name": "total_seconds",
            "metric_value": benchmark["total_seconds"],
            "unit": "seconds",
            "success": benchmark["success"],
            "source_file": benchmark["artifacts"]["benchmark_json"],
        }
    )
    return rows


def _build_quality_table_rows(quality: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    metrics_by_group = {
        "topics": quality["topic_metrics"],
        "prerequisites": quality["prerequisite_metrics"],
        "similarity": quality["similarity_metrics"],
    }
    for metric_group, metric_values in metrics_by_group.items():
        for metric_name in ["precision", "recall", "f1", "tp", "fp", "fn", "predicted", "gold"]:
            rows.append(
                {
                    "sample_name": quality["sample_name"],
                    "dimension": "quality_eval",
                    "metric_group": metric_group,
                    "metric_name": metric_name,
                    "metric_value": metric_values[metric_name],
                    "unit": "ratio" if metric_name in {"precision", "recall", "f1"} else "count",
                    "success": True,
                    "source_file": quality["artifacts"]["quality_json"],
                }
            )
    return rows


def _create_artifact_index(
    *,
    config_path: Path,
    benchmark: dict[str, Any],
    quality: dict[str, Any],
    benchmark_table_csv: Path,
    quality_table_csv: Path,
    experiment_table_csv: Path,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "experiment_id": "task4_evaluable_release_paper_ready_v1",
        "config_path": str(config_path),
        "benchmark": {
            "sample_name": benchmark["sample_name"],
            "artifact_dir": benchmark["output_dir"],
            "result_json": benchmark["artifacts"]["benchmark_json"],
            "summary_csv": benchmark["artifacts"]["benchmark_summary_csv"],
            "stage_outputs": benchmark["artifacts"],
        },
        "quality_eval": {
            "sample_name": quality["sample_name"],
            "result_json": quality["artifacts"]["quality_json"],
            "summary_csv": quality["artifacts"]["quality_summary_csv"],
            "gold_inputs": quality["inputs"],
        },
        "paper_tables": {
            "benchmark_table_csv": str(benchmark_table_csv),
            "quality_table_csv": str(quality_table_csv),
            "experiment_table_draft_csv": str(experiment_table_csv),
        },
    }


def run_task4(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    ensure_data_dirs()
    config = _load_json(config_path)

    benchmark_cfg = config["benchmark"]
    quality_cfg = config["quality_eval"]
    tables_cfg = config["paper_tables"]

    benchmark = run_benchmark(
        pdf_path=_resolve_path(benchmark_cfg["pdf_path"]),
        output_dir=_resolve_path(benchmark_cfg["output_dir"]),
        sample_name=benchmark_cfg["sample_name"],
        run_mode=benchmark_cfg["run_mode"],
        stage_names=benchmark_cfg.get("stage_names"),
    )

    quality = evaluate_quality(
        predicted_topics_path=_resolve_path(quality_cfg["predicted_topics_path"]),
        predicted_prereq_path=_resolve_path(quality_cfg["predicted_prereq_path"]),
        predicted_similarity_path=_resolve_path(quality_cfg["predicted_similarity_path"]),
        gold_topics_path=_resolve_path(quality_cfg["gold_topics_path"]),
        gold_prereq_path=_resolve_path(quality_cfg["gold_prereq_path"]),
        gold_similarity_path=_resolve_path(quality_cfg["gold_similarity_path"]),
        output_path=_resolve_path(quality_cfg["output_path"]),
        sample_name=quality_cfg["sample_name"],
        metric_protocol=quality_cfg["metric_protocol"],
    )

    benchmark_table_rows = _build_benchmark_table_rows(benchmark)
    quality_table_rows = _build_quality_table_rows(quality)
    experiment_table_rows = benchmark_table_rows + quality_table_rows

    benchmark_table_csv = _resolve_path(tables_cfg["benchmark_table_csv"])
    quality_table_csv = _resolve_path(tables_cfg["quality_table_csv"])
    experiment_table_csv = _resolve_path(tables_cfg["experiment_table_draft_csv"])

    common_fields = [
        "sample_name",
        "dimension",
        "metric_group",
        "metric_name",
        "metric_value",
        "unit",
        "success",
        "source_file",
    ]
    _write_table_csv(benchmark_table_csv, common_fields, benchmark_table_rows)
    _write_table_csv(quality_table_csv, common_fields, quality_table_rows)
    _write_table_csv(experiment_table_csv, common_fields, experiment_table_rows)

    artifact_index = _create_artifact_index(
        config_path=config_path,
        benchmark=benchmark,
        quality=quality,
        benchmark_table_csv=benchmark_table_csv,
        quality_table_csv=quality_table_csv,
        experiment_table_csv=experiment_table_csv,
    )
    artifact_index_path = _resolve_path(config["artifact_index_path"])
    _write_json(artifact_index_path, artifact_index)

    run_report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(PROJECT_DIR),
        "benchmark_root": str(BENCHMARK_DIR),
        "config_path": str(config_path),
        "artifact_index_path": str(artifact_index_path),
        "benchmark_result": benchmark["artifacts"]["benchmark_json"],
        "quality_result": quality["artifacts"]["quality_json"],
        "experiment_table_draft_csv": str(experiment_table_csv),
    }
    _write_json(_resolve_path(tables_cfg["output_dir"]) / "task4_run_report.json", run_report)
    return run_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="执行 Task 4 的固定 benchmark 与质量评测。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="实验配置 JSON 路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_task4(config_path=Path(args.config).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
