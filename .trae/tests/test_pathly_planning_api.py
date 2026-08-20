from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


PATHLY_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
sys.path.insert(0, str(PATHLY_DIR))
sys.path.insert(0, str(KG_DIR))

import pathly_server  # noqa: E402
from infra.profile_store import ProfileStore  # noqa: E402
import pathly_backend  # noqa: E402
from pathly_backend import PathlyBackend, PathlyStore, PlanningClarificationRequiredError, PlanningUnavailableError, profile_from_payload  # noqa: E402
from pathly_contracts import build_path_context  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402


client = TestClient(pathly_server.app)


@pytest.fixture()
def isolated_backend(tmp_path, monkeypatch):
    profiles = ProfileStore(str(tmp_path / "profiles.db"))
    plans = PathlyStore(tmp_path / "plans.db")
    contracts = PathlyContractStore(plans.db_path)
    monkeypatch.setattr(pathly_server.backend, "profiles", profiles)
    monkeypatch.setattr(pathly_server.backend, "plans", plans)
    monkeypatch.setattr(pathly_server.backend, "contracts", contracts)

    def create_plan(user_id, goal_text=None, path_id=None, confirmed_mappings=None):
        profile = profiles.get_profile(user_id)
        if not profile:
            raise KeyError("profile_not_found")
        if goal_text:
            profile.goal_text = goal_text
            profiles.upsert_profile(profile)
        plan = {"plan_id": "test-plan-" + user_id + "-" + str(len(plans.list_plans(user_id)) + 1), "days": [{"day": 1, "focus_topics": ["Test Topic"], "estimated_minutes": profile.daily_minutes}], "feasibility": {"requested_days": profile.target_days, "daily_minutes": profile.daily_minutes}}
        snapshot = pathly_server.backend.get_profile_record(user_id) or profile.to_dict()
        record = plans.save_plan(
            user_id, plan, "fallback", ["test_kg"], path_id=path_id,
            goal_text=profile.goal_text, profile_snapshot=snapshot,
        )
        context = build_path_context(
            path_id=record["path_id"], user_id=user_id, goal_text=profile.goal_text,
            target_days=profile.target_days, max_daily_minutes=profile.daily_minutes,
            profile_snapshot=snapshot, plan=plan,
        ).to_dict()
        contracts.save_path_context(record["plan_id"], context)
        return plans.get_plan(record["plan_id"])

    monkeypatch.setattr(pathly_server.backend, "create_plan", create_plan)
    return profiles, plans


def test_profile_create_read_and_patch(isolated_backend):
    created = client.post(
        "/api/profiles",
        json={
            "user_id": "milestone-2-user",
            "name": "Lin",
            "goal_text": "Learn neural networks",
            "target_days": 7,
            "daily_minutes": 75,
            "known_topics": ["Python"],
        },
    )
    assert created.status_code == 201
    assert created.json()["data"]["user_id"] == "milestone-2-user"

    read = client.get("/api/profiles/milestone-2-user")
    assert read.status_code == 200
    assert read.json()["data"]["known_topics"] == ["Python"]

    patched = client.patch("/api/profiles/milestone-2-user", json={"daily_minutes": 45})
    assert patched.status_code == 200
    assert patched.json()["data"]["daily_minutes"] == 45


def test_user_can_own_multiple_paths_with_independent_versions(isolated_backend):
    client.post("/api/profiles", json={"user_id": "planner-user", "name": "Planner"})
    first = client.post("/api/plans", json={"user_id": "planner-user", "goal_text": "Neural networks"})
    second = client.post("/api/plans", json={"user_id": "planner-user", "goal_text": "Backpropagation"})
    assert first.status_code == 201
    assert first.json()["meta"]["mode"] == "fallback"
    assert first.json()["data"]["version"] == 1
    assert second.json()["data"]["version"] == 1
    assert first.json()["data"]["path_id"] != second.json()["data"]["path_id"]

    adapted = client.post(
        "/api/plans",
        json={"user_id": "planner-user", "goal_text": "Neural networks", "path_id": first.json()["data"]["path_id"]},
    )
    assert adapted.json()["data"]["version"] == 2
    assert adapted.json()["data"]["path_id"] == first.json()["data"]["path_id"]

    plan_id = first.json()["data"]["plan_id"]
    assert client.get(f"/api/plans/{plan_id}").status_code == 200
    listed = client.get("/api/users/planner-user/plans").json()["data"]
    assert sorted(item["version"] for item in listed) == [1, 1, 2]
    assert {item["goal_text"] for item in listed} == {"Neural networks", "Backpropagation"}


def test_user_can_delete_a_saved_path_with_confirmation_flow(isolated_backend):
    client.post("/api/profiles", json={"user_id": "deleter-user", "name": "Deleter"})
    first = client.post("/api/plans", json={"user_id": "deleter-user", "goal_text": "Neural networks"})
    second = client.post(
        "/api/plans",
        json={"user_id": "deleter-user", "goal_text": "Neural networks", "path_id": first.json()["data"]["path_id"]},
    )
    path_id = first.json()["data"]["path_id"]
    assert second.json()["data"]["path_id"] == path_id

    deleted = client.delete(f"/api/plans/{path_id}", json={"user_id": "deleter-user"})
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_plans"] == 2
    assert deleted.json()["data"]["deleted_v4_snapshots"] == 0

    remaining = client.get("/api/users/deleter-user/plans").json()["data"]
    assert remaining == []
    assert client.get(f"/api/plans/{first.json()['data']['plan_id']}").status_code == 404


def test_missing_profile_and_validation_errors_use_standard_envelope(isolated_backend):
    missing = client.post("/api/plans", json={"user_id": "missing"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"

    invalid = client.post("/api/profiles", json={"daily_minutes": 2})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"



def test_backend_raises_explicit_error_when_all_planners_fail(tmp_path, monkeypatch):
    service = PathlyBackend()
    service.profiles = ProfileStore(str(tmp_path / "fallback-profiles.db"))
    service.plans = PathlyStore(tmp_path / "fallback-plans.db")
    profile = profile_from_payload({"user_id": "fallback-user", "name": "Fallback"})
    service.profiles.upsert_profile(profile)

    class BrokenPlanner:
        def __init__(self, *args, **kwargs):
            pass

        def generate_plan(self, *args, **kwargs):
            raise RuntimeError("forced planning failure")

    monkeypatch.setattr(pathly_backend, "PlanningAgent", BrokenPlanner)
    with pytest.raises(PlanningUnavailableError) as exc:
        service.create_plan(profile.user_id)
    assert exc.value.attempts

def test_plan_api_returns_409_for_unreliable_topic_mapping(isolated_backend, monkeypatch):
    client.post("/api/profiles", json={"user_id": "clarify-user", "name": "Clarify"})

    def requires_clarification(*args, **kwargs):
        raise PlanningClarificationRequiredError([{
            "backend": "neo4j",
            "unmatched_terms": ["RAG"],
            "confirmation_required": [],
            "mapping_explanations": ["RAG -> unmatched"],
        }])

    monkeypatch.setattr(pathly_server.backend, "create_plan", requires_clarification)
    response = client.post("/api/plans", json={"user_id": "clarify-user", "goal_text": "learn RAG"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "planning_clarification_required"
    assert response.json()["error"]["details"]["mappings"][0]["unmatched_terms"] == ["RAG"]


def test_neo4j_failure_falls_back_to_json_and_is_labeled(tmp_path, monkeypatch):
    service = PathlyBackend()
    service.profiles = ProfileStore(str(tmp_path / "profiles.db"))
    service.plans = PathlyStore(tmp_path / "plans.db")
    service.contracts = PathlyContractStore(tmp_path / "plans.db")
    profile = profile_from_payload({"user_id": "json-fallback-user", "goal_text": "Learn target"})
    service.profiles.upsert_profile(profile)
    monkeypatch.setenv("NEO4J_PASSWORD", "configured-for-failure-injection")

    class Neo4jFailsJsonWorks:
        def __init__(self, *args, **kwargs):
            self.backend = kwargs.get("kg_backend")

        def generate_plan(self, *args, **kwargs):
            if self.backend == "neo4j":
                raise RuntimeError("forced neo4j outage")
            return {
                "days": [{"day": 1, "focus_topics": ["Target"], "estimated_minutes": 45}],
                "mapping": {"confirmation_required": [], "mapping_explanations": []},
                "uncovered_constraints": [],
            }

    monkeypatch.setattr(pathly_backend, "PlanningAgent", Neo4jFailsJsonWorks)
    result = service.create_plan(profile.user_id)
    assert result["mode"] == "fallback"
    assert result["sources"] == ["sqlite_profile", "kg_json"]
    assert result["plan"]["days"][0]["focus_topics"] == ["Target"]
