from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import pathly_server
from pathly_backend import PathlyStore
from pathly_contract_store import PathlyContractStore
from pathly_scheduler import (
    ActivityScheduler,
    ScheduleNotFoundError,
    ScheduleService,
)


def pending_plan(days=7, capacity=60, strategy="proceed"):
    return {
        "schema_version": 3,
        "plan_id": "plan-v1",
        "path_id": "path-1",
        "goal": {"text": "Learn Target"},
        "concept_path": [
            {
                "concept_id": "Foundation",
                "is_target": False,
                "prerequisite_ids": [],
            },
            {
                "concept_id": "Target",
                "is_target": True,
                "prerequisite_ids": ["Foundation"],
            },
        ],
        "activities": [
            {
                "activity_id": "f-explain",
                "activity_type": "explanation",
                "concept_ids": ["Foundation"],
                "estimated_minutes": 45,
                "sequence": 1,
            },
            {
                "activity_id": "f-review",
                "activity_type": "review",
                "concept_ids": ["Foundation"],
                "estimated_minutes": 20,
                "sequence": 2,
            },
            {
                "activity_id": "t-explain",
                "activity_type": "explanation",
                "concept_ids": ["Target"],
                "estimated_minutes": 55,
                "sequence": 3,
            },
            {
                "activity_id": "t-practice",
                "activity_type": "practice",
                "concept_ids": ["Target"],
                "estimated_minutes": 50,
                "sequence": 4,
            },
            {
                "activity_id": "t-quiz",
                "activity_type": "quiz",
                "concept_ids": ["Target"],
                "estimated_minutes": 15,
                "sequence": 5,
            },
            {
                "activity_id": "t-review",
                "activity_type": "review",
                "concept_ids": ["Target"],
                "estimated_minutes": 20,
                "sequence": 6,
            },
            {
                "activity_id": "project",
                "activity_type": "project",
                "concept_ids": ["Target"],
                "estimated_minutes": 35,
                "sequence": 7,
            },
            {
                "activity_id": "reflection",
                "activity_type": "reflection",
                "concept_ids": ["Target"],
                "estimated_minutes": 10,
                "sequence": 8,
            },
        ],
        "feasibility": {
            "requested_days": days,
            "effective_days": days,
            "max_available_daily_minutes": capacity,
            "capacity_gap_minutes": max(0, days * capacity - 250),
            "selected_strategy": strategy,
        },
        "days": [],
        "schedule_status": "pending_o6_activity_scheduling",
    }


@pytest.mark.parametrize("days", [7, 13, 30])
def test_arbitrary_horizons_respect_capacity_and_have_no_padding(days):
    result = ActivityScheduler().schedule(pending_plan(days=days))
    assert result["days"]
    assert all(0 < day["total_minutes"] <= 60 for day in result["days"])
    assert all(day["activities"] for day in result["days"])
    assert result["confirmed_horizon_days"] == days


def test_prerequisite_order_and_spaced_review_follow_introduction():
    result = ActivityScheduler().schedule(pending_plan(days=13))
    activity_days = {
        activity["activity_id"]: day["day"]
        for day in result["days"]
        for activity in day["activities"]
    }
    foundation_day = activity_days["f-explain"]
    target_day = min(
        day["day"]
        for day in result["days"]
        for activity in day["activities"]
        if activity["activity_id"].startswith("t-explain")
    )
    assert target_day >= foundation_day
    review_parts = [
        (day["day"], activity)
        for day in result["days"]
        for activity in day["activities"]
        if activity.get("parent_activity_id") == "f-review"
    ]
    assert review_parts
    assert all(day > foundation_day for day, _ in review_parts)
    assert {
        activity["review_offset_days"] for _, activity in review_parts
    }.issubset({1, 3, 7, 14})


def test_short_horizon_retains_unplaceable_review():
    plan = pending_plan(days=1, capacity=300)
    result = ActivityScheduler().schedule(plan)
    review_unscheduled = [
        item
        for item in result["unscheduled_activities"]
        if item["activity_type"] == "review"
    ]
    assert review_unscheduled
    assert all(
        item["reason"] == "review_interval_outside_horizon"
        for item in review_unscheduled
    )


def test_paced_consolidation_adds_only_optional_surplus_work():
    plan = pending_plan(days=7, capacity=90, strategy="paced_consolidation")
    result = ActivityScheduler().schedule(plan)
    assert result["optional_consolidation_activities"]
    assert result["scheduled_optional_minutes"] <= plan["feasibility"][
        "capacity_gap_minutes"
    ]
    assert all(
        activity["optional"] is True
        for activity in result["optional_consolidation_activities"]
    )
    assert {day["day"] for day in result["days"]} == set(range(1, 8))


def test_required_minutes_are_never_silently_dropped():
    plan = pending_plan(days=2, capacity=60)
    result = ActivityScheduler().schedule(plan)
    original = sum(item["estimated_minutes"] for item in plan["activities"])
    scheduled = result["scheduled_required_minutes"]
    unscheduled = sum(
        item["estimated_minutes"] for item in result["unscheduled_activities"]
    )
    assert scheduled + unscheduled == original


class FakeBackend:
    def __init__(self, db_path):
        self.plans = PathlyStore(db_path)
        self.contracts = PathlyContractStore(db_path)


def service_environment(tmp_path):
    backend = FakeBackend(tmp_path / "plans.db")
    plan = pending_plan(days=13)
    v1 = backend.plans.save_plan(
        "schedule-user",
        deepcopy(plan),
        "fallback",
        ["kg_metadata"],
        path_id="path-1",
        goal_text="Learn Target",
        profile_snapshot={"user_id": "schedule-user"},
    )
    backend.contracts.save_path_context(
        v1["plan_id"],
        {
            "path_id": "path-1",
            "user_id": "schedule-user",
            "target_days": 13,
            "max_daily_minutes": 60,
            "status": "awaiting_schedule",
        },
    )
    return backend, v1, ScheduleService(backend)


def test_service_creates_v2_preserves_v1_and_is_idempotent(tmp_path):
    backend, v1, service = service_environment(tmp_path)
    v2 = service.create(user_id="schedule-user", plan_id=v1["plan_id"])
    assert v2["version"] == 2
    assert v2["path_id"] == v1["path_id"]
    assert v2["plan"]["days"]
    assert v1["plan"]["days"] == []
    repeated = service.create(user_id="schedule-user", plan_id=v1["plan_id"])
    assert repeated["plan_id"] == v2["plan_id"]
    assert len(backend.plans.list_plans("schedule-user")) == 2
    with pytest.raises(ScheduleNotFoundError):
        service.get(user_id="other", plan_id=v1["plan_id"])


def test_schedule_api_create_and_restore(monkeypatch, tmp_path):
    backend, v1, service = service_environment(tmp_path)
    monkeypatch.setattr(pathly_server, "schedule_service", service, raising=False)
    client = TestClient(pathly_server.app)
    created = client.post(
        f"/api/plans/{v1['plan_id']}/schedule",
        json={"user_id": "schedule-user"},
    )
    assert created.status_code == 201
    assert created.json()["data"]["version"] == 2
    restored = client.get(
        f"/api/plans/{v1['plan_id']}/schedule?user_id=schedule-user"
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["plan"]["days"]
