from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from infra.config import SQLITE_PATH, ensure_data_dirs
from infra.profile_schema import LearnerProfile


class ProfileStore:
    def __init__(self, db_path: str | None = None):
        ensure_data_dirs()
        self.db_path = db_path or str(SQLITE_PATH)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_profiles (
                    user_id TEXT PRIMARY KEY,
                    academic_level TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    goal_text TEXT NOT NULL,
                    target_days INTEGER NOT NULL,
                    daily_minutes INTEGER NOT NULL,
                    prior_knowledge_level INTEGER NOT NULL,
                    math_foundation INTEGER NOT NULL,
                    programming_foundation INTEGER NOT NULL,
                    self_regulation INTEGER NOT NULL,
                    interest_tags TEXT NOT NULL,
                    preferred_style TEXT NOT NULL,
                    motivation_level INTEGER NOT NULL,
                    confidence_level INTEGER NOT NULL,
                    anxiety_level INTEGER NOT NULL,
                    known_topics TEXT NOT NULL,
                    skill_tree TEXT NOT NULL DEFAULT '{}',
                    preferred_examples TEXT NOT NULL,
                    pace_preference TEXT NOT NULL,
                    mastery_vector TEXT NOT NULL DEFAULT '{}',
                    completed_topics TEXT NOT NULL DEFAULT '[]',
                    current_day INTEGER NOT NULL DEFAULT 1,
                    last_practice TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "learner_profiles", "skill_tree", "TEXT NOT NULL DEFAULT '{}'" )
            self._ensure_column(conn, "learner_profiles", "mastery_vector", "TEXT NOT NULL DEFAULT '{}'" )
            self._ensure_column(conn, "learner_profiles", "completed_topics", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "learner_profiles", "current_day", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "learner_profiles", "last_practice", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_goal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    goal_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def upsert_profile(self, profile: LearnerProfile) -> None:
        now = datetime.utcnow().isoformat()
        payload = profile.to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users(user_id, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
                """,
                (profile.user_id, profile.name, now),
            )
            conn.execute(
                """
                INSERT INTO learner_profiles(
                    user_id, academic_level, domain, goal_text, target_days, daily_minutes,
                    prior_knowledge_level, math_foundation, programming_foundation,
                    self_regulation, interest_tags, preferred_style, motivation_level,
                    confidence_level, anxiety_level, known_topics, skill_tree,
                    preferred_examples, pace_preference, mastery_vector, completed_topics,
                    current_day, last_practice, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    academic_level=excluded.academic_level,
                    domain=excluded.domain,
                    goal_text=excluded.goal_text,
                    target_days=excluded.target_days,
                    daily_minutes=excluded.daily_minutes,
                    prior_knowledge_level=excluded.prior_knowledge_level,
                    math_foundation=excluded.math_foundation,
                    programming_foundation=excluded.programming_foundation,
                    self_regulation=excluded.self_regulation,
                    interest_tags=excluded.interest_tags,
                    preferred_style=excluded.preferred_style,
                    motivation_level=excluded.motivation_level,
                    confidence_level=excluded.confidence_level,
                    anxiety_level=excluded.anxiety_level,
                    known_topics=excluded.known_topics,
                    skill_tree=excluded.skill_tree,
                    preferred_examples=excluded.preferred_examples,
                    pace_preference=excluded.pace_preference,
                    mastery_vector=excluded.mastery_vector,
                    completed_topics=excluded.completed_topics,
                    current_day=excluded.current_day,
                    last_practice=excluded.last_practice,
                    updated_at=excluded.updated_at
                """,
                (
                    profile.user_id,
                    profile.academic_level,
                    profile.domain,
                    profile.goal_text,
                    profile.target_days,
                    profile.daily_minutes,
                    profile.prior_knowledge_level,
                    profile.math_foundation,
                    profile.programming_foundation,
                    profile.self_regulation,
                    json.dumps(payload["interest_tags"], ensure_ascii=False),
                    profile.preferred_style,
                    profile.motivation_level,
                    profile.confidence_level,
                    profile.anxiety_level,
                    json.dumps(payload["known_topics"], ensure_ascii=False),
                    json.dumps(payload["skill_tree"], ensure_ascii=False),
                    json.dumps(payload["preferred_examples"], ensure_ascii=False),
                    profile.pace_preference,
                    json.dumps(payload["mastery_vector"], ensure_ascii=False),
                    json.dumps(payload["completed_topics"], ensure_ascii=False),
                    profile.current_day,
                    profile.last_practice,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO learner_goal_history(user_id, goal_text, created_at) VALUES (?, ?, ?)",
                (profile.user_id, profile.goal_text, now),
            )

    def get_profile(self, user_id: str) -> LearnerProfile | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT u.name, p.* FROM learner_profiles p JOIN users u ON u.user_id = p.user_id WHERE p.user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return LearnerProfile(
            user_id=row["user_id"],
            name=row["name"],
            academic_level=row["academic_level"],
            domain=row["domain"],
            goal_text=row["goal_text"],
            target_days=row["target_days"],
            daily_minutes=row["daily_minutes"],
            prior_knowledge_level=row["prior_knowledge_level"],
            math_foundation=row["math_foundation"],
            programming_foundation=row["programming_foundation"],
            self_regulation=row["self_regulation"],
            interest_tags=json.loads(row["interest_tags"]),
            preferred_style=row["preferred_style"],
            motivation_level=row["motivation_level"],
            confidence_level=row["confidence_level"],
            anxiety_level=row["anxiety_level"],
            known_topics=json.loads(row["known_topics"]),
            skill_tree=json.loads(row["skill_tree"] or "{}"),
            preferred_examples=json.loads(row["preferred_examples"]),
            pace_preference=row["pace_preference"],
            mastery_vector=json.loads(row["mastery_vector"] or "{}"),
            completed_topics=json.loads(row["completed_topics"] or "[]"),
            current_day=row["current_day"],
            last_practice=row["last_practice"],
        )

    def list_profiles(self) -> list[LearnerProfile]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT user_id FROM learner_profiles ORDER BY updated_at DESC").fetchall()
        profiles = []
        for row in rows:
            profile = self.get_profile(row["user_id"])
            if profile:
                profiles.append(profile)
        return profiles
