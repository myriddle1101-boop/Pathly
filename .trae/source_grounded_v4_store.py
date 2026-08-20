"""Isolated persistence and compatibility baseline for Source-Grounded Lecture v4."""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

V4_CONTRACT_VERSION = "source-grounded-lecture-v4"
V4_GENERATOR_VERSION = "source-grounded-v4-s4-lecture-v1"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def create_v4_baseline(
    v3_lecture: dict[str, Any], source_links: list[dict[str, Any]] | None = None,
    source_link_version: str = "unknown", golden_path: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lecture = copy.deepcopy(v3_lecture)
    lecture["contract_version"] = V4_CONTRACT_VERSION
    metadata = dict(lecture.get("generation_metadata") or {})
    metadata.update({"content_contract_version": V4_CONTRACT_VERSION,
        "generator_version": V4_GENERATOR_VERSION,
        "baseline_source": "full-lecture-v3-read-only-snapshot",
        "source_link_version": source_link_version, "source_link_status": "indexed" if source_links is not None else "not_indexed", "isolated_from_v3": True})
    lecture["generation_metadata"] = metadata
    lecture["v4_status"] = "baseline"
    lecture["source_links"] = copy.deepcopy(source_links or [])
    lecture["golden_path_sources"] = copy.deepcopy(golden_path or [])
    return lecture

class SourceGroundedLectureV4Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.migrate()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS source_grounded_lecture_v4(
                user_id TEXT NOT NULL, plan_id TEXT NOT NULL, day INTEGER NOT NULL,
                payload_json TEXT NOT NULL, generator_version TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, plan_id, day))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS source_grounded_lecture_v4_progress(
                user_id TEXT NOT NULL, plan_id TEXT NOT NULL, day INTEGER NOT NULL,
                section_id TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, plan_id, day, section_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS source_grounded_lecture_v4_exercise_answers(
                user_id TEXT NOT NULL, plan_id TEXT NOT NULL, day INTEGER NOT NULL,
                section_id TEXT NOT NULL, question_id TEXT NOT NULL, answer_id TEXT NOT NULL,
                correct INTEGER NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, plan_id, day, section_id, question_id))""")

    def get(self, user_id: str, plan_id: str, day: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM source_grounded_lecture_v4 WHERE user_id=? AND plan_id=? AND day=?", (user_id, plan_id, int(day))).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def find_by_generation_metadata(self, key: str, value: Any, day: int) -> dict[str, Any] | None:
        """Return a compatible read-only cached lecture template for a public case."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM source_grounded_lecture_v4 WHERE day=? ORDER BY updated_at DESC",
                (int(day),),
            ).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if (payload.get("generation_metadata") or {}).get(key) == value:
                return payload
        return None

    def save(self, user_id: str, plan_id: str, day: int, payload: dict[str, Any]) -> dict[str, Any]:
        stamp = _now()
        with self._connect() as conn:
            conn.execute("""INSERT INTO source_grounded_lecture_v4 VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(user_id, plan_id, day) DO UPDATE SET payload_json=excluded.payload_json,
                generator_version=excluded.generator_version, updated_at=excluded.updated_at""",
                (user_id, plan_id, int(day), json.dumps(payload, ensure_ascii=False), V4_GENERATOR_VERSION, stamp, stamp))
        return payload

    def progress(self, user_id: str, plan_id: str, day: int) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT section_id,status,updated_at FROM source_grounded_lecture_v4_progress WHERE user_id=? AND plan_id=? AND day=?", (user_id, plan_id, int(day))).fetchall()
        return {row["section_id"]: {"status": row["status"], "updated_at": row["updated_at"]} for row in rows}

    def set_progress(self, user_id: str, plan_id: str, day: int, section_id: str, completed: bool) -> dict[str, Any]:
        status, stamp = ("completed" if completed else "available"), _now()
        with self._connect() as conn:
            conn.execute("""INSERT INTO source_grounded_lecture_v4_progress VALUES(?,?,?,?,?,?)
                ON CONFLICT(user_id,plan_id,day,section_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at""",
                (user_id, plan_id, int(day), section_id, status, stamp))
        return {"section_id": section_id, "status": status, "updated_at": stamp}

    def exercise_answers(self, user_id: str, plan_id: str, day: int) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT section_id,question_id,answer_id,correct,updated_at FROM source_grounded_lecture_v4_exercise_answers WHERE user_id=? AND plan_id=? AND day=?", (user_id, plan_id, int(day))).fetchall()
        return {f"{row['section_id']}:{row['question_id']}": {"answer_id": row["answer_id"], "correct": bool(row["correct"]), "updated_at": row["updated_at"]} for row in rows}

    def set_exercise_answer(self, user_id: str, plan_id: str, day: int, section_id: str, question_id: str, answer_id: str, correct: bool) -> dict[str, Any]:
        stamp = _now()
        with self._connect() as conn:
            conn.execute("""INSERT INTO source_grounded_lecture_v4_exercise_answers VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id,plan_id,day,section_id,question_id) DO UPDATE SET answer_id=excluded.answer_id,correct=excluded.correct,updated_at=excluded.updated_at""", (user_id, plan_id, int(day), section_id, question_id, answer_id, int(correct), stamp))
        return {"section_id": section_id, "question_id": question_id, "answer_id": answer_id, "correct": correct, "updated_at": stamp}

    @staticmethod
    def _references_document(payload: dict[str, Any], document_id: str) -> bool:
        if any(str(item.get("document_id") or "") == document_id for item in payload.get("source_links") or []):
            return True
        if any(str(item.get("document_id") or "") == document_id for item in payload.get("lecture_sections") or []):
            return True
        return any(str(item.get("document_id") or "") == document_id for item in payload.get("source_materials") or [])

    def delete_by_document(self, user_id: str, document_id: str) -> int:
        """Invalidate only this owner's v4 snapshots that reference a deleted private PDF."""
        targets: list[tuple[str, int]] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT plan_id,day,payload_json FROM source_grounded_lecture_v4 WHERE user_id=?",
                (user_id,),
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload_json"])
                if self._references_document(payload, document_id):
                    targets.append((row["plan_id"], int(row["day"])))
            for plan_id, day in targets:
                conn.execute(
                    "DELETE FROM source_grounded_lecture_v4 WHERE user_id=? AND plan_id=? AND day=?",
                    (user_id, plan_id, day),
                )
                conn.execute(
                    "DELETE FROM source_grounded_lecture_v4_progress WHERE user_id=? AND plan_id=? AND day=?",
                    (user_id, plan_id, day),
                )
                conn.execute(
                    "DELETE FROM source_grounded_lecture_v4_exercise_answers WHERE user_id=? AND plan_id=? AND day=?",
                    (user_id, plan_id, day),
                )
        return len(targets)

    def delete_by_path(self, user_id: str, path_id: str, plan_ids: list[str] | None = None) -> int:
        """Remove cached v4 content for a deleted learning path."""
        removed = 0
        with self._connect() as conn:
            if plan_ids is None:
                rows = conn.execute(
                    "SELECT plan_id FROM source_grounded_lecture_v4 WHERE user_id=?",
                    (user_id,),
                ).fetchall()
                plan_ids = [row["plan_id"] for row in rows if row["plan_id"] == path_id or row["plan_id"].startswith(path_id)]
            if not plan_ids:
                return 0
            for plan_id in set(plan_ids):
                rows = conn.execute(
                    "SELECT day FROM source_grounded_lecture_v4 WHERE user_id=? AND plan_id=?",
                    (user_id, plan_id),
                ).fetchall()
                removed += len(rows)
                conn.execute(
                    "DELETE FROM source_grounded_lecture_v4 WHERE user_id=? AND plan_id=?",
                    (user_id, plan_id),
                )
                conn.execute(
                    "DELETE FROM source_grounded_lecture_v4_progress WHERE user_id=? AND plan_id=?",
                    (user_id, plan_id),
                )
                conn.execute(
                    "DELETE FROM source_grounded_lecture_v4_exercise_answers WHERE user_id=? AND plan_id=?",
                    (user_id, plan_id),
                )
        return removed
