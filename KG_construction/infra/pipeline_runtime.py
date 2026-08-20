from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json_safe(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_json_record(path: Path, record: dict[str, Any]) -> None:
    payload = load_json_safe(path, {"records": []})
    records = payload.get("records", [])
    if not isinstance(records, list):
        records = []
    records.append(record)
    payload["records"] = records
    payload["updated_at"] = now_iso()
    save_json(path, payload)


def slugify_doc_name(name: str) -> str:
    lowered = name.strip().lower()
    lowered = re.sub(r"[^0-9a-zA-Z._-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-._")
    return lowered or "document"


def build_doc_dir(run_root: Path, file_name: str, digest: str) -> Path:
    doc_name = slugify_doc_name(Path(file_name).stem)
    return run_root / doc_name / digest[:12]


def stage_text_log_path(doc_dir: Path, stage_name: str) -> Path:
    return doc_dir / "logs" / f"{stage_name}.log"


def stage_json_log_path(doc_dir: Path, stage_name: str) -> Path:
    return doc_dir / "logs" / f"{stage_name}.json"


def default_stage_entry(doc_dir: Path, stage_name: str) -> dict[str, Any]:
    return {
        "status": "pending",
        "attempts": 0,
        "started_at": None,
        "ended_at": None,
        "duration_seconds": None,
        "return_code": None,
        "reused_on_resume": False,
        "input_paths": [],
        "output_paths": [],
        "log_text_path": str(stage_text_log_path(doc_dir, stage_name)),
        "log_json_path": str(stage_json_log_path(doc_dir, stage_name)),
        "validation": {
            "inputs_ok": False,
            "outputs_ok": False,
            "missing_inputs": [],
            "missing_outputs": [],
            "details": [],
        },
        "stdout_tail": "",
        "stderr_tail": "",
    }


def ensure_manifest(
    doc_dir: Path,
    file_name: str,
    digest: str,
    pdf_path: Path,
    pdf_size_bytes: int,
    stage_names: list[str],
) -> tuple[dict[str, Any], Path, Path, Path]:
    manifest_path = doc_dir / "manifest.json"
    run_log_path = doc_dir / "run_log.json"
    recovery_state_path = doc_dir / "recovery_state.json"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "logs").mkdir(parents=True, exist_ok=True)

    manifest = load_json_safe(manifest_path, {})
    if not isinstance(manifest, dict):
        manifest = {}

    run_id = f"{slugify_doc_name(Path(file_name).stem)}-{digest[:12]}"
    manifest.setdefault("schema_version", "1.0")
    manifest.setdefault("run_id", run_id)
    manifest.setdefault("created_at", now_iso())
    manifest["updated_at"] = now_iso()
    manifest["status"] = manifest.get("status", "pending")
    manifest["run_attempts"] = int(manifest.get("run_attempts", 0))
    manifest["document"] = {
        "file_name": file_name,
        "doc_name": Path(file_name).stem,
        "sha256": digest,
        "pdf_path": str(pdf_path),
        "pdf_size_bytes": pdf_size_bytes,
    }
    manifest["artifacts"] = {
        "output_dir": str(doc_dir),
        "manifest_path": str(manifest_path),
        "run_log_path": str(run_log_path),
        "recovery_state_path": str(recovery_state_path),
        "log_dir": str(doc_dir / "logs"),
    }
    summary = manifest.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    summary.setdefault("completed_stages", [])
    summary.setdefault("failed_stage", None)
    summary.setdefault("next_resume_stage", stage_names[0] if stage_names else None)
    summary.setdefault("last_resume_from_stage", None)
    summary.setdefault("duration_seconds", None)
    manifest["summary"] = summary

    stages = manifest.get("stages", {})
    if not isinstance(stages, dict):
        stages = {}
    for stage_name in stage_names:
        stage_entry = stages.get(stage_name, {})
        if not isinstance(stage_entry, dict):
            stage_entry = {}
        merged = default_stage_entry(doc_dir, stage_name)
        merged.update(stage_entry)
        merged["log_text_path"] = str(stage_text_log_path(doc_dir, stage_name))
        merged["log_json_path"] = str(stage_json_log_path(doc_dir, stage_name))
        stages[stage_name] = merged
    manifest["stages"] = stages

    save_json(manifest_path, manifest)
    if not run_log_path.exists():
        save_json(run_log_path, {"run_id": run_id, "events": [], "updated_at": now_iso()})
    if not recovery_state_path.exists():
        save_json(
            recovery_state_path,
            {
                "run_id": run_id,
                "can_resume": True,
                "last_failed_stage": None,
                "next_resume_stage": stage_names[0] if stage_names else None,
                "completed_stages": [],
                "updated_at": now_iso(),
            },
        )
    return manifest, manifest_path, run_log_path, recovery_state_path


def save_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = now_iso()
    save_json(manifest_path, manifest)


def append_run_event(
    run_log_path: Path,
    *,
    level: str,
    message: str,
    stage: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    payload = load_json_safe(run_log_path, {"events": []})
    events = payload.get("events", [])
    if not isinstance(events, list):
        events = []
    events.append(
        {
            "time": now_iso(),
            "level": level,
            "stage": stage,
            "message": message,
            "data": data or {},
        }
    )
    payload["events"] = events
    payload["updated_at"] = now_iso()
    save_json(run_log_path, payload)


def update_recovery_state(
    recovery_state_path: Path,
    *,
    run_id: str,
    completed_stages: list[str],
    next_resume_stage: str | None,
    failed_stage: str | None,
    can_resume: bool,
) -> None:
    save_json(
        recovery_state_path,
        {
            "run_id": run_id,
            "can_resume": can_resume,
            "last_failed_stage": failed_stage,
            "next_resume_stage": next_resume_stage,
            "completed_stages": completed_stages,
            "updated_at": now_iso(),
        },
    )
