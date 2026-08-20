"""Additive, page-level source registry for new full-experience goal chains."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperienceSourceStore:
    """Owns curated source records without replacing the legacy golden registry."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS experience_sources (
                    source_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    canonical_concept_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    license_status TEXT NOT NULL,
                    learner_tier TEXT NOT NULL DEFAULT 'shared',
                    review_status TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experience_page_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES experience_sources(source_id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    content_role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(source_id, page_number)
                );
                CREATE INDEX IF NOT EXISTS idx_experience_sources_goal
                    ON experience_sources(goal_id, canonical_concept_id, review_status);
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(experience_sources)").fetchall()}
            if "learner_tier" not in columns:
                conn.execute("ALTER TABLE experience_sources ADD COLUMN learner_tier TEXT NOT NULL DEFAULT 'shared'")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def upsert(self, source: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
        required = {"source_id", "goal_id", "canonical_concept_id", "resource_id", "document_id", "document_title", "source_url", "license_status", "learner_tier", "review_status", "source_version"}
        missing = sorted(required - set(source))
        if missing:
            raise ValueError("missing source fields: " + ", ".join(missing))
        if source["review_status"] != "approved":
            raise ValueError("only explicitly approved source records may be stored for a full-experience chain")
        if not pages or any(not int(item.get("page_number") or 0) or not str(item.get("text") or "").strip() for item in pages):
            raise ValueError("every curated source requires non-empty page-level evidence")
        stamp = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO experience_sources
                (source_id, goal_id, canonical_concept_id, resource_id, document_id,
                 document_title, source_url, license_status, learner_tier, review_status,
                 source_version, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_id) DO UPDATE SET goal_id=excluded.goal_id,
                  canonical_concept_id=excluded.canonical_concept_id, resource_id=excluded.resource_id,
                  document_id=excluded.document_id, document_title=excluded.document_title,
                  source_url=excluded.source_url, license_status=excluded.license_status,
                  learner_tier=excluded.learner_tier,
                  review_status=excluded.review_status, source_version=excluded.source_version, updated_at=excluded.updated_at""",
                (source["source_id"], source["goal_id"], source["canonical_concept_id"], source["resource_id"], source["document_id"], source["document_title"], source["source_url"], source["license_status"], source["learner_tier"], source["review_status"], source["source_version"], stamp, stamp),
            )
            conn.execute("DELETE FROM experience_page_chunks WHERE source_id=?", (source["source_id"],))
            conn.executemany(
                "INSERT INTO experience_page_chunks VALUES (?,?,?,?,?,?)",
                [(item["chunk_id"], source["source_id"], int(item["page_number"]), item["content_role"], item["text"], stamp) for item in pages],
            )
        return self.get(source["source_id"]) or {}

    def get(self, source_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM experience_sources WHERE source_id=?", (source_id,)).fetchone()
            if not row:
                return None
            pages = conn.execute("SELECT chunk_id,page_number,content_role,text FROM experience_page_chunks WHERE source_id=? ORDER BY page_number", (source_id,)).fetchall()
        value = dict(row)
        value["pages"] = [dict(item) for item in pages]
        return value
