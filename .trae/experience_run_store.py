"""Auditable end-to-end run records for fresh walkthroughs and evaluations."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperienceRunStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS experience_runs(
                run_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, plan_id TEXT NOT NULL,
                day INTEGER NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_experience_runs_owner ON experience_runs(user_id,plan_id,day,updated_at DESC)")

    def save(self, *, user_id: str, plan_id: str, day: int, status: str, payload: dict[str, Any]) -> dict[str, Any]:
        stamp = _now()
        run_id = str(payload.get("run_id") or f"run-{uuid.uuid4()}")
        record = {**payload, "run_id": run_id, "user_id": user_id, "plan_id": plan_id, "day": int(day), "status": status, "timestamp": payload.get("timestamp") or stamp}
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO experience_runs VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,payload_json=excluded.payload_json,updated_at=excluded.updated_at", (run_id, user_id, plan_id, int(day), status, json.dumps(record, ensure_ascii=False), stamp, stamp))
        return record

    def latest(self, user_id: str, plan_id: str, day: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT payload_json FROM experience_runs WHERE user_id=? AND plan_id=? AND day=? ORDER BY updated_at DESC LIMIT 1", (user_id, plan_id, int(day))).fetchone()
        return json.loads(row[0]) if row else None

    def list_runs(self, *, user_id: str | None = None, run_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Return immutable-looking run artifacts for local audit/export views."""
        safe_limit = max(1, min(int(limit), 500))
        clauses: list[str] = []
        values: list[Any] = []
        if user_id:
            clauses.append("user_id=?")
            values.append(user_id)
        query = "SELECT payload_json FROM experience_runs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        values.append(safe_limit)
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(query, values).fetchall()
        records = [json.loads(row[0]) for row in rows]
        if run_type:
            records = [record for record in records if record.get("run_type") == run_type]
        return records


def build_experience_run(*, user_id: str, plan_record: dict[str, Any], day: int, lecture: dict[str, Any], success: bool, error_reason: str | None = None) -> dict[str, Any]:
    metadata = lecture.get("generation_metadata") or {}
    sections = lecture.get("lecture_sections") or []
    source_refs = []
    for section in sections:
        for page in section.get("source_pages") or []:
            source_refs.append({key: page.get(key) for key in ("resource_id", "document_id", "page_number", "link_id")})
    return {
        "run_id": f"run-{uuid.uuid4()}",
        "learner_state": "controlled_evaluation" if user_id.startswith("demo-") else "fresh_or_anonymous_walkthrough",
        "profile_snapshot": plan_record.get("profile_snapshot") or {},
        "goal": plan_record.get("goal_text") or (plan_record.get("plan") or {}).get("goal_text"),
        "selected_system_version": "v4",
        "versions": {
            "kg": ((plan_record.get("plan") or {}).get("verified_goal_scope") or {}).get("source"),
            "source": metadata.get("source_link_version"),
            "asset": metadata.get("asset_manifest_version"),
            "prompt": metadata.get("prompt_version"),
            "generator": metadata.get("generator_version"),
            "treatment": metadata.get("treatment_version"),
            "model": metadata.get("content_model"),
            "temperature": metadata.get("temperature", 0.2),
        },
        "plan": plan_record.get("plan") or {},
        "core_content_output": sections,
        "source_evidence": source_refs,
        "cache_status": metadata.get("cache_status"),
        "success": bool(success),
        "error_reason": error_reason,
    }
