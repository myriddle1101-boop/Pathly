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
from agents.concept_expander import ConceptExpander  # noqa: E402
from infra.profile_store import ProfileStore  # noqa: E402
from pathly_backend import PathlyBackend, PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402
from pathly_goal_interpretation import GoalInterpretationStore  # noqa: E402
from verified_golden_sources import GOLDEN_PATH  # noqa: E402
from pathly_onboarding import (  # noqa: E402
    OnboardingDraftNotFoundError,
    OnboardingService,
    OnboardingStore,
    OnboardingValidationError,
)


client = TestClient(pathly_server.app)


FIRST_ANSWERS = {
    "math_situation": "basic_algebra",
    "programming_situation": "small_scripts",
    "abstract_situation": "mixed_representation",
    "logic_situation": "partial_decompose",
    "learning_experience": "some_courses",
    "learning_style": "example",
    "preferred_examples": ["code", "daily_life"],
    "interest_tags": ["education", "natural_language"],
    "pace_preference": "steady",
    "self_regulation": 4,
    "target_familiarity": "never",
    "path_style_override": "use_default",
    "current_confidence": 3,
    "current_anxiety": 2,
}


REPEAT_ANSWERS = {
    "profile_changed": "no",
    "target_familiarity": "applied",
    "path_style_override": "project",
    "current_confidence": 4,
    "current_anxiety": 2,
}


@pytest.fixture()
def onboarding_env(tmp_path):
    profiles = ProfileStore(str(tmp_path / "profiles.db"))
    plans = PathlyStore(tmp_path / "plans.db")
    contracts = PathlyContractStore(plans.db_path)
    backend = PathlyBackend()
    backend.profiles = profiles
    backend.plans = plans
    backend.contracts = contracts
    interpretations = GoalInterpretationStore(plans.db_path)
    store = OnboardingStore(plans.db_path)
    service = OnboardingService(store, backend, interpretations)
    return profiles, plans, contracts, backend, interpretations, store, service


def complete_first_profile(service, user_id="first-user", answers=None, **confirm_kwargs):
    draft = service.create_draft(
        user_id=user_id,
        goal_text="Learn Neural Networks",
        name="Lin",
    )
    updated = service.update_draft(
        user_id=user_id,
        draft_id=draft["draft_id"],
        answers=answers or FIRST_ANSWERS,
        current_step=13,
    )
    confirmed = service.confirm_profile(
        user_id=user_id,
        draft_id=draft["draft_id"],
        **confirm_kwargs,
    )
    return draft, updated, confirmed


def test_first_time_infers_auditable_profile_and_user_override(onboarding_env):
    _, _, _, backend, _, store, service = onboarding_env
    draft = service.create_draft(
        user_id="first-user",
        goal_text="Learn Neural Networks",
        name="Lin",
    )
    assert draft["onboarding_type"] == "first_time"
    assert len(draft["questions"]) == 13
    assert draft["reused_fields"] == []
    assert draft["legacy_constraint_placeholder"] is True
    question_ids = {question["id"] for question in draft["questions"]}
    assert "motivation_level" not in question_ids
    assert {"current_confidence", "current_anxiety"} <= question_ids
    assert "confidence_level" not in question_ids
    assert "anxiety_level" not in question_ids
    assert "interest_tags" in question_ids
    assert "path_style_override" not in question_ids
    assert draft["answers"]["path_style_override"] == "use_default"

    preview = service.update_draft(
        user_id="first-user",
        draft_id=draft["draft_id"],
        answers=FIRST_ANSWERS,
        current_step=12,
    )
    math_record = preview["profile_preview"]["inference_records"]["mathematical_ability"]
    assert preview["profile_preview"]["cognitive_traits"]["mathematical_ability"] == 2
    assert math_record["confidence"] == 0.78
    assert math_record["reason"]
    assert math_record["evidence_source"] == "onboarding_answer:math_situation"
    pace_record = preview["profile_preview"]["inference_records"]["pace_preference"]
    assert pace_record["value"] == "steady"
    assert pace_record["confidence"] == 0.9
    assert pace_record["evidence_source"] == "onboarding_answer:pace_preference"
    assert preview["profile_preview"]["affective_defaults"]["interest_tags"] == [
        "education",
        "natural_language",
    ]
    interest_record = preview["profile_preview"]["inference_records"]["interest_tags"]
    assert interest_record["value"] == ["education", "natural_language"]
    assert interest_record["evidence_source"] == "onboarding_answer:interest_tags"
    assert "daily_minutes" not in preview["profile_preview"]["affective_defaults"]

    confirmed = service.confirm_profile(
        user_id="first-user",
        draft_id=draft["draft_id"],
        cognitive_overrides={"mathematical_ability": 4},
    )
    assert confirmed["status"] == "profile_confirmed"
    assert confirmed["profile_preview"]["cognitive_traits"]["mathematical_ability"] == 4
    override_record = confirmed["profile_preview"]["inference_records"]["mathematical_ability"]
    assert override_record["confidence"] == 1.0
    assert override_record["evidence_source"] == "user_override"
    assert override_record["confirmed"] is True
    persisted = backend.get_profile_record("first-user")
    assert persisted["math_foundation"] == 4
    assert persisted["cognitive_traits"]["mathematical_ability"] == 4
    assert store.get("first-user", draft["draft_id"])["status"] == "profile_confirmed"


def test_repeat_onboarding_reuses_stable_profile_and_keeps_target_mastery_path_specific(
    onboarding_env,
):
    _, _, _, backend, _, _, service = onboarding_env
    _, _, first = complete_first_profile(service, user_id="repeat-user")
    stable_cognitive = first["profile_snapshot"]["cognitive_traits"]
    assert backend.get_profile_record("repeat-user")["profile_version"] == 2
    assert backend.get_profile_record("repeat-user")["mastery_vector"] == {}

    repeat = service.create_draft(
        user_id="repeat-user",
        goal_text="Learn Transformers",
    )
    assert repeat["onboarding_type"] == "repeat"
    assert len(repeat["questions"]) == 4
    assert "cognitive_traits" in repeat["reused_fields"]
    assert repeat["legacy_constraint_placeholder"] is False
    question_ids = {question["id"] for question in repeat["questions"]}
    assert "current_motivation" not in question_ids
    assert {"current_confidence", "current_anxiety"} <= question_ids
    assert "path_style_override" not in question_ids

    service.update_draft(
        user_id="repeat-user",
        draft_id=repeat["draft_id"],
        answers=REPEAT_ANSWERS,
    )
    confirmed = service.confirm_profile(
        user_id="repeat-user",
        draft_id=repeat["draft_id"],
    )
    assert confirmed["profile_snapshot"]["cognitive_traits"] == stable_cognitive
    assert backend.get_profile_record("repeat-user")["profile_version"] == 3
    target_id = repeat["target_terms"][0]
    assert confirmed["path_context_preview"]["target_mastery"][target_id] == 0.8
    mastery_evidence = confirmed["path_context_preview"]["target_mastery_evidence"][
        target_id
    ]
    assert mastery_evidence["value"] == 0.8
    assert mastery_evidence["confidence"] == 0.85
    assert (
        mastery_evidence["evidence_source"]
        == "onboarding_answer:target_familiarity"
    )
    assert confirmed["path_context_preview"]["preference_overrides"] == {
        "activity_style": "project"
    }
    assert confirmed["path_context_preview"]["current_affective_state"] == {
        "motivation": 3,
        "confidence": 4,
        "anxiety": 2,
    }
    # Uploading a new target mastery signal must not claim global mastery.
    assert backend.get_profile_record("repeat-user")["mastery_vector"] == {}


def test_profile_changed_flag_exposes_review_and_allows_stable_override(onboarding_env):
    _, _, _, backend, _, _, service = onboarding_env
    complete_first_profile(service, user_id="changed-user")
    repeat = service.create_draft(
        user_id="changed-user",
        goal_text="Learn Transformers",
    )
    answers = {**REPEAT_ANSWERS, "profile_changed": "yes"}
    preview = service.update_draft(
        user_id="changed-user",
        draft_id=repeat["draft_id"],
        answers=answers,
    )
    assert preview["profile_review_required"] is True
    confirmed = service.confirm_profile(
        user_id="changed-user",
        draft_id=repeat["draft_id"],
        cognitive_overrides={"programming_ability": 5},
    )
    assert confirmed["profile_snapshot"]["programming_foundation"] == 5
    assert backend.get_profile_record("changed-user")["inference_records"][
        "programming_ability"
    ]["evidence_source"] == "user_override"


def test_missing_answers_and_cross_user_access_are_rejected(onboarding_env):
    _, _, _, _, _, store, service = onboarding_env
    draft = service.create_draft(
        user_id="owner",
        goal_text="Learn Neural Networks",
    )
    with pytest.raises(OnboardingValidationError):
        service.confirm_profile(user_id="owner", draft_id=draft["draft_id"])
    assert store.get("other", draft["draft_id"]) is None
    with pytest.raises(OnboardingDraftNotFoundError):
        service.update_draft(
            user_id="other",
            draft_id=draft["draft_id"],
            answers={},
        )
    store.delete("owner", draft["draft_id"])
    assert store.get("owner", draft["draft_id"]) is None


def test_confirmed_goal_interpretation_supplies_microdiagnostic_targets(onboarding_env):
    _, _, _, _, interpretations, _, service = onboarding_env
    interpretation = {
        "interpretation_id": "confirmed-goal",
        "user_id": "interpretation-user",
        "goal_text": "Learn my private topic",
        "source_mode": "private_plus_kg",
        "status": "confirmed",
        "canonical_concepts": [{"concept_id": "Neural Networks"}],
        "private_concepts": [{"private_concept_id": "private:abc"}],
        "confirmation_required": [],
        "kg_source": "json",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    interpretations.save(interpretation, [])
    draft = service.create_draft(
        user_id="interpretation-user",
        goal_text="Learn my private topic",
        goal_interpretation_id="confirmed-goal",
    )
    assert draft["target_terms"] == ["Neural Networks", "private:abc"]

    pending = {**interpretation, "interpretation_id": "pending-goal", "status": "draft"}
    interpretations.save(pending, [])
    with pytest.raises(OnboardingValidationError):
        service.create_draft(
            user_id="interpretation-user",
            goal_text="Learn my private topic",
            goal_interpretation_id="pending-goal",
        )


class WorkloadRepository:
    def get_topic(self, topic):
        return {
            "id": topic,
            "difficulty_level": 4,
            "estimated_learning_time": "100 min",
        }

    def get_prerequisites(self, topic):
        return []


def test_different_confirmed_foundations_change_planning_estimate(onboarding_env):
    _, _, _, backend, _, _, service = onboarding_env
    low_answers = {
        **FIRST_ANSWERS,
        "math_situation": "avoid_formulas",
        "programming_situation": "no_code",
    }
    high_answers = {
        **FIRST_ANSWERS,
        "math_situation": "advanced_math",
        "programming_situation": "advanced_engineering",
    }
    complete_first_profile(service, user_id="low-user", answers=low_answers)
    complete_first_profile(service, user_id="high-user", answers=high_answers)
    expander = ConceptExpander(WorkloadRepository())
    low = expander.expand(
        ["Neural Networks"],
        ["Neural Networks"],
        backend.profiles.get_profile("low-user"),
        requested_days=7,
        available_daily_minutes=90,
    )
    high = expander.expand(
        ["Neural Networks"],
        ["Neural Networks"],
        backend.profiles.get_profile("high-user"),
        requested_days=7,
        available_daily_minutes=90,
    )
    assert (
        low["workload_estimate"]["total_required_minutes"]
        > high["workload_estimate"]["total_required_minutes"]
    )


def test_onboarding_api_can_resume_and_confirm(tmp_path, monkeypatch):
    profiles = ProfileStore(str(tmp_path / "profiles.db"))
    plans = PathlyStore(tmp_path / "plans.db")
    contracts = PathlyContractStore(plans.db_path)
    backend = PathlyBackend()
    backend.profiles = profiles
    backend.plans = plans
    backend.contracts = contracts
    interpretations = GoalInterpretationStore(plans.db_path)
    store = OnboardingStore(plans.db_path)
    service = OnboardingService(store, backend, interpretations)
    monkeypatch.setattr(pathly_server, "backend", backend)
    monkeypatch.setattr(pathly_server, "onboarding_store", store)
    monkeypatch.setattr(pathly_server, "onboarding_service", service)

    created = client.post(
        "/api/onboarding-drafts",
        json={
            "user_id": "api-onboarding",
            "goal_text": "Learn Neural Networks",
            "name": "API Learner",
        },
    )
    assert created.status_code == 201
    draft_id = created.json()["data"]["draft_id"]
    patched = client.patch(
        f"/api/onboarding-drafts/{draft_id}",
        json={
            "user_id": "api-onboarding",
            "answers": FIRST_ANSWERS,
            "current_step": 13,
        },
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["remaining_required"] == []
    resumed = client.get(
        f"/api/onboarding-drafts/{draft_id}",
        params={"user_id": "api-onboarding"},
    )
    assert resumed.json()["data"]["answers"] == FIRST_ANSWERS
    confirmed = client.post(
        f"/api/onboarding-drafts/{draft_id}/confirm-profile",
        json={"user_id": "api-onboarding"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "profile_confirmed"
    listed = client.get("/api/users/api-onboarding/onboarding-drafts")
    assert len(listed.json()["data"]) == 1


def test_knowledge_map_review_persists_exclusions_and_protects_target(tmp_path):
    profiles = ProfileStore(str(tmp_path / "profiles.db"))
    backend = PathlyBackend()
    backend.profiles = profiles
    store = OnboardingStore(tmp_path / "plans.db")
    service = OnboardingService(store, backend)
    draft = service.create_draft(
        user_id="map-review-user", goal_text="Learn Machine Learning"
    )
    saved = service.confirm_knowledge_map(
        user_id="map-review-user",
        draft_id=draft["draft_id"],
        reviewed_concepts=[
            {"concept_id": "Regression", "display_name": "Regression", "is_target": False, "path_role": "prerequisite"},
            {"concept_id": "Machine Learning", "display_name": "Machine Learning", "is_target": True},
        ],
        excluded_concept_ids=["Regression"],
        edges=[{"source": "Regression", "target": "Machine Learning", "type": "sequence_hint"}],
    )
    review = saved["knowledge_map_review"]
    assert review["excluded_concept_ids"] == ["Regression"]
    assert review["included_concept_ids"] == ["Machine Learning"]
    assert review["reviewed_concepts"][0]["path_role"] == "prerequisite"
    assert review["edges"] == []
    assert store.get("map-review-user", draft["draft_id"])["knowledge_map_review"] == review
    with pytest.raises(OnboardingValidationError, match="cannot be excluded"):
        service.confirm_knowledge_map(
            user_id="map-review-user",
            draft_id=draft["draft_id"],
            reviewed_concepts=[{"concept_id": "Machine Learning", "is_target": True}],
            excluded_concept_ids=["Machine Learning"],
            edges=[],
        )


def test_repeat_profile_review_reasks_only_selected_dimensions(onboarding_env):
    _, _, _, backend, _, _, service = onboarding_env
    complete_first_profile(service, user_id="review-user")
    repeat = service.create_draft(user_id="review-user", goal_text="Learn Transformers")
    review_ids = {question["id"] for question in repeat["profile_review_questions"]}
    assert "motivation_level" not in review_ids
    assert {"math_situation", "learning_style", "self_regulation", "interest_tags"} <= review_ids
    assert "confidence_level" not in review_ids
    assert "anxiety_level" not in review_ids

    answers = {
        **REPEAT_ANSWERS,
        "profile_changed": "yes",
        "programming_situation": "advanced_engineering",
    }
    preview = service.update_draft(
        user_id="review-user",
        draft_id=repeat["draft_id"],
        answers=answers,
    )
    assert preview["profile_preview"]["cognitive_traits"]["programming_ability"] == 5
    assert preview["profile_review_changes"] == [
        {
            "answer_id": "programming_situation",
            "dimension": "programming_ability",
            "before": 3,
            "after": 5,
        }
    ]
    confirmed = service.confirm_profile(user_id="review-user", draft_id=repeat["draft_id"])
    assert confirmed["profile_snapshot"]["programming_foundation"] == 5
    record = backend.get_profile_record("review-user")["inference_records"]["programming_ability"]
    assert record["evidence_source"] == "onboarding_answer:programming_situation"


def test_repeat_profile_review_can_update_interest_tags(onboarding_env):
    _, _, _, backend, _, _, service = onboarding_env
    complete_first_profile(service, user_id="interest-review-user")
    repeat = service.create_draft(
        user_id="interest-review-user",
        goal_text="Learn Neural Networks for finance",
    )
    preview = service.update_draft(
        user_id="interest-review-user",
        draft_id=repeat["draft_id"],
        answers={
            **REPEAT_ANSWERS,
            "profile_changed": "yes",
            "interest_tags": ["finance"],
        },
    )
    assert preview["profile_preview"]["affective_defaults"]["interest_tags"] == ["finance"]
    assert preview["profile_review_changes"] == [
        {
            "answer_id": "interest_tags",
            "dimension": "interest_tags",
            "before": ["education", "natural_language"],
            "after": ["finance"],
        }
    ]
    confirmed = service.confirm_profile(
        user_id="interest-review-user",
        draft_id=repeat["draft_id"],
    )
    assert confirmed["profile_snapshot"]["interest_tags"] == ["finance"]
    persisted = backend.get_profile_record("interest-review-user")
    assert persisted["affective_defaults"]["interest_tags"] == ["finance"]
    assert persisted["inference_records"]["interest_tags"]["evidence_source"] == (
        "onboarding_answer:interest_tags"
    )


def test_repeat_profile_review_requires_selection_and_no_clears_review_answers(onboarding_env):
    _, _, _, _, _, _, service = onboarding_env
    complete_first_profile(service, user_id="review-clear-user")
    repeat = service.create_draft(user_id="review-clear-user", goal_text="Learn Transformers")
    required = {**REPEAT_ANSWERS, "profile_changed": "yes"}
    preview = service.update_draft(
        user_id="review-clear-user",
        draft_id=repeat["draft_id"],
        answers=required,
    )
    with pytest.raises(OnboardingValidationError, match="Select at least one profile dimension"):
        service.confirm_profile(user_id="review-clear-user", draft_id=repeat["draft_id"])

    preview = service.update_draft(
        user_id="review-clear-user",
        draft_id=repeat["draft_id"],
        answers={"programming_situation": "advanced_engineering"},
    )
    assert "programming_situation" in preview["answers"]
    preview = service.update_draft(
        user_id="review-clear-user",
        draft_id=repeat["draft_id"],
        answers={"profile_changed": "no"},
    )
    assert "programming_situation" not in preview["answers"]
    assert preview["profile_review_changes"] == []

    with pytest.raises(OnboardingValidationError, match="profile_changed=yes"):
        service.update_draft(
            user_id="review-clear-user",
            draft_id=repeat["draft_id"],
            answers={"math_situation": "advanced_math"},
        )

def test_goal_revision_preserves_profile_and_invalidates_downstream_state(onboarding_env):
    _, _, _, _, _, store, service = onboarding_env
    _, _, confirmed = complete_first_profile(service, user_id="revision-user")
    before_profile = confirmed["profile_snapshot"]
    before_answers = confirmed["answers"]
    confirmed["workload_estimate_id"] = "old-estimate"
    confirmed["workload_estimate"] = {"total_required_minutes": 999}
    confirmed["feasibility_decision_id"] = "old-decision"
    store.save(confirmed)

    revised = service.revise_goal(
        user_id="revision-user",
        draft_id=confirmed["draft_id"],
        goal_text="Learn Retrieval Augmented Generation",
    )

    assert revised["status"] == "profile_confirmed"
    assert revised["goal_text"] == "Learn Retrieval Augmented Generation"
    assert revised["profile_snapshot"] == before_profile
    assert revised["answers"] == before_answers
    assert "workload_estimate_id" not in revised
    assert "workload_estimate" not in revised
    assert "feasibility_decision_id" not in revised


def test_draft_goal_can_be_revised_before_profile_confirmation(onboarding_env):
    _, _, _, _, _, _, service = onboarding_env
    draft = service.create_draft(
        user_id="draft-revision-user",
        goal_text="Learn the old goal",
    )
    updated = service.update_draft(
        user_id="draft-revision-user",
        draft_id=draft["draft_id"],
        answers={"math_situation": "basic_algebra"},
    )
    revised = service.revise_goal(
        user_id="draft-revision-user",
        draft_id=draft["draft_id"],
        goal_text="Learn the revised goal",
    )
    assert revised["status"] == "draft"
    assert revised["goal_text"] == "Learn the revised goal"
    assert revised["answers"] == updated["answers"]
    assert "workload_estimate_id" not in revised
    assert "feasibility_decision_id" not in revised


def test_golden_goal_draft_uses_verified_canonical_chain(onboarding_env):
    _, _, _, _, _, _, service = onboarding_env
    draft = service.create_draft(
        user_id="golden-normal-user",
        goal_text=(
            "I want to understand why XOR is not linearly separable and learn how "
            "neural networks, activation functions, and gradient descent solve this problem."
        ),
    )
    assert draft["target_terms"] == list(GOLDEN_PATH)

    service.update_draft(
        user_id="golden-normal-user",
        draft_id=draft["draft_id"],
        answers=FIRST_ANSWERS,
        current_step=12,
    )
    confirmed = service.confirm_profile(
        user_id="golden-normal-user",
        draft_id=draft["draft_id"],
    )
    assert confirmed["path_context_preview"]["target_terms"] == list(GOLDEN_PATH)
