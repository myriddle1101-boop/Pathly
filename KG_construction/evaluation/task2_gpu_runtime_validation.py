from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import BENCHMARK_DIR, PROJECT_DIR, ensure_data_dirs
from infra.device_manager import get_device_info
from infra.rag_ingestion import ingest_stage1_chunks_with_report
from stage2a_hybrid_keybert_llm import run_stage2a
from stage2c_similarity import run_stage2c

DEFAULT_SAMPLE_DIR = PROJECT_DIR / "web_data" / "runs" / "Crime"
DEFAULT_STAGE1_PATH = DEFAULT_SAMPLE_DIR / "stage1_chunks.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _collect_nvidia_smi() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return {
            "command": "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader",
            "return_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0,
        }
    except Exception as exc:
        return {
            "command": "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader",
            "return_code": None,
            "stdout": "",
            "stderr": f"{exc.__class__.__name__}: {exc}",
            "success": False,
        }


def _stage_summary(result: dict[str, Any]) -> dict[str, Any]:
    benchmark = result.get("benchmark", {})
    device_info = benchmark.get("device_info", {})
    return {
        "duration_seconds": benchmark.get("duration_seconds"),
        "requested_device": device_info.get("requested_device"),
        "selected_device": device_info.get("selected_device"),
        "fallback_applied": device_info.get("fallback_applied"),
        "fallback_reason": device_info.get("fallback_reason"),
        "batch_size": benchmark.get("batch_size"),
        "output_path": result.get("_output_path"),
    }


def _run_suite(stage1_path: Path, output_root: Path, requested_device: str, run_label: str) -> dict[str, Any]:
    run_dir = output_root / run_label
    run_dir.mkdir(parents=True, exist_ok=True)

    stage2a_out = run_dir / "stage2a_topics_hybrid.json"
    stage2c_out = run_dir / "stage2c_similarity_edges.json"
    rag_out = run_dir / "rag_ingestion_report.json"

    stage2a_result = run_stage2a(str(stage1_path), str(stage2a_out), force_device=requested_device)
    stage2a_result["_output_path"] = str(stage2a_out)

    stage2c_result = run_stage2c(str(stage2a_out), str(stage2c_out), force_device=requested_device)
    stage2c_result["_output_path"] = str(stage2c_out)

    rag_start = time.perf_counter()
    rag_result = ingest_stage1_chunks_with_report(
        str(stage1_path),
        collection_name=f"kg_chunks_task2_{run_label}_{int(time.time())}",
        force_device=requested_device,
    )
    rag_duration = round(time.perf_counter() - rag_start, 4)
    _write_json(rag_out, rag_result)

    return {
        "run_label": run_label,
        "requested_device": requested_device,
        "stage2a": _stage_summary(stage2a_result),
        "stage2c": _stage_summary(stage2c_result),
        "rag": {
            "duration_seconds": rag_duration,
            "requested_device": rag_result.get("device_info", {}).get("requested_device"),
            "selected_device": rag_result.get("device_info", {}).get("selected_device"),
            "fallback_applied": rag_result.get("device_info", {}).get("fallback_applied"),
            "fallback_reason": rag_result.get("device_info", {}).get("fallback_reason"),
            "batch_size": rag_result.get("batch_size"),
            "output_path": str(rag_out),
            "inserted": rag_result.get("inserted"),
        },
    }


def _build_log_text(
    *,
    artifact_dir: Path,
    stage1_path: Path,
    device_validation: dict[str, Any],
    cpu_run: dict[str, Any],
    gpu_attempt_run: dict[str, Any],
) -> str:
    lines = [
        "Task 2 GPU Runtime Validation",
        f"artifact_dir: {artifact_dir}",
        f"stage1_input: {stage1_path}",
        "",
        "[Environment]",
        json.dumps(device_validation, ensure_ascii=False, indent=2),
        "",
        "[CPU Run]",
        json.dumps(cpu_run, ensure_ascii=False, indent=2),
        "",
        "[CUDA Requested Run]",
        json.dumps(gpu_attempt_run, ensure_ascii=False, indent=2),
    ]
    return "\n".join(lines)


def main() -> None:
    ensure_data_dirs()
    if not DEFAULT_STAGE1_PATH.exists():
        raise FileNotFoundError(f"找不到默认验证输入: {DEFAULT_STAGE1_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = BENCHMARK_DIR / "task2_gpu_priority" / timestamp
    artifact_dir.mkdir(parents=True, exist_ok=True)

    device_validation = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(PROJECT_DIR),
        "sample_dir": str(DEFAULT_SAMPLE_DIR),
        "torch_probe_cpu": get_device_info(force_device="cpu"),
        "torch_probe_cuda_preferred": get_device_info(force_device="cuda"),
        "nvidia_smi": _collect_nvidia_smi(),
    }
    _write_json(artifact_dir / "device_validation.json", device_validation)

    cpu_run = _run_suite(DEFAULT_STAGE1_PATH, artifact_dir, "cpu", "cpu")
    gpu_attempt_run = _run_suite(DEFAULT_STAGE1_PATH, artifact_dir, "cuda", "cuda_requested")

    gpu_selected_everywhere = all(
        section.get("selected_device") == "cuda"
        for section in [gpu_attempt_run["stage2a"], gpu_attempt_run["stage2c"], gpu_attempt_run["rag"]]
    )
    benchmark_comparison = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "artifact_dir": str(artifact_dir),
        "sample_input": str(DEFAULT_STAGE1_PATH),
        "true_gpu_verified": gpu_selected_everywhere,
        "cpu_run": cpu_run,
        "gpu_attempt_run": gpu_attempt_run,
    }
    _write_json(artifact_dir / "benchmark_comparison.json", benchmark_comparison)

    log_text = _build_log_text(
        artifact_dir=artifact_dir,
        stage1_path=DEFAULT_STAGE1_PATH,
        device_validation=device_validation,
        cpu_run=cpu_run,
        gpu_attempt_run=gpu_attempt_run,
    )
    with open(artifact_dir / "gpu_validation.log", "w", encoding="utf-8") as f:
        f.write(log_text)

    print(f"[OK] Task 2 验证产物已输出到: {artifact_dir}")


if __name__ == "__main__":
    main()
