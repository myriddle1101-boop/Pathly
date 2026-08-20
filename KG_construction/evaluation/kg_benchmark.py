from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import PROJECT_DIR


STAGE_SCRIPTS = [
    ("stage1", PROJECT_DIR / "stage1_adaptive_chunking.py"),
    ("stage2a", PROJECT_DIR / "stage2a_hybrid_keybert_llm.py"),
    ("stage2b", PROJECT_DIR / "stage2b_prerequisites_hybrid.py"),
    ("stage2c", PROJECT_DIR / "stage2c_similarity.py"),
    ("stage3", PROJECT_DIR / "stage3_node_summary_hybrid.py"),
    ("stage4", PROJECT_DIR / "stage4_build_and_visualize_kg.py"),
]


def ask_path(prompt: str) -> str:
    return input(prompt + "\n> ").strip().strip('"').strip("'")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_stage_summary_csv(path: Path, stages: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "stage",
                "script",
                "duration_seconds",
                "return_code",
                "success",
                "log_path",
            ],
        )
        writer.writeheader()
        for stage in stages:
            writer.writerow(
                {
                    "stage": stage["stage"],
                    "script": stage["script"],
                    "duration_seconds": stage["duration_seconds"],
                    "return_code": stage["return_code"],
                    "success": stage["success"],
                    "log_path": stage["log_path"],
                }
            )


def run_stage(script_path: Path, inputs: list[str], cwd: Path) -> tuple[float, int, str]:
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input="\n".join(inputs) + "\n",
        text=True,
        capture_output=True,
        cwd=str(cwd),
    )
    duration = time.perf_counter() - start
    return duration, result.returncode, result.stdout + "\n" + result.stderr


def run_benchmark(
    *,
    pdf_path: str | Path,
    output_dir: str | Path,
    sample_name: str = "default_sample",
    run_mode: str = "full_pipeline_cli",
    stage_names: list[str] | None = None,
) -> dict[str, Any]:
    pdf_path = Path(pdf_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stage1_out = output_dir / "stage1_chunks.json"
    stage2a_out = output_dir / "stage2a_topics_hybrid.json"
    stage2b_out = output_dir / "stage2b_prerequisites.json"
    stage2c_out = output_dir / "stage2c_similarity_edges.json"
    stage3_out = output_dir / "stage3_topics_with_summary.json"

    stage_inputs = {
        "stage1": [str(pdf_path), str(stage1_out)],
        "stage2a": [str(stage1_out), str(stage2a_out)],
        "stage2b": [str(stage2a_out), str(stage2b_out)],
        "stage2c": [str(stage2a_out), str(stage2c_out)],
        "stage3": [str(stage2a_out), str(stage3_out)],
        "stage4": [str(stage3_out), str(stage2b_out), str(stage2c_out)],
    }

    selected_stage_names = stage_names or [stage_name for stage_name, _ in STAGE_SCRIPTS]
    selected_stage_scripts = [(stage_name, script_path) for stage_name, script_path in STAGE_SCRIPTS if stage_name in selected_stage_names]

    artifacts: dict[str, str] = {"benchmark_json": str(output_dir / "kg_benchmark.json"), "benchmark_summary_csv": str(output_dir / "kg_benchmark_summary.csv")}
    if "stage1" in selected_stage_names:
        artifacts["stage1_chunks"] = str(stage1_out)
    if "stage2a" in selected_stage_names:
        artifacts["stage2a_topics"] = str(stage2a_out)
    if "stage2b" in selected_stage_names:
        artifacts["stage2b_prerequisites"] = str(stage2b_out)
    if "stage2c" in selected_stage_names:
        artifacts["stage2c_similarity_edges"] = str(stage2c_out)
    if "stage3" in selected_stage_names:
        artifacts["stage3_topics_with_summary"] = str(stage3_out)

    benchmark = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sample_name": sample_name,
        "run_mode": run_mode,
        "selected_stages": selected_stage_names,
        "pdf_path": str(pdf_path),
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "stages": [],
    }
    for stage_name, script_path in selected_stage_scripts:
        duration, return_code, log = run_stage(
            script_path=script_path,
            inputs=stage_inputs[stage_name],
            cwd=output_dir if stage_name == "stage4" else PROJECT_DIR,
        )
        log_path = output_dir / f"{stage_name}_benchmark.log"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log)

        benchmark["stages"].append(
            {
                "stage": stage_name,
                "script": str(script_path),
                "duration_seconds": round(duration, 3),
                "return_code": return_code,
                "success": return_code == 0,
                "log_path": str(log_path),
            }
        )
        if return_code != 0:
            break

    benchmark["success"] = all(item["success"] for item in benchmark["stages"]) and len(benchmark["stages"]) == len(
        selected_stage_scripts
    )
    benchmark["completed_stage_count"] = len(benchmark["stages"])
    benchmark["total_seconds"] = round(sum(item["duration_seconds"] for item in benchmark["stages"]), 3)

    benchmark_json_path = output_dir / "kg_benchmark.json"
    benchmark_csv_path = output_dir / "kg_benchmark_summary.csv"
    _write_json(benchmark_json_path, benchmark)
    _write_stage_summary_csv(benchmark_csv_path, benchmark["stages"])
    _write_json(benchmark_json_path, benchmark)
    return benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行固定输入的 KG benchmark。")
    parser.add_argument("--pdf-path", help="待评测 PDF 绝对路径")
    parser.add_argument("--output-dir", help="benchmark 输出目录")
    parser.add_argument("--sample-name", default="default_sample", help="样本名称")
    parser.add_argument("--run-mode", default="full_pipeline_cli", help="运行方式标识")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf_path) if args.pdf_path else Path(ask_path("请输入 PDF 完整路径"))
    output_dir = Path(args.output_dir) if args.output_dir else Path(ask_path("请输入 benchmark 输出目录"))
    benchmark = run_benchmark(
        pdf_path=pdf_path,
        output_dir=output_dir,
        sample_name=args.sample_name,
        run_mode=args.run_mode,
    )
    print(f"[OK] benchmark 结果已保存: {benchmark['artifacts']['benchmark_json']}")


if __name__ == "__main__":
    main()
