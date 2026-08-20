import json
from pathlib import Path
import sqlite3
import sys

from fastapi.testclient import TestClient


PATHLY_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
sys.path.insert(0, str(PATHLY_DIR))
sys.path.insert(0, str(KG_DIR))

import pathly_server  # noqa: E402
from infra.profile_store import ProfileStore  # noqa: E402
from pathly_backend import PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402


client = TestClient(pathly_server.app)


def test_profile_v2_separates_stable_traits_from_path_capacity(tmp_path, monkeypatch):
    profiles = ProfileStore(str(tmp_path / "profiles.db"))
    plans = PathlyStore(tmp_path / "plans.db")
    contracts = PathlyContractStore(plans.db_path)
    monkeypatch.setattr(pathly_server.backend, "profiles", profiles)
    monkeypatch.setattr(pathly_server.backend, "plans", plans)
    monkeypatch.setattr(pathly_server.backend, "contracts", contracts)

    response = client.post(
        "/api/profiles",
        json={
            "user_id": "profile-v2-user",
            "name": "Lin",
            "daily_minutes": 80,
            "cognitive_traits": {
                "mathematical_ability": 4,
                "logical_reasoning": 5,
            },
            "affective_defaults": {
                "learning_style": "visual",
                "daily_time_minutes": 999,
            },
            "inference_records": {
                "mathematical_ability": {
                    "confidence": 0.8,
                    "reason": "situational answer",
                }
            },
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["profile_version"] == 2
    assert data["cognitive_traits"]["mathematical_ability"] == 4
    assert data["cognitive_traits"]["logical_reasoning"] == 5
    assert data["affective_defaults"]["learning_style"] == "visual"
    assert "daily_time_minutes" not in data["affective_defaults"]
    assert "daily_minutes" not in data["affective_defaults"]
    # Legacy capacity is intentionally retained until onboarding switches to
    # LearningPathContext.
    assert data["daily_minutes"] == 80

    patched = client.patch(
        "/api/profiles/profile-v2-user",
        json={
            "cognitive_traits": {"abstract_thinking": 4},
            "affective_defaults": {"pace_preference": "steady"},
        },
    )
    patched_data = patched.json()["data"]
    assert patched_data["cognitive_traits"]["mathematical_ability"] == 4
    assert patched_data["cognitive_traits"]["abstract_thinking"] == 4
    assert patched_data["affective_defaults"]["learning_style"] == "visual"
    assert patched_data["affective_defaults"]["pace_preference"] == "steady"


def test_contract_store_backfills_legacy_plan_without_deleting_it(tmp_path):
    db_path = tmp_path / "legacy-plans.db"
    plan = {
        "plan_id": "legacy-plan",
        "target_topics": ["Neural Networks"],
        "days": [{"day": 1, "focus_topics": ["Neural Networks"]}],
        "feasibility": {"requested_days": 12, "daily_minutes": 55},
    }
    snapshot = {
        "goal_text": "Learn neural networks",
        "target_days": 12,
        "daily_minutes": 55,
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE learning_plans (
                plan_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                mode TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO learning_plans(
                plan_id, user_id, version, status, mode, sources_json,
                plan_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-plan",
                "legacy-user",
                1,
                "active",
                "fallback",
                '["kg_json"]',
                json.dumps(plan),
                "2026-01-01T00:00:00+00:00",
            ),
        )

    plans = PathlyStore(db_path)
    PathlyContractStore(db_path)
    record = plans.get_plan("legacy-plan")
    assert record is not None
    assert record["plan"]["target_topics"] == ["Neural Networks"]
    assert record["path_id"] == "legacy-plan"
    assert record["path_context"]["target_days"] == 12
    assert record["path_context"]["max_daily_minutes"] == 55
    assert record["path_context"]["target_concepts"] == ["Neural Networks"]


def test_o0_creates_future_contract_tables_without_document_rows(tmp_path):
    db_path = tmp_path / "contracts.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {
            "learner_profile_extensions",
            "learning_path_contexts",
            "user_documents",
            "path_document_links",
            "workload_estimates",
        }.issubset(tables)
        assert conn.execute("SELECT COUNT(*) FROM user_documents").fetchone()[0] == 0
