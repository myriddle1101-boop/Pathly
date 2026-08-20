"""Additive SQLite storage for Pathly V2 contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from pathly_contracts import PROFILE_SCHEMA_VERSION, build_path_context


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PathlyContractStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _object(value: str | None) -> dict[str, Any]:
        try:
            decoded = json.loads(value or "{}")
            return decoded if isinstance(decoded, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _init_db(self) -> None:
        with self._connect() as conn:
            plan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(learning_plans)")}
            if plan_columns and "path_context_json" not in plan_columns:
                conn.execute("ALTER TABLE learning_plans ADD COLUMN path_context_json TEXT")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS learner_profile_extensions (
                    user_id TEXT PRIMARY KEY,
                    profile_version INTEGER NOT NULL DEFAULT 2,
                    cognitive_traits_json TEXT NOT NULL DEFAULT '{}',
                    affective_defaults_json TEXT NOT NULL DEFAULT '{}',
                    inference_records_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learning_path_contexts (
                    path_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS user_documents (
                    document_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );
                CREATE TABLE IF NOT EXISTS path_document_links (
                    path_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    link_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(path_id, document_id)
                );
                CREATE TABLE IF NOT EXISTS workload_estimates (
                    estimate_id TEXT PRIMARY KEY,
                    path_id TEXT NOT NULL,
                    estimate_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._backfill_paths(conn)

    def _backfill_paths(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(learning_plans)")}
        needed = {"plan_id", "user_id", "plan_json", "created_at", "path_context_json"}
        if not needed.issubset(columns):
            return
        rows = conn.execute(
            "SELECT * FROM learning_plans WHERE path_context_json IS NULL OR path_context_json = ''"
        ).fetchall()
        for row in rows:
            plan = self._object(row["plan_json"])
            snapshot = self._object(row["profile_snapshot_json"]) if "profile_snapshot_json" in columns else {}
            feasibility = plan.get("feasibility") or {}
            path_id = row["path_id"] if "path_id" in columns and row["path_id"] else row["plan_id"]
            goal = row["goal_text"] if "goal_text" in columns and row["goal_text"] else snapshot.get("goal_text", "")
            context = build_path_context(
                path_id=path_id,
                user_id=row["user_id"],
                goal_text=goal,
                target_days=snapshot.get("target_days") or feasibility.get("requested_days") or 7,
                max_daily_minutes=snapshot.get("daily_minutes") or feasibility.get("daily_minutes") or 75,
                profile_snapshot=snapshot,
                plan=plan,
            ).to_dict()
            self._save_path_context_with_connection(conn, context, row["created_at"])
            conn.execute(
                "UPDATE learning_plans SET path_context_json = ? WHERE plan_id = ?",
                (json.dumps(context, ensure_ascii=False), row["plan_id"]),
            )

    def save_profile_extension(
        self,
        user_id: str,
        *,
        cognitive_traits: dict[str, Any] | None = None,
        affective_defaults: dict[str, Any] | None = None,
        inference_records: dict[str, Any] | None = None,
        profile_version: int = PROFILE_SCHEMA_VERSION,
    ) -> None:
        existing = self.get_profile_extension(user_id)
        cognitive = {**(existing.get("cognitive_traits") or {}), **(cognitive_traits or {})}
        affective = {**(existing.get("affective_defaults") or {}), **(affective_defaults or {})}
        affective.pop("daily_minutes", None)
        affective.pop("daily_time_minutes", None)
        inferences = {**(existing.get("inference_records") or {}), **(inference_records or {})}
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learner_profile_extensions(
                    user_id, profile_version, cognitive_traits_json,
                    affective_defaults_json, inference_records_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    profile_version=excluded.profile_version,
                    cognitive_traits_json=excluded.cognitive_traits_json,
                    affective_defaults_json=excluded.affective_defaults_json,
                    inference_records_json=excluded.inference_records_json,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    profile_version,
                    json.dumps(cognitive, ensure_ascii=False),
                    json.dumps(affective, ensure_ascii=False),
                    json.dumps(inferences, ensure_ascii=False),
                    existing.get("created_at") or now,
                    now,
                ),
            )

    def get_profile_extension(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM learner_profile_extensions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return {}
        return {
            "profile_version": row["profile_version"],
            "cognitive_traits": self._object(row["cognitive_traits_json"]),
            "affective_defaults": self._object(row["affective_defaults_json"]),
            "inference_records": self._object(row["inference_records_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _save_path_context_with_connection(
        self,
        conn: sqlite3.Connection,
        context: dict[str, Any],
        created_at: str | None = None,
    ) -> None:
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO learning_path_contexts(path_id, user_id, context_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path_id) DO UPDATE SET
                context_json=excluded.context_json,
                updated_at=excluded.updated_at
            """,
            (
                context["path_id"],
                context["user_id"],
                json.dumps(context, ensure_ascii=False),
                created_at or now,
                now,
            ),
        )

    def save_path_context(self, plan_id: str, context: dict[str, Any]) -> None:
        with self._connect() as conn:
            self._save_path_context_with_connection(conn, context)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(learning_plans)")}
            if "path_context_json" in columns:
                conn.execute(
                    "UPDATE learning_plans SET path_context_json = ? WHERE plan_id = ?",
                    (json.dumps(context, ensure_ascii=False), plan_id),
                )

    def delete_path_context(self, path_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM learning_path_contexts WHERE path_id = ?", (path_id,))
            conn.execute("DELETE FROM workload_estimates WHERE path_id = ?", (path_id,))
            conn.execute("DELETE FROM path_document_links WHERE path_id = ?", (path_id,))
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(learning_plans)")}
            if "path_context_json" in columns:
                conn.execute("UPDATE learning_plans SET path_context_json = NULL WHERE path_id = ?", (path_id,))
