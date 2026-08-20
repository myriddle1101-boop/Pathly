import sqlite3

from fastapi.testclient import TestClient

import pathly_server
from pathly_security import AnonymousSessionStore, COOKIE_NAME
from experience_run_store import ExperienceRunStore


def test_session_store_hashes_token_and_resolves_owner(tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    token, record = store.create()
    assert store.resolve(token)["user_id"] == record["user_id"]
    with sqlite3.connect(tmp_path / "sessions.db") as conn:
        row = conn.execute(
            "SELECT token_hash FROM anonymous_sessions WHERE session_id = ?",
            (record["session_id"],),
        ).fetchone()
    assert row[0] != token
    assert len(row[0]) == 64
    store.revoke(token)
    assert store.resolve(token) is None


def test_required_session_blocks_missing_and_mismatched_owner(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    client = TestClient(pathly_server.app)
    assert client.get("/api/users/no-session/plans").status_code == 401
    created = client.post("/api/sessions/anonymous")
    assert created.status_code == 201
    user_id = created.json()["data"]["user_id"]
    assert COOKIE_NAME in client.cookies
    assert client.get(f"/api/users/{user_id}/plans").status_code == 200
    mismatch = client.get("/api/users/another-user/plans")
    assert mismatch.status_code == 403
    assert mismatch.json()["error"]["code"] == "owner_mismatch"


def test_json_owner_and_origin_are_checked(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    client = TestClient(pathly_server.app)
    session = client.post("/api/sessions/anonymous").json()["data"]
    wrong_owner = client.post(
        "/api/onboarding-drafts",
        json={"user_id": "other", "goal_text": "Learn safely"},
    )
    assert wrong_owner.status_code == 403
    cross_origin = client.post(
        "/api/onboarding-drafts",
        headers={"Origin": "https://attacker.example"},
        json={"user_id": session["user_id"], "goal_text": "Learn safely"},
    )
    assert cross_origin.status_code == 403
    assert cross_origin.json()["error"]["code"] == "origin_mismatch"


def test_two_sessions_cannot_read_each_others_profile(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    owner = TestClient(pathly_server.app)
    other = TestClient(pathly_server.app)
    owner_id = owner.post("/api/sessions/anonymous").json()["data"]["user_id"]
    other.post("/api/sessions/anonymous")
    assert other.get(f"/api/profiles/{owner_id}").status_code == 403


def test_fresh_walkthrough_always_issues_empty_isolated_owner(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    monkeypatch.setattr(pathly_server, "LOCAL_DEMO_SHARED_MODE", False)
    client = TestClient(pathly_server.app)

    original = client.post("/api/sessions/anonymous").json()["data"]
    original_cookie = client.cookies.get(COOKIE_NAME)
    fresh_response = client.post("/api/sessions/fresh-walkthrough")

    assert fresh_response.status_code == 201
    fresh = fresh_response.json()["data"]
    assert fresh["user_id"] != original["user_id"]
    assert client.cookies.get(COOKIE_NAME) != original_cookie
    assert store.resolve(client.cookies.get(COOKIE_NAME))["user_id"] == fresh["user_id"]
    assert fresh["walkthrough_type"] == "fresh_user"
    assert fresh["fixture_injected"] is False
    assert fresh["profile_exists"] is False
    assert fresh["plan_count"] == 0
    assert fresh["onboarding_draft_count"] == 0
    assert fresh["content_cache_count"] == 0
    assert fresh["empty_workspace_verified"] is True

    second = client.post("/api/sessions/fresh-walkthrough").json()["data"]
    assert second["user_id"] != fresh["user_id"]


def test_demo_user_switch_reissues_server_owned_cookie_and_changes_owner(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    monkeypatch.setattr(pathly_server, "DEMO_USERS_ENABLED", True)
    monkeypatch.setattr(pathly_server, "LOCAL_DEMO_SHARED_MODE", False)
    monkeypatch.setattr(pathly_server, "_ensure_demo_profile", lambda fixture: fixture)
    client = TestClient(pathly_server.app)
    client.post("/api/sessions/anonymous")
    users = client.get("/api/demo-users").json()["data"]
    assert {user["user_id"] for user in users} == {
        "demo-foundation-learner", "demo-advanced-learner"
    }
    first_cookie = client.cookies.get(COOKIE_NAME)
    switched = client.post("/api/demo-users/demo-foundation-learner/switch")
    assert switched.status_code == 200
    assert switched.json()["data"]["display_name"] == "Foundation Learner"
    assert client.cookies.get(COOKIE_NAME) != first_cookie
    assert store.resolve(client.cookies.get(COOKIE_NAME))["user_id"] == "demo-foundation-learner"
    assert client.get("/api/users/demo-advanced-learner/plans").status_code == 403


def test_demo_user_routes_are_hidden_when_disabled(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    monkeypatch.setattr(pathly_server, "DEMO_USERS_ENABLED", False)
    client = TestClient(pathly_server.app)
    client.post("/api/sessions/anonymous")
    assert client.get("/api/demo-users").status_code == 404
    assert client.post("/api/demo-users/demo-foundation-learner/switch").status_code == 404


def test_controlled_evaluation_routes_expose_isolated_local_research_contract(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    monkeypatch.setattr(pathly_server, "DEMO_USERS_ENABLED", True)
    monkeypatch.setattr(pathly_server, "LOCAL_DEMO_SHARED_MODE", False)
    monkeypatch.setattr(pathly_server, "_ensure_demo_profile", lambda fixture: fixture)
    client = TestClient(pathly_server.app)
    client.post("/api/sessions/anonymous")

    options = client.get("/api/controlled-evaluation/options")
    assert options.status_code == 200
    data = options.json()["data"]
    assert [row["version"] for row in data["systems"]] == ["V0", "V1", "V2", "V3"]
    assert any(goal["goal_id"] == "rag" for goal in data["goals"])
    assert any(profile["user_id"] == "demo-foundation-learner" for profile in data["profiles"])


def test_controlled_evaluation_run_isolated_from_ordinary_learning_paths(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "REQUIRE_SESSION_AUTH", True)
    monkeypatch.setattr(pathly_server, "DEMO_USERS_ENABLED", True)
    monkeypatch.setattr(pathly_server, "LOCAL_DEMO_SHARED_MODE", False)
    monkeypatch.setattr(pathly_server, "_run_controlled_evaluation", lambda payload: {
        "run_id": "controlled-run-1",
        "run_type": "controlled_evaluation",
        "user_id": payload.user_id,
        "goal": payload.goal_text,
        "system_version": payload.system_version.upper(),
        "status": "success",
        "checks": {"ordinary_learning_paths_untouched": True},
    })
    client = TestClient(pathly_server.app)
    client.post("/api/sessions/anonymous")

    response = client.post("/api/controlled-evaluation/runs", json={
        "user_id": "demo-foundation-learner",
        "goal_text": "Understand how retrieval-augmented generation uses retrieved evidence to answer a query.",
        "system_version": "V3",
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["run_type"] == "controlled_evaluation"
    assert data["system_version"] == "V3"
    assert data["checks"]["ordinary_learning_paths_untouched"] is True


def test_controlled_evaluation_run_history_is_owner_scoped(monkeypatch, tmp_path):
    store = AnonymousSessionStore(tmp_path / "sessions.db")
    monkeypatch.setattr(pathly_server, "session_store", store)
    monkeypatch.setattr(pathly_server, "DEMO_USERS_ENABLED", True)
    monkeypatch.setattr(pathly_server, "LOCAL_DEMO_SHARED_MODE", False)
    monkeypatch.setattr(pathly_server, "_controlled_evaluation_enabled", lambda: True)
    monkeypatch.setattr(pathly_server, "NORMAL_PROFILE_FIXTURES", {
        "foundation": {"user_id": "demo-foundation-learner", "display_name": "Foundation Learner", "level": "foundation"},
        "advanced": {"user_id": "demo-advanced-learner", "display_name": "Advanced Learner", "level": "advanced"},
    })
    monkeypatch.setattr(pathly_server, "experience_run_store", ExperienceRunStore(tmp_path / "runs.db"))
    client = TestClient(pathly_server.app)
    session = client.post("/api/sessions/anonymous")
    assert session.status_code == 201
    cookie = session.cookies.get(pathly_server.COOKIE_NAME)
    # The normal anonymous session cannot read demo-owned controlled artifacts.
    response = client.get("/api/controlled-evaluation/runs", cookies={pathly_server.COOKIE_NAME: cookie})
    assert response.status_code == 403


def test_controlled_evaluation_artifact_contains_reproducibility_and_quality_checks(monkeypatch, tmp_path):
    monkeypatch.setattr(pathly_server, "experience_run_store", ExperienceRunStore(tmp_path / "runs.db"))
    monkeypatch.setattr(pathly_server, "_controlled_planning_unit", lambda *args, **kwargs: {
        "planning_agent": "controlled_eval_v0_planning_live",
        "goal_text": args[0]["goal"], "core_concept": args[0]["goal"],
        "prerequisite_path": [], "daily_minutes": 60, "session_minutes": 60,
        "estimated_total_minutes": 120, "estimated_days": 2, "concept_count": 1,
        "feasibility": {"status": "feasible"}, "planning_rationale": "Natural plan.",
        "plan_markdown": "## Goal interpretation\nTest\n\n## Day 1 plan\nTest",
        "output_format": "natural_markdown", "prompt_version": "test",
    })
    monkeypatch.setattr(pathly_server, "_controlled_eval_text_unit", lambda *args, **kwargs: {
        "contract_version": "controlled-evaluation-natural-content-v2",
        "title": "Test", "goal": args[0]["goal"], "content_markdown": "## Core idea\nTest",
        "content_agent": "controlled_eval_v0_content_live", "content_inputs": {},
        "source_evidence": [], "generation_mode": "controlled_eval_v0_live",
        "planning_agent": "controlled_eval_v0_planning_live", "output_format": "natural_markdown",
        "day_1": {"title": "Day 1", "estimated_minutes": 60, "content_markdown": "## Core idea\nTest", "lecture_sections": []},
        "lecture_sections": [],
    })
    payload = pathly_server.ControlledEvaluationRunPayload(
        user_id="demo-foundation-learner",
        goal_text="Explain how neural networks learn to solve XOR.",
        system_version="V0",
        daily_minutes=60,
        temperature=0.2,
        allow_cache=False,
    )
    record = pathly_server._run_controlled_evaluation(payload)
    assert record["cache"]["fingerprint"]
    assert record["checks"]["goal_coverage"]["passed"] is True
    assert record["checks"]["schema"]["passed"] is True
    assert record["checks"]["cache_identity"]["passed"] is True
    assert record["checks"]["ordinary_learning_paths_untouched"] is True
