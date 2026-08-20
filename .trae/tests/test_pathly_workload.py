from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import pathly_server
from pathly_onboarding import OnboardingStore
from pathly_workload import (
    ActivityPlanner,
    WorkloadService,
    WorkloadStore,
    WorkloadValidationError,
)
from verified_golden_sources import GOLDEN_PATH


CONCEPT_PATH = [
    {
        "concept_id": "Foundation",
        "estimated_total_minutes": 100,
        "source_mode": "json",
        "planning_reason": "Foundation is a required prerequisite.",
    },
    {
        "concept_id": "Target",
        "estimated_total_minutes": 150,
        "source_mode": "json",
        "planning_reason": "Target is the confirmed goal.",
    },
]


def test_activity_planner_consumes_profile_dimensions_without_changing_concepts():
    planner = ActivityPlanner()
    base = {
        "cognitive_traits": {"mathematical_ability": 5, "programming_ability": 5, "abstract_thinking": 5, "logical_reasoning": 5},
        "affective_defaults": {"confidence_baseline": 5, "anxiety_baseline": 1, "learning_style": "mixed", "preferred_examples": ["research"], "pace_preference": "intensive"},
    }
    supported = deepcopy(base)
    supported["cognitive_traits"].update({"mathematical_ability": 1, "programming_ability": 1, "abstract_thinking": 1, "logical_reasoning": 1})
    supported["affective_defaults"].update({"confidence_baseline": 1, "anxiety_baseline": 4, "learning_style": "project", "preferred_examples": ["code"], "pace_preference": "flexible"})
    first = planner._template_activities(deepcopy(CONCEPT_PATH), base, {})
    second = planner._template_activities(deepcopy(CONCEPT_PATH), supported, {})
    totals = lambda rows, kind: sum(row["estimated_minutes"] for row in rows if row["activity_type"] == kind)
    assert {concept for row in first for concept in row["concept_ids"]} == {concept for row in second for concept in row["concept_ids"]}
    assert totals(second, "example") > totals(first, "example")
    assert totals(second, "review") > totals(first, "review")
    assert totals(second, "quiz") > totals(first, "quiz")
    assert totals(second, "project") > totals(first, "project")

PROFILE = {
    "cognitive_traits": {
        "mathematical_ability": 3,
        "programming_ability": 4,
        "abstract_thinking": 3,
        "logical_reasoning": 3,
        "general_learning_foundation": 3,
    },
    "affective_defaults": {
        "learning_style": "mixed",
        "preferred_examples": ["code"],
        "anxiety_baseline": 2,
        "confidence_baseline": 3,
        "self_regulation": 3,
    },
}

CONTEXT = {
    "preference_overrides": {},
    "current_affective_state": {
        "motivation": 4,
        "confidence": 3,
        "anxiety": 2,
    },
}

SOURCES = [
    {
        "source_type": "kg_metadata",
        "source_id": "Foundation",
        "confidence": 0.76,
        "reason": "KG estimated_learning_time",
    },
    {
        "source_type": "kg_metadata",
        "source_id": "Target",
        "confidence": 0.76,
        "reason": "KG estimated_learning_time",
    },
]


def estimate(*, context=None, readings=None, planner=None):
    return (planner or ActivityPlanner()).plan(
        concept_path=deepcopy(CONCEPT_PATH),
        profile_snapshot=deepcopy(PROFILE),
        path_context=deepcopy(context or CONTEXT),
        readings=deepcopy(readings or []),
        estimate_sources=deepcopy(SOURCES),
    )


def test_final_estimate_contains_complete_activity_set_and_sources():
    result = estimate()
    activity_types = {item["activity_type"] for item in result["activities"]}
    assert {
        "explanation",
        "example",
        "practice",
        "code",
        "review",
        "quiz",
        "project",
        "reflection",
    }.issubset(activity_types)
    assert result["is_final"] is True
    assert result["estimate_is_final"] is True
    assert result["estimate_scope"] == "complete_activity_workload"
    assert result["total_required_minutes"] == sum(
        item["estimated_minutes"] for item in result["activities"]
    )
    assert result["total_required_minutes"] > 250
    assert all(item["reason"] for item in result["activities"])
    assert result["estimate_sources"][0]["source_type"] == "kg_metadata"


def test_final_flag_is_rejected_when_no_confirmed_concept_exists():
    with pytest.raises(WorkloadValidationError):
        ActivityPlanner().plan(
            concept_path=[],
            profile_snapshot=deepcopy(PROFILE),
            path_context=deepcopy(CONTEXT),
            readings=[],
            estimate_sources=[],
        )


def test_total_is_independent_of_requested_days():
    ten_day_context = {**CONTEXT, "requested_days": 10}
    thirty_day_context = {**CONTEXT, "requested_days": 30}
    ten = estimate(context=ten_day_context)
    thirty = estimate(context=thirty_day_context)
    assert ten["total_required_minutes"] == thirty["total_required_minutes"]
    assert "requested_days" not in ten
    assert "recommended_daily_minutes" not in ten


def test_preference_changes_activity_mix_and_total_but_not_concept_path():
    theory = estimate(
        context={
            **CONTEXT,
            "preference_overrides": {"activity_style": "theory"},
        }
    )
    project = estimate(
        context={
            **CONTEXT,
            "preference_overrides": {"activity_style": "project"},
        }
    )
    assert theory["total_required_minutes"] != project["total_required_minutes"]
    assert theory["project_minutes"] < project["project_minutes"]
    assert theory["practice_minutes"] < project["practice_minutes"]
    assert any(
        "theory" in item["reason"]
        for item in theory["activities"]
        if item["activity_type"] == "example"
    )
    assert [item["concept_id"] for item in CONCEPT_PATH] == ["Foundation", "Target"]


def test_reference_document_adds_no_time_but_required_scope_is_counted_and_deduped():
    reference = {
        "document_id": "doc-1",
        "display_name": "Notes.pdf",
        "required": False,
        "word_count": 1900,
        "reading_speed_wpm": 190,
        "estimated_minutes": 10,
        "overlap_concept_ids": ["Target"],
        "duplicate_chunk_count": 0,
        "scope": {"included_pages": [1, 2]},
        "source_refs": [{"chunk_id": "chunk-1", "page_start": 1, "page_end": 1}],
        "reason": "Reference-only material adds no independent workload.",
    }
    without_document = estimate()
    reference_result = estimate(readings=[reference])
    assert reference_result["total_required_minutes"] == without_document[
        "total_required_minutes"
    ]
    assert reference_result["required_reading_minutes"] == 0
    assert reference_result["estimate_sources"][-1]["required"] is False

    required = {**reference, "required": True}
    required["reason"] = "Learner confirmed this scope as mandatory."
    required_result = estimate(readings=[required])
    assert required_result["required_reading_minutes"] == 10
    assert required_result["deduplication"]["replaced_explanation_minutes"] == 10
    assert required_result["total_required_minutes"] == without_document[
        "total_required_minutes"
    ]
    reading_activity = next(
        item
        for item in required_result["activities"]
        if item["activity_type"] == "required_reading"
    )
    assert reading_activity["source_refs"][0]["page_start"] == 1


def test_activity_model_failure_uses_explicit_complete_template_fallback():
    def failing_generator(**_kwargs):
        raise RuntimeError("model unavailable")

    result = estimate(planner=ActivityPlanner(failing_generator))
    assert result["is_final"] is True
    assert result["generation_mode"] == "fallback_template"
    assert result["fallback_reason"] == "RuntimeError"
    assert any("deterministic template" in warning for warning in result["coverage_warnings"])


def test_workload_store_persists_and_enforces_owner(tmp_path):
    store = WorkloadStore(tmp_path / "pathly.db")
    payload = {
        "estimate_id": "estimate-1",
        "path_id": "onboarding:draft-1",
        "draft_id": "draft-1",
        "user_id": "owner",
        "mode": "fallback",
        "total_required_minutes": 500,
    }
    store.save(payload)
    assert store.get("owner", "estimate-1")["total_required_minutes"] == 500
    assert store.get("other-user", "estimate-1") is None
    assert store.latest_for_draft("owner", "draft-1")["estimate_id"] == "estimate-1"


class FakeProfiles:
    def get_profile(self, user_id):
        if user_id != "workload-user":
            return None
        from infra.profile_schema import LearnerProfile

        return LearnerProfile(
            user_id=user_id,
            name="Workload User",
            academic_level="unspecified",
            domain="test",
            goal_text="Learn Target",
            target_days=7,
            daily_minutes=75,
            prior_knowledge_level=3,
            math_foundation=3,
            programming_foundation=4,
            self_regulation=3,
            motivation_level=4,
            confidence_level=3,
            anxiety_level=2,
            preferred_examples=["code"],
            pace_preference="medium",
        )


class FakeBackend:
    profiles = FakeProfiles()


class FakeInterpretations:
    def get(self, _user_id, _interpretation_id):
        return None

    def evidence(self, _user_id, _interpretation_id):
        return []


class FakeDocuments:
    def get_document(self, _user_id, _document_id):
        return None

    def get_chunks(self, _user_id, _document_id):
        return []


def service_environment(tmp_path):
    onboarding = OnboardingStore(tmp_path / "pathly.db")
    store = WorkloadStore(tmp_path / "pathly.db")
    draft = {
        "draft_id": "draft-1",
        "user_id": "workload-user",
        "onboarding_type": "repeat",
        "status": "profile_confirmed",
        "current_step": 6,
        "goal_text": "Learn Target",
        "goal_interpretation_id": None,
        "target_terms": ["Target"],
        "profile_snapshot": deepcopy(PROFILE),
        "path_context_preview": deepcopy(CONTEXT)
        | {"target_mastery": {"Target": 0.2}},
    }
    onboarding.save(draft)
    service = WorkloadService(
        store=store,
        onboarding_store=onboarding,
        backend=FakeBackend(),
        goal_interpretations=FakeInterpretations(),
        documents=FakeDocuments(),
    )
    service._build_concept_path = lambda _profile, _terms, **_kwargs: {
        "concept_path": deepcopy(CONCEPT_PATH),
        "concept_units": [],
        "kg_source": "json",
        "estimate_sources": deepcopy(SOURCES),
        "coverage_warnings": [],
    }
    return onboarding, store, service


def test_service_and_api_require_confirmation_persist_and_restore(monkeypatch, tmp_path):
    onboarding, store, service = service_environment(tmp_path)
    result = service.generate(user_id="workload-user", draft_id="draft-1")
    assert result["is_final"] is True
    assert result["mode"] == "fallback"
    assert store.get("workload-user", result["estimate_id"]) is not None
    draft = onboarding.get("workload-user", "draft-1")
    assert draft["status"] == "profile_confirmed"
    assert draft["workload_estimate"]["estimate_is_final"] is True

    monkeypatch.setattr(pathly_server, "onboarding_store", onboarding)
    monkeypatch.setattr(pathly_server, "workload_store", store)
    monkeypatch.setattr(pathly_server, "workload_service", service)
    client = TestClient(pathly_server.app)
    created = client.post(
        "/api/onboarding-drafts/draft-1/workload-estimates",
        json={"user_id": "workload-user"},
    )
    assert created.status_code == 201
    estimate_id = created.json()["data"]["estimate_id"]
    restored = client.get(
        f"/api/workload-estimates/{estimate_id}?user_id=workload-user"
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["total_required_minutes"] > 0
    assert client.get(
        f"/api/workload-estimates/{estimate_id}?user_id=other"
    ).status_code == 404

    unconfirmed = onboarding.get("workload-user", "draft-1")
    unconfirmed["status"] = "draft"
    onboarding.save(unconfirmed)
    rejected = client.post(
        "/api/onboarding-drafts/draft-1/workload-estimates",
        json={"user_id": "workload-user"},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "workload_estimate_unavailable"


def test_confirmed_map_exclusion_reduces_workload_and_removes_scheduled_concept(tmp_path):
    onboarding, _, service = service_environment(tmp_path)
    baseline = service.generate(user_id="workload-user", draft_id="draft-1")
    draft = onboarding.get("workload-user", "draft-1")
    draft.pop("workload_estimate_id", None)
    draft.pop("workload_estimate", None)
    draft["knowledge_map_review"] = {
        "status": "confirmed",
        "reviewed_concepts": [
            {"concept_id": "Foundation", "is_target": False},
            {"concept_id": "Target", "is_target": True},
        ],
        "included_concept_ids": ["Target"],
        "excluded_concept_ids": ["Foundation"],
        "edges": [],
    }
    onboarding.save(draft)
    filtered = service.generate(user_id="workload-user", draft_id="draft-1")
    assert [item["concept_id"] for item in filtered["concept_path"]] == ["Target"]
    assert filtered["total_required_minutes"] < baseline["total_required_minutes"]
    assert all("Foundation" not in item.get("concept_ids", []) for item in filtered["activities"])

    from pathly_scheduler import ActivityScheduler

    scheduled_input = deepcopy(filtered)
    scheduled_input["feasibility"] = {
        "requested_days": 10,
        "effective_days": 10,
        "max_available_daily_minutes": 120,
        "capacity_gap_minutes": 1000,
        "selected_strategy": "proceed",
    }
    result = ActivityScheduler().schedule(scheduled_input)
    scheduled_activities = [activity for day in result["days"] for activity in day["activities"]]
    assert scheduled_activities
    assert all("Foundation" not in item.get("concept_ids", []) for item in scheduled_activities)


def test_private_concept_display_name_is_carried_into_concept_path():
    concept_result = {
        "concept_path": [
            {"concept_id": "private:abc", "title": "private:abc"},
            {"concept_id": "Canonical", "title": "Canonical"},
        ]
    }
    interpretation = {
        "private_concepts": [
            {
                "private_concept_id": "private:abc",
                "display_name": "Tool Planner",
                "requested_term": "Tool Planner",
            }
        ]
    }

    WorkloadService._apply_private_concept_names(concept_result, interpretation)

    assert concept_result["concept_path"][0]["title"] == "Tool Planner"
    assert concept_result["concept_path"][0]["display_name"] == "Tool Planner"
    assert concept_result["concept_path"][1]["title"] == "Canonical"


def test_verified_goal_scope_preserves_golden_chain_when_neo4j_path_is_sparse(monkeypatch, tmp_path):
    class FakeRepository:
        def get_topic(self, term):
            if term == "XOR":
                return None
            return {"id": term}

        def get_dependents(self, _target):
            return ["AI Applications"]

        def get_similar(self, _target, limit=6):
            return [{"name": "Machine Learning"}]

    class FakePathPlanner:
        def plan(self, *, targets, known_topics, algorithm):
            return {
                "ordered_topics": ["Neural Networks", "AI Applications"],
                "covered_prerequisites": [],
            }

    class FakePlanner:
        repository = FakeRepository()
        path_planner = FakePathPlanner()

        def __init__(self, *args, **kwargs):
            pass

        def build_learner_state(self, _profile):
            return {"excluded_topics": []}

        def prioritize_topics_for_learner(self, *, ordered_topics, covered_prerequisites, profile):
            return {"ordered_topics": ordered_topics}

        class concept_expander:
            @staticmethod
            def expand(*, ordered_topics, target_topics, profile, requested_days, available_daily_minutes):
                return {
                    "concept_path": [
                        {
                            "concept_id": "Neural Networks",
                            "title": "Neural Networks",
                            "estimated_total_minutes": 90,
                            "planning_reason": "Sparse Neo4j result.",
                            "source_mode": "neo4j",
                            "units": [],
                        },
                        {
                            "concept_id": "AI Applications",
                            "title": "AI Applications",
                            "estimated_total_minutes": 80,
                            "planning_reason": "Noisy neighbor.",
                            "source_mode": "neo4j",
                            "units": [],
                        },
                    ],
                    "concept_units": [],
                    "coverage_warnings": [],
                }

    monkeypatch.setenv("NEO4J_PASSWORD", "test")
    monkeypatch.setattr("pathly_workload.PlanningAgent", FakePlanner)
    service = WorkloadService(
        store=WorkloadStore(tmp_path / "pathly.db"),
        onboarding_store=OnboardingStore(tmp_path / "pathly.db"),
        backend=FakeBackend(),
        goal_interpretations=FakeInterpretations(),
        documents=FakeDocuments(),
    )
    profile = FakeProfiles().get_profile("workload-user")
    result = service._build_concept_path(profile, list(GOLDEN_PATH))

    assert [item["concept_id"] for item in result["concept_path"]] == list(GOLDEN_PATH)
    assert result["kg_source"] == "neo4j"
    assert result["verified_goal_scope"]["status"] == "applied"
    assert all(item["verified_public_source_reusable"] for item in result["concept_path"])
    assert "AI Applications" not in [item["concept_id"] for item in result["concept_path"]]


def test_concept_roles_keep_true_prerequisites_before_supporting_and_target_last():
    result = {
        "concept_path": [
            {"concept_id": "Artificial Intelligence", "is_target": False, "prerequisite_ids": []},
            {"concept_id": "Machine Learning", "is_target": True, "prerequisite_ids": ["Artificial Intelligence"]},
            {"concept_id": "Deep Learning", "is_target": False, "prerequisite_ids": ["Machine Learning"], "estimated_total_minutes": 90},
        ]
    }
    WorkloadService._normalize_concept_roles_and_order(result)
    assert [item["concept_id"] for item in result["concept_path"]] == [
        "Artificial Intelligence", "Deep Learning", "Machine Learning"
    ]
    assert [item["path_role"] for item in result["concept_path"]] == [
        "prerequisite", "supporting", "target"
    ]
    assert result["concept_path"][1]["prerequisite_ids"] == []
    assert "not claimed as a required prerequisite" in result["concept_path"][1]["planning_reason"]


def test_activity_display_names_do_not_expose_private_ids():
    activities = [
        {
            "title": "Explanation: private:abc",
            "reason": "Practice for private:abc.",
        }
    ]
    concept_path = [
        {
            "concept_id": "private:abc",
            "display_name": "Tool Planner",
            "title": "Tool Planner",
        }
    ]

    ActivityPlanner._apply_concept_display_names(activities, concept_path)

    assert activities[0]["title"] == "Explanation: Tool Planner"
    assert activities[0]["reason"] == "Practice for Tool Planner."
    assert "private:" not in str(activities)
