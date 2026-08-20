from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.config import SQLITE_PATH


REQUIRED_PROFILE_COLUMNS = [
    "user_id",
    "goal_text",
    "target_days",
    "daily_minutes",
    "known_topics",
    "skill_tree",
    "confidence_level",
    "anxiety_level",
    "pace_preference",
    "mastery_vector",
    "completed_topics",
    "current_day",
    "last_practice",
]


def verify_profiles(db_path: Path = SQLITE_PATH) -> dict[str, Any]:
    result: dict[str, Any] = {
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "passed": True,
        "checks": [],
    }
    if not db_path.exists():
        result["passed"] = False
        result["checks"].append({"name": "db_exists", "passed": False})
        return result

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        profile_table_exists = "learner_profiles" in tables
        result["checks"].append({"name": "learner_profiles_table", "passed": profile_table_exists})
        if not profile_table_exists:
            result["passed"] = False
            return result

        columns = [row["name"] for row in conn.execute("PRAGMA table_info(learner_profiles)").fetchall()]
        missing_columns = [column for column in REQUIRED_PROFILE_COLUMNS if column not in columns]
        result["checks"].append(
            {
                "name": "required_columns",
                "required": REQUIRED_PROFILE_COLUMNS,
                "missing": missing_columns,
                "passed": not missing_columns,
            }
        )
        if missing_columns:
            result["passed"] = False

        profile_count = conn.execute("SELECT count(*) AS count FROM learner_profiles").fetchone()["count"]
        result["profile_count"] = int(profile_count)
        result["checks"].append({"name": "profile_count", "actual": int(profile_count), "passed": profile_count > 0})
        if profile_count <= 0:
            result["passed"] = False

        examples = conn.execute(
            """
            SELECT user_id, goal_text, target_days, daily_minutes, known_topics, skill_tree,
                   confidence_level, anxiety_level, pace_preference,
                   mastery_vector, completed_topics, current_day, last_practice
            FROM learner_profiles
            ORDER BY updated_at DESC
            LIMIT 5
            """
        ).fetchall()
        result["examples"] = [dict(row) for row in examples]

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify local SQLite learner profile infrastructure.")
    parser.add_argument("--db", default=str(SQLITE_PATH), help="Path to learner_profiles.db")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_profiles(Path(args.db))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
