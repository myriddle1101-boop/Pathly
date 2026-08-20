from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from infra.config import BASELINE_DIR, GLOBAL_DIR, HISTORY_JSON, PROJECT_DIR, RUN_DIR


BASELINE_NAME = "current_kg_baseline"
CORE_STAGE_FILES = {
    "stage1": "stage1_chunks.json",
    "stage2a": "stage2a_topics_hybrid.json",
    "stage2b": "stage2b_prerequisites.json",
    "stage2c": "stage2c_similarity_edges.json",
    "stage3": "stage3_topics_with_summary.json",
    "stage4_json": "knowledge_graph.json",
    "stage4_gexf": "knowledge_graph.gexf",
}
OPTIONAL_FILES = [
    "stage1_text_cleaned.txt",
    "kg_prerequisite.png",
    "kg_similarity.png",
]
GLOBAL_FILES = [
    "global_knowledge_graph.json",
    "processed_files.json",
    "upload_history.json",
]
PIPELINE_SCRIPTS = {
    "stage1": "stage1_adaptive_chunking.py",
    "stage2a": "stage2a_hybrid_keybert_llm.py",
    "stage2b": "stage2b_prerequisites_hybrid.py",
    "stage2c": "stage2c_similarity.py",
    "stage3": "stage3_node_summary_hybrid.py",
    "stage4": "stage4_build_and_visualize_kg.py",
}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _hash_file(path: Path) -> str:
    digest = sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(PROJECT_DIR)),
        "size_bytes": stat.st_size,
        "sha256": _hash_file(path),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def _load_history_rows() -> list[dict[str, Any]]:
    rows = _read_json(HISTORY_JSON, [])
    return rows if isinstance(rows, list) else []


def _parse_history_time(value: str | None) -> tuple[int, str]:
    if not value:
        return (0, "")
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return (int(dt.timestamp()), value)
    except ValueError:
        return (0, value)


def _latest_history_for_doc(doc_name: str, history_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    matched: list[dict[str, Any]] = []
    for row in history_rows:
        file_name = str(row.get("file_name", ""))
        row_doc_name = Path(file_name).stem if file_name else ""
        row_doc_dir = row.get("doc_dir")
        row_dir_name = Path(str(row_doc_dir)).name if row_doc_dir else ""
        if row_doc_name == doc_name or row_dir_name == doc_name:
            matched.append(row)
    if not matched:
        return None
    matched.sort(key=lambda row: _parse_history_time(row.get("time"))[0], reverse=True)
    return matched[0]


def _extract_count(path: Path, key: str | None = None, fallback_keys: list[str] | None = None) -> int | None:
    data = _read_json(path, None)
    if data is None:
        return None
    if key and isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, int):
            return value
    if fallback_keys and isinstance(data, dict):
        for fallback_key in fallback_keys:
            value = data.get(fallback_key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, int):
                return value
    if isinstance(data, list):
        return len(data)
    return None


def _evaluate_run(doc_dir: Path, history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pdf_files = sorted(doc_dir.glob("*.pdf"))
    pdf_path = pdf_files[0] if pdf_files else None
    available_files = sorted([item.name for item in doc_dir.iterdir() if item.is_file()])
    latest_history = _latest_history_for_doc(doc_dir.name, history_rows)

    stage_status = {stage: (doc_dir / file_name).exists() for stage, file_name in CORE_STAGE_FILES.items()}
    stage_status["stage4"] = stage_status["stage4_json"] and stage_status["stage4_gexf"]
    stage_status["kg_prerequisite_png"] = (doc_dir / "kg_prerequisite.png").exists()
    stage_status["kg_similarity_png"] = (doc_dir / "kg_similarity.png").exists()

    file_inventory: dict[str, dict[str, Any]] = {}
    for file_name in available_files:
        file_inventory[file_name] = _file_metadata(doc_dir / file_name)

    counts = {
        "chunks": _extract_count(doc_dir / "stage1_chunks.json"),
        "topics": _extract_count(doc_dir / "stage2a_topics_hybrid.json", "topics_count"),
        "prerequisites": _extract_count(doc_dir / "stage2b_prerequisites.json", "prerequisites"),
        "similarity_edges": _extract_count(
            doc_dir / "stage2c_similarity_edges.json",
            "similarity_count",
            ["similarity_edges"],
        ),
        "topics_with_summary": _extract_count(doc_dir / "stage3_topics_with_summary.json", "topics"),
    }
    graph_json = _read_json(doc_dir / "knowledge_graph.json", {})
    if isinstance(graph_json, dict):
        counts["graph_nodes"] = len(graph_json.get("nodes", []))
        counts["graph_edges"] = len(graph_json.get("edges", []))
    else:
        counts["graph_nodes"] = None
        counts["graph_edges"] = None

    completeness_score = sum(
        1 for stage_name in ["stage1", "stage2a", "stage2b", "stage2c", "stage3", "stage4"] if stage_status.get(stage_name)
    )

    return {
        "doc_name": doc_dir.name,
        "source_dir": str(doc_dir),
        "pdf_file": pdf_path.name if pdf_path else None,
        "pdf_path": str(pdf_path) if pdf_path else None,
        "pdf_sha256": _hash_file(pdf_path) if pdf_path else None,
        "latest_status": latest_history.get("status") if latest_history else "unknown",
        "latest_history_time": latest_history.get("time") if latest_history else None,
        "history_row": latest_history,
        "available_files": available_files,
        "stage_status": stage_status,
        "counts": counts,
        "is_complete_candidate": bool(pdf_path) and all(stage_status.get(name) for name in ["stage1", "stage2a", "stage2b", "stage2c", "stage3", "stage4"]),
        "completeness_score": completeness_score,
        "file_inventory": file_inventory,
    }


def _collect_run_inventory() -> list[dict[str, Any]]:
    history_rows = _load_history_rows()
    run_inventory: list[dict[str, Any]] = []
    if not RUN_DIR.exists():
        return run_inventory
    for doc_dir in sorted([path for path in RUN_DIR.iterdir() if path.is_dir()], key=lambda path: path.name.lower()):
        run_inventory.append(_evaluate_run(doc_dir, history_rows))
    return run_inventory


def _select_representative_runs(run_inventory: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    complete_runs = [run for run in run_inventory if run["is_complete_candidate"]]
    complete_runs.sort(
        key=lambda run: (
            _parse_history_time(run.get("latest_history_time"))[0],
            run.get("counts", {}).get("graph_nodes") or 0,
        ),
        reverse=True,
    )
    if complete_runs:
        return complete_runs[:limit]

    fallback_runs = sorted(
        run_inventory,
        key=lambda run: (
            run.get("completeness_score", 0),
            _parse_history_time(run.get("latest_history_time"))[0],
        ),
        reverse=True,
    )
    return fallback_runs[: max(1, min(limit, len(fallback_runs)))]


def _collect_global_inventory() -> dict[str, Any]:
    inventory: dict[str, Any] = {}
    for file_name in GLOBAL_FILES:
        path = GLOBAL_DIR / file_name
        inventory[file_name] = {
            "exists": path.exists(),
            "metadata": _file_metadata(path) if path.exists() else None,
        }
    graph_json = _read_json(GLOBAL_DIR / "global_knowledge_graph.json", {})
    if isinstance(graph_json, dict):
        inventory["global_graph_counts"] = {
            "nodes": len(graph_json.get("nodes", [])),
            "edges": len(graph_json.get("edges", [])),
        }
    else:
        inventory["global_graph_counts"] = {"nodes": None, "edges": None}
    return inventory


def _collect_dependency_snapshot() -> dict[str, Any]:
    requirements_path = PROJECT_DIR / "requirements.txt"
    requirements_txt = requirements_path.read_text(encoding="utf-8").splitlines() if requirements_path.exists() else []
    requirements = [
        line.strip()
        for line in requirements_txt
        if line.strip() and not line.strip().startswith("#")
    ]

    pip_freeze: list[str] = []
    freeze_error = None
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            pip_freeze = [line for line in result.stdout.splitlines() if line.strip()]
        else:
            freeze_error = result.stderr.strip() or f"pip freeze failed with code {result.returncode}"
    except OSError as exc:
        freeze_error = str(exc)

    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "requirements_path": str(requirements_path),
        "requirements": requirements,
        "pip_freeze": pip_freeze,
        "pip_freeze_error": freeze_error,
    }


def _reset_baseline_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {
        "source": str(src),
        "snapshot": str(dst),
        "restore_target": str(src),
        "sha256": _hash_file(dst),
    }


def _copy_global_snapshot(snapshot_root: Path) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for file_name in GLOBAL_FILES:
        src = GLOBAL_DIR / file_name
        if not src.exists():
            continue
        dst = snapshot_root / "global" / file_name
        copied.append(_copy_file(src, dst))
    return copied


def _copy_representative_runs(snapshot_root: Path, representative_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for run in representative_runs:
        src_dir = Path(run["source_dir"])
        dst_dir = snapshot_root / "runs" / run["doc_name"]
        dst_dir.mkdir(parents=True, exist_ok=True)
        for file_name in run["available_files"]:
            src = src_dir / file_name
            if src.is_file():
                copied.append(_copy_file(src, dst_dir / file_name))
    return copied


def _build_status_summary(run_inventory: list[dict[str, Any]], representative_runs: list[dict[str, Any]]) -> dict[str, Any]:
    complete_runs = [run for run in run_inventory if run["is_complete_candidate"]]
    partial_runs = [run for run in run_inventory if not run["is_complete_candidate"]]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_counts": {
            "total": len(run_inventory),
            "complete": len(complete_runs),
            "partial_or_incomplete": len(partial_runs),
        },
        "representative_selection_rule": "优先选择最近成功且具备 Stage1-Stage4 核心产物的运行目录，最多保留 3 份代表样本。",
        "representative_runs": [run["doc_name"] for run in representative_runs],
        "runs": run_inventory,
    }


def _build_restore_plan(snapshot_root: Path, representative_runs: list[dict[str, Any]]) -> dict[str, Any]:
    restore_actions: list[dict[str, Any]] = []

    for file_name in GLOBAL_FILES:
        snapshot_path = snapshot_root / "global" / file_name
        if snapshot_path.exists():
            restore_actions.append(
                {
                    "type": "copy_file",
                    "from_snapshot": str(snapshot_path),
                    "to_worktree": str(GLOBAL_DIR / file_name),
                    "purpose": "恢复全局知识图谱与处理历史",
                }
            )

    for run in representative_runs:
        doc_name = run["doc_name"]
        restore_actions.append(
            {
                "type": "replace_directory_contents",
                "from_snapshot": str(snapshot_root / "runs" / doc_name),
                "to_worktree": str(RUN_DIR / doc_name),
                "purpose": f"恢复代表样本 {doc_name} 的分阶段产物与输入 PDF",
            }
        )

    return {
        "baseline_dir": str(snapshot_root.parent),
        "restore_actions": restore_actions,
    }


def _build_reproduction_recipe(snapshot_root: Path, representative_runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not representative_runs:
        return {
            "pipeline_project_dir": str(PROJECT_DIR),
            "available": False,
            "reason": "当前没有可用的代表样本。",
        }

    primary = representative_runs[0]
    doc_name = primary["doc_name"]
    snapshot_run_dir = snapshot_root / "runs" / doc_name
    pdf_files = sorted(snapshot_run_dir.glob("*.pdf"))
    if not pdf_files:
        return {
            "pipeline_project_dir": str(PROJECT_DIR),
            "available": False,
            "reason": f"代表样本 {doc_name} 缺少 PDF，无法生成复现配方。",
        }

    sample_pdf = pdf_files[0]
    reproduced_output_dir = RUN_DIR / f"{doc_name}__reproduced"

    steps = [
        {
            "stage": "stage1",
            "script": str(PROJECT_DIR / PIPELINE_SCRIPTS["stage1"]),
            "cwd": str(PROJECT_DIR),
            "inputs": [str(sample_pdf), str(reproduced_output_dir / "stage1_chunks.json")],
            "expected_output_sha256": primary["file_inventory"].get("stage1_chunks.json", {}).get("sha256"),
        },
        {
            "stage": "stage2a",
            "script": str(PROJECT_DIR / PIPELINE_SCRIPTS["stage2a"]),
            "cwd": str(PROJECT_DIR),
            "inputs": [
                str(reproduced_output_dir / "stage1_chunks.json"),
                str(reproduced_output_dir / "stage2a_topics_hybrid.json"),
            ],
            "expected_output_sha256": primary["file_inventory"].get("stage2a_topics_hybrid.json", {}).get("sha256"),
        },
        {
            "stage": "stage2b",
            "script": str(PROJECT_DIR / PIPELINE_SCRIPTS["stage2b"]),
            "cwd": str(PROJECT_DIR),
            "inputs": [
                str(reproduced_output_dir / "stage2a_topics_hybrid.json"),
                str(reproduced_output_dir / "stage2b_prerequisites.json"),
            ],
            "expected_output_sha256": primary["file_inventory"].get("stage2b_prerequisites.json", {}).get("sha256"),
        },
        {
            "stage": "stage2c",
            "script": str(PROJECT_DIR / PIPELINE_SCRIPTS["stage2c"]),
            "cwd": str(PROJECT_DIR),
            "inputs": [
                str(reproduced_output_dir / "stage2a_topics_hybrid.json"),
                str(reproduced_output_dir / "stage2c_similarity_edges.json"),
            ],
            "expected_output_sha256": primary["file_inventory"].get("stage2c_similarity_edges.json", {}).get("sha256"),
        },
        {
            "stage": "stage3",
            "script": str(PROJECT_DIR / PIPELINE_SCRIPTS["stage3"]),
            "cwd": str(PROJECT_DIR),
            "inputs": [
                str(reproduced_output_dir / "stage2a_topics_hybrid.json"),
                str(reproduced_output_dir / "stage3_topics_with_summary.json"),
            ],
            "expected_output_sha256": primary["file_inventory"].get("stage3_topics_with_summary.json", {}).get("sha256"),
        },
        {
            "stage": "stage4",
            "script": str(PROJECT_DIR / PIPELINE_SCRIPTS["stage4"]),
            "cwd": str(reproduced_output_dir),
            "inputs": [
                str(reproduced_output_dir / "stage3_topics_with_summary.json"),
                str(reproduced_output_dir / "stage2b_prerequisites.json"),
                str(reproduced_output_dir / "stage2c_similarity_edges.json"),
            ],
            "expected_output_sha256": primary["file_inventory"].get("knowledge_graph.json", {}).get("sha256"),
        },
    ]

    return {
        "pipeline_project_dir": str(PROJECT_DIR),
        "available": True,
        "primary_representative_run": doc_name,
        "sample_pdf": str(sample_pdf),
        "reproduced_output_dir": str(reproduced_output_dir),
        "steps": steps,
    }


def freeze_current_baseline() -> Path:
    baseline_root = BASELINE_DIR / BASELINE_NAME
    snapshot_root = baseline_root / "snapshot"

    run_inventory = _collect_run_inventory()
    representative_runs = _select_representative_runs(run_inventory)
    global_inventory = _collect_global_inventory()
    dependency_snapshot = _collect_dependency_snapshot()

    _reset_baseline_dir(baseline_root)
    copied_globals = _copy_global_snapshot(snapshot_root)
    copied_runs = _copy_representative_runs(snapshot_root, representative_runs)

    status_summary = _build_status_summary(run_inventory, representative_runs)
    restore_plan = _build_restore_plan(snapshot_root, representative_runs)
    reproduction_recipe = _build_reproduction_recipe(snapshot_root, representative_runs)

    artifacts_index = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_root": str(baseline_root),
        "copied_global_files": copied_globals,
        "copied_run_files": copied_runs,
    }

    manifest = {
        "baseline_name": BASELINE_NAME,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(PROJECT_DIR),
        "baseline_dir": str(baseline_root),
        "mechanism_version": 1,
        "design_goal": "冻结当前已跑通的 KG baseline，保留依赖、代表样本、关键输出和状态说明，为后续升级提供可回滚、可复现的锚点。",
        "global_inventory": global_inventory,
        "representative_runs": [
            {
                "doc_name": run["doc_name"],
                "source_dir": run["source_dir"],
                "snapshot_dir": str(snapshot_root / "runs" / run["doc_name"]),
                "latest_status": run["latest_status"],
                "latest_history_time": run["latest_history_time"],
                "counts": run["counts"],
                "stage_status": run["stage_status"],
            }
            for run in representative_runs
        ],
        "stage_output_artifacts": [
            {"name": "baseline_manifest.json", "path": str(baseline_root / "baseline_manifest.json")},
            {"name": "dependencies.json", "path": str(baseline_root / "dependencies.json")},
            {"name": "run_status_summary.json", "path": str(baseline_root / "run_status_summary.json")},
            {"name": "artifacts_index.json", "path": str(baseline_root / "artifacts_index.json")},
            {"name": "restore_plan.json", "path": str(baseline_root / "restore_plan.json")},
            {"name": "reproduction_recipe.json", "path": str(baseline_root / "reproduction_recipe.json")},
        ],
        "rollback_proof": {
            "snapshot_contains_global_state": bool(copied_globals),
            "snapshot_contains_representative_runs": [run["doc_name"] for run in representative_runs],
            "restore_plan_path": str(baseline_root / "restore_plan.json"),
        },
        "reproduction_proof": {
            "recipe_path": str(baseline_root / "reproduction_recipe.json"),
            "primary_sample": reproduction_recipe.get("primary_representative_run"),
            "verification_mode": "按阶段输出 sha256 与 baseline 产物比对",
        },
    }

    _write_json(baseline_root / "baseline_manifest.json", manifest)
    _write_json(baseline_root / "dependencies.json", dependency_snapshot)
    _write_json(baseline_root / "run_status_summary.json", status_summary)
    _write_json(baseline_root / "artifacts_index.json", artifacts_index)
    _write_json(baseline_root / "restore_plan.json", restore_plan)
    _write_json(baseline_root / "reproduction_recipe.json", reproduction_recipe)

    return baseline_root
