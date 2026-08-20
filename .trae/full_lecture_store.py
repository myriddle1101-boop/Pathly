"""Server-side progress storage for Full Lecture View v3."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FullLectureProgressStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.migrate()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS full_lecture_section_progress(
                    user_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    section_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, plan_id, day, section_id)
                )
                """
            )

    def get(self, user_id: str, plan_id: str, day: int) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT section_id, status, updated_at FROM full_lecture_section_progress WHERE user_id=? AND plan_id=? AND day=?",
                (user_id, plan_id, int(day)),
            ).fetchall()
        return {row["section_id"]: {"status": row["status"], "updated_at": row["updated_at"]} for row in rows}

    def set(self, user_id: str, plan_id: str, day: int, section_id: str, completed: bool) -> dict[str, Any]:
        status = "completed" if completed else "available"
        stamp = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO full_lecture_section_progress VALUES(?,?,?,?,?,?)
                ON CONFLICT(user_id, plan_id, day, section_id)
                DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
                """,
                (user_id, plan_id, int(day), section_id, status, stamp),
            )
        return {"section_id": section_id, "status": status, "updated_at": stamp}

