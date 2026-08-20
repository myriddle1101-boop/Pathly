from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

import pathly_server
from pathly_backend import PathlyStore
from pathly_contract_store import PathlyContractStore
from pathly_feasibility import (
    CapacityNegotiator,
    FeasibilityService,
    FeasibilityStore,
    FeasibilityValidationError,
)
from pathly_onboarding import OnboardingStore
from pathly_workload import WorkloadStore


def final_estimate(user_id="capacity-user", draft_id="draft-1"):
    activities = [
        {
            "activity_id": "foundation-explanation",
            "activity_type": "explanation",
            "concept_ids": ["Foundation"],
            "estimated_minutes": 400,
            "reason": "Learn the prerequisite.",
            "source": "kg",
        },
        {
            "activity_id": "target-explanation",
            "activity_type": "explanation",
            "concept_ids": ["Target"],
            "estimated_minutes": 300,
            "reason": "Learn the target.",
            "source": "kg",
        },
        {
            "activity_id": "target-practice",
            "activity_type": "practice",
            "concept_ids": ["Target"],
            "estimated_minutes": 300,
            "reason": "Apply the target.",
            "source": "profile_rule",
        },
    ]
    return {
        "estimate_id": "estimate-1",
        "path_id": f"onboarding:{draft_id}",
        "draft_id": draft_id,
        "user_id": user_id,
        "goal_text": "Learn Target",
        "source_mode": "kg_only",
        "mode": "fallback",
        "is_final": True,
        "estimate_is_final": True,
        "total_required_minutes": 1000,
        "concept_path": [
            {
                "concept_id": "Foundation",
                "is_target": False,
                "prerequisite_ids": [],
                "estimated_total_minutes": 400,
            },
            {
                "concept_id": "Target",
                "is_target": True,
                "prerequisite_ids": ["Foundation"],
                "estimated_total_minutes": 600,
            },
        ],
        "activities": activities,
        "estimate_sources": [{"source_type": "kg_metadata"}],
        "coverage_warnings": [],
        "reason": "Final activity workload.",
    }


def test_1000_minutes_over_10_days_with_60_daily_has_exact_gap():
    result = CapacityNegotiator().evaluate(
        total_required_minutes=1000,
        requested_days=10,
        max_available_daily_minutes=60,
    )
    assert result["recommended_daily_minutes"] == 100
    assert result["available_capacity_minutes"] == 600
    assert result["capacity_gap_minutes"] == -400
    assert result["minimum_recommended_days"] == 17
    assert result["status"] == "insufficient"
    assert "400 minutes" in result["status_reason"]


def test_total_is_shown_before_daily_capacity_is_collected():
    result = CapacityNegotiator().evaluate(
        total_required_minutes=1000,
        requested_days=13,
        max_available_daily_minutes=None,
    )
    assert result["recommended_daily_minutes"] == 77
    assert result["status"] == "capacity_pending"
    assert result["available_capacity_minutes"] is None


def test_deadline_is_converted_to_inclusive_calendar_days():
    negotiator = CapacityNegotiator(today_provider=lambda: date(2026, 7, 24))
    days, deadline, mode = negotiator.requested_days(
        requested_days=None,
        deadline="2026-08-02",
    )
    assert days == 10
    assert deadline == "2026-08-02"
    assert mode == "deadline"


def test_four_capacity_statuses_preserve_exact_minutes():
    negotiator = CapacityNegotiator()
    cases = [
        (70, "comfortable", 200),
        (60, "feasible", 100),
        (52, "tight", 20),
        (49, "insufficient", -10),
    ]
    for daily, expected, gap in cases:
        result = negotiator.evaluate(
            total_required_minutes=500,
            requested_days=10,
            max_available_daily_minutes=daily,
        )
        assert result["status"] == expected
        assert result["capacity_gap_minutes"] == gap


class FakeBackend:
    def __init__(self, db_path):
        self.plans = PathlyStore(db_path)
        self.contracts = PathlyContractStore(db_path)


class FakeInterpretations:
    def get(self, _user_id, _interpretation_id):
        return None


class FakeDocuments:
    def get_document(self, _user_id, _document_id):
        return None


def environment(tmp_path):
    db_path = tmp_path / "pathly.db"
    workloads = WorkloadStore(db_path)
    workloads.save(final_estimate())
    onboarding = OnboardingStore(db_path)
    onboarding.save(
        {
            "draft_id": "draft-1",
            "user_id": "capacity-user",
            "status": "profile_confirmed",
            "onboarding_type": "repeat",
            "current_step": 6,
            "goal_text": "Learn Target",
            "goal_interpretation_id": None,
            "profile_snapshot": {
                "user_id": "capacity-user",
                "cognitive_traits": {"programming_ability": 3},
            },
            "path_context_preview": {
                "target_mastery": {"Target": 0.2},
                "preference_overrides": {"activity_style": "project"},
                "current_affective_state": {"confidence": 3, "anxiety": 2},
            },
        }
    )
    store = FeasibilityStore(db_path)
    service = FeasibilityService(
        store=store,
        workload_store=workloads,
        onboarding_store=onboarding,
        backend=FakeBackend(db_path),
        goal_interpretations=FakeInterpretations(),
        documents=FakeDocuments(),
    )
    return db_path, workloads, onboarding, store, service


def test_arbitrary_days_can_be_saved_then_capacity_added(tmp_path):
    _, _, _, _, service = environment(tmp_path)
    decision = service.create(
        user_id="capacity-user",
        estimate_id="estimate-1",
        requested_days=13,
    )
    assert decision["status"] == "capacity_pending"
    assert decision["recommended_daily_minutes"] == 77
    updated = service.update(
        user_id="capacity-user",
        decision_id=decision["decision_id"],
        max_available_daily_minutes=80,
        selected_strategy="proceed",
    )
    assert updated["status"] == "tight"
    assert updated["capacity_gap_minutes"] == 40


def test_scope_change_is_separate_requires_acceptance_and_protects_prerequisites(
    tmp_path,
):
    _, _, _, _, service = environment(tmp_path)
    decision = service.create(
        user_id="capacity-user",
        estimate_id="estimate-1",
        requested_days=10,
        max_available_daily_minutes=60,
    )
    with pytest.raises(FeasibilityValidationError, match="prerequisite"):
        service.update(
            user_id="capacity-user",
            decision_id=decision["decision_id"],
            selected_strategy="narrow_scope",
            scope_remove_concept_ids=["Foundation"],
        )
    proposed = service.update(
        user_id="capacity-user",
        decision_id=decision["decision_id"],
        selected_strategy="narrow_scope",
        scope_remove_concept_ids=["Target"],
    )
    assert proposed["scope_change_draft"]["status"] == "pending"
    assert proposed["scope_change_draft"]["proposed_total_minutes"] == 400
    assert proposed["effective_total_minutes"] == 1000
    assert proposed["status"] == "insufficient"
    with pytest.raises(FeasibilityValidationError, match="scope change"):
        service.confirm(
            user_id="capacity-user",
            decision_id=decision["decision_id"],
        )
    accepted = service.update(
        user_id="capacity-user",
        decision_id=decision["decision_id"],
        scope_change_decision="accept",
    )
    assert accepted["effective_total_minutes"] == 400
    assert accepted["status"] == "comfortable"


def test_rejecting_scope_change_preserves_original_goal_and_total(tmp_path):
    _, _, _, _, service = environment(tmp_path)
    decision = service.create(
        user_id="capacity-user",
        estimate_id="estimate-1",
        requested_days=10,
        max_available_daily_minutes=60,
    )
    proposed = service.update(
        user_id="capacity-user",
        decision_id=decision["decision_id"],
        selected_strategy="narrow_scope",
        scope_remove_concept_ids=["Target"],
    )
    rejected = service.update(
        user_id="capacity-user",
        decision_id=proposed["decision_id"],
        scope_change_decision="reject",
        selected_strategy="save_draft",
    )
    assert rejected["scope_change_draft"]["status"] == "rejected"
    assert rejected["effective_total_minutes"] == 1000
    assert rejected["status"] == "insufficient"


def test_confirmation_creates_plan_v1_only_after_explicit_feasible_decision(
    tmp_path,
):
    db_path, _, onboarding, store, service = environment(tmp_path)
    insufficient = service.create(
        user_id="capacity-user",
        estimate_id="estimate-1",
        requested_days=10,
        max_available_daily_minutes=60,
    )
    with pytest.raises(FeasibilityValidationError, match="Capacity"):
        service.confirm(
            user_id="capacity-user",
            decision_id=insufficient["decision_id"],
        )
    updated = service.update(
        user_id="capacity-user",
        decision_id=insufficient["decision_id"],
        requested_days=17,
        selected_strategy="extend_days",
    )
    assert updated["status"] == "tight"
    result = service.confirm(
        user_id="capacity-user",
        decision_id=updated["decision_id"],
    )
    assert result["decision"]["status"] == "confirmed"
    assert result["plan"]["version"] == 1
    assert result["plan"]["plan"]["days"] == []
    assert result["plan"]["plan"]["schedule_status"] == "pending_o6_activity_scheduling"
    assert result["path_context"]["target_days"] == 17
    assert result["path_context"]["max_daily_minutes"] == 60
    assert onboarding.get("capacity-user", "draft-1")["status"] == "path_confirmed"
    assert len(PathlyStore(db_path).list_plans("capacity-user")) == 1
    assert store.get("capacity-user", updated["decision_id"])["plan_id"]


def test_api_create_patch_get_and_confirm(monkeypatch, tmp_path):
    _, _, onboarding, store, service = environment(tmp_path)
    monkeypatch.setattr(pathly_server, "onboarding_store", onboarding)
    monkeypatch.setattr(pathly_server, "feasibility_store", store, raising=False)
    monkeypatch.setattr(pathly_server, "feasibility_service", service, raising=False)
    client = TestClient(pathly_server.app)
    created = client.post(
        "/api/feasibility-decisions",
        json={
            "user_id": "capacity-user",
            "estimate_id": "estimate-1",
            "requested_days": 10,
            "max_available_daily_minutes": 100,
        },
    )
    assert created.status_code == 201
    decision_id = created.json()["data"]["decision_id"]
    patched = client.patch(
        f"/api/feasibility-decisions/{decision_id}",
        json={"user_id": "capacity-user", "selected_strategy": "proceed"},
    )
    assert patched.status_code == 200
    restored = client.get(
        f"/api/feasibility-decisions/{decision_id}?user_id=capacity-user"
    )
    assert restored.status_code == 200
    confirmed = client.post(
        f"/api/feasibility-decisions/{decision_id}/confirm",
        json={"user_id": "capacity-user"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["plan"]["version"] == 1
    assert client.get(
        f"/api/feasibility-decisions/{decision_id}?user_id=other"
    ).status_code == 404


def test_extend_options_always_include_a_valid_future_day():
    negotiator = CapacityNegotiator()
    tight = negotiator.evaluate(
        total_required_minutes=210,
        requested_days=10,
        max_available_daily_minutes=21,
    )
    tight_options = negotiator.options({**tight, "effective_total_minutes": 210})
    tight_extend = next(item for item in tight_options if item["strategy"] == "extend_days")
    assert tight_extend["suggested_days"] == 11
    assert tight_extend["suggested_days"] > tight["requested_days"]

    feasible = negotiator.evaluate(
        total_required_minutes=210,
        requested_days=11,
        max_available_daily_minutes=21,
    )
    feasible_options = negotiator.options({**feasible, "effective_total_minutes": 210})
    feasible_extend = next(item for item in feasible_options if item["strategy"] == "extend_days")
    assert feasible_extend["suggested_days"] == 13
    assert feasible_extend["suggested_days"] > feasible["requested_days"]

    maximum = negotiator.evaluate(
        total_required_minutes=60,
        requested_days=60,
        max_available_daily_minutes=1,
    )
    maximum_options = negotiator.options({**maximum, "effective_total_minutes": 60})
    assert all(item["strategy"] != "extend_days" for item in maximum_options)

def test_decision_is_linked_to_draft_and_restored_by_estimate(tmp_path):
    _, _, onboarding, store, service = environment(tmp_path)
    decision = service.create(
        user_id="capacity-user",
        estimate_id="estimate-1",
        requested_days=13,
        max_available_daily_minutes=80,
    )
    draft = onboarding.get("capacity-user", "draft-1")
    assert draft["feasibility_decision_id"] == decision["decision_id"]
    restored = store.latest_for_estimate("capacity-user", "estimate-1")
    assert restored["decision_id"] == decision["decision_id"]
    assert store.latest_for_estimate("other-user", "estimate-1") is None




def test_comfortable_strategy_options_explain_time_allocation():
    negotiator = CapacityNegotiator()
    decision = negotiator.evaluate(
        total_required_minutes=245,
        requested_days=10,
        max_available_daily_minutes=60,
    )
    options = {
        item["strategy"]: item
        for item in negotiator.options({**decision, "effective_total_minutes": 245})
    }
    paced = options["paced_consolidation"]
    assert paced["required_daily_minutes"] == 25
    assert paced["daily_capacity_minutes"] == 60
    assert paced["horizon_days"] == 10
    assert paced["optional_consolidation_budget_minutes"] == 355

    early = options["early_completion"]
    assert early["suggested_days"] == 5
    assert early["required_daily_minutes"] == 49
    assert early["freed_days"] == 5

    proceed = options["proceed"]
    assert proceed["required_daily_minutes"] == 25
    assert proceed["unused_capacity_minutes"] == 355

def test_save_draft_is_not_offered_because_onboarding_auto_saves():
    negotiator = CapacityNegotiator()
    decisions = [
        {**negotiator.evaluate(total_required_minutes=500, requested_days=10, max_available_daily_minutes=None), "effective_total_minutes": 500},
        {**negotiator.evaluate(total_required_minutes=500, requested_days=10, max_available_daily_minutes=40), "effective_total_minutes": 500},
        {**negotiator.evaluate(total_required_minutes=500, requested_days=10, max_available_daily_minutes=52), "effective_total_minutes": 500},
        {**negotiator.evaluate(total_required_minutes=500, requested_days=10, max_available_daily_minutes=60), "effective_total_minutes": 500},
        {**negotiator.evaluate(total_required_minutes=500, requested_days=10, max_available_daily_minutes=70), "effective_total_minutes": 500},
    ]
    for decision in decisions:
        assert "save_draft" not in {option["strategy"] for option in negotiator.options(decision)}
