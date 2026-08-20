"""Anonymous, server-owned session identity for Pathly."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


COOKIE_NAME = "pathly_session"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnonymousSessionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS anonymous_sessions (
                    session_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_token
                    ON anonymous_sessions(token_hash, expires_at);
                """
            )

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, ttl_days: int = 30) -> tuple[str, dict]:
        token = secrets.token_urlsafe(48)
        now = _now()
        record = {
            "session_id": str(uuid.uuid4()),
            "user_id": f"anon-{uuid.uuid4().hex}",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=ttl_days)).isoformat(),
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO anonymous_sessions(
                    session_id, token_hash, user_id, created_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    record["session_id"],
                    self.token_hash(token),
                    record["user_id"],
                    record["created_at"],
                    record["expires_at"],
                ),
            )
        return token, record

    def create_for_user(self, user_id: str, ttl_days: int = 30) -> tuple[str, dict]:
        """Issue a fresh local session for a known demo identity."""
        user_id = str(user_id or "").strip()
        if not user_id:
            raise ValueError("user_id is required")
        token = secrets.token_urlsafe(48)
        now = _now()
        record = {
            "session_id": str(uuid.uuid4()),
            "user_id": user_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=ttl_days)).isoformat(),
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM anonymous_sessions WHERE user_id = ?", (user_id,))
            conn.execute(
                """
                INSERT INTO anonymous_sessions(
                    session_id, token_hash, user_id, created_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    record["session_id"], self.token_hash(token), user_id,
                    record["created_at"], record["expires_at"],
                ),
            )
        return token, record

    def resolve(self, token: str | None) -> dict | None:
        if not token:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT session_id, user_id, created_at, expires_at
                FROM anonymous_sessions
                WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?
                """,
                (self.token_hash(token), _now().isoformat()),
            ).fetchone()
        return dict(row) if row else None

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE anonymous_sessions SET revoked_at = ? WHERE token_hash = ?",
                (_now().isoformat(), self.token_hash(token)),
            )
