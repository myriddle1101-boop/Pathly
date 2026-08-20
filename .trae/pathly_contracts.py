"""Versioned Pathly onboarding contracts.

The current PlanningAgent still consumes the legacy LearnerProfile. These
contracts keep that interface readable while Pathly separates stable learner
traits from path-specific goals and capacity constraints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


PROFILE_SCHEMA_VERSION = 2


def _score(value: Any, default: int = 3) -> int:
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return default


@dataclass
class LearnerProfileV2:
    user_id: str
    basic_info: dict[str, Any]
    cognitive_traits: dict[str, Any]
    affective_defaults: dict[str, Any]
    known_topics: list[str] = field(default_factory=list)
    mastery_vector: dict[str, float] = field(default_factory=dict)
    inference_records: dict[str, Any] = field(default_factory=dict)
    profile_version: int = PROFILE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LearningPathContext:
    path_id: str
    user_id: str
    goal_text: str
    target_days: int
    max_daily_minutes: int
    outcome_type: str = "knowledge_and_application"
    target_concepts: list[str] = field(default_factory=list)
    target_mastery: dict[str, float] = field(default_factory=dict)
    deadline: str | None = None
    source_mode: str = "kg_only"
    preference_overrides: dict[str, Any] = field(default_factory=dict)
    current_affective_state: dict[str, Any] = field(default_factory=dict)
    profile_snapshot: dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UserDocument:
    document_id: str
    user_id: str
    display_name: str
    file_type: str
    storage_key: str
    sha256: str
    size_bytes: int
    privacy_scope: str = "private"
    parse_status: str = "pending"
    index_status: str = "pending"
    page_count: int | None = None
    language: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PathDocumentLink:
    path_id: str
    document_id: str
    role: str = "supplementary"
    required: bool = False
    included_sections: list[str] = field(default_factory=list)
    excluded_sections: list[str] = field(default_factory=list)
    source_priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkloadEstimate:
    estimate_id: str
    path_id: str
    concept_minutes: int = 0
    example_minutes: int = 0
    required_reading_minutes: int = 0
    practice_minutes: int = 0
    code_minutes: int = 0
    review_minutes: int = 0
    assessment_minutes: int = 0
    project_minutes: int = 0
    reflection_minutes: int = 0
    activity_minutes: int = 0
    total_required_minutes: int = 0
    estimate_confidence: float = 0.0
    estimate_sources: list[dict[str, Any]] = field(default_factory=list)
    coverage_warnings: list[str] = field(default_factory=list)
    generation_mode: str = "template"
    estimate_scope: str = "complete_activity_workload"
    is_final: bool = False
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def profile_v2_from_legacy(legacy: Any, extension: dict[str, Any] | None = None) -> LearnerProfileV2:
    extension = extension or {}
    cognitive = {
        "mathematical_ability": _score(getattr(legacy, "math_foundation", 3)),
        "programming_ability": _score(getattr(legacy, "programming_foundation", 3)),
        "abstract_thinking": _score(getattr(legacy, "prior_knowledge_level", 3)),
        "logical_reasoning": _score(getattr(legacy, "prior_knowledge_level", 3)),
        "general_learning_foundation": _score(getattr(legacy, "prior_knowledge_level", 3)),
    }
    cognitive.update(extension.get("cognitive_traits") or {})
    affective = {
        "learning_style": getattr(legacy, "preferred_style", "balanced"),
        "preferred_examples": list(getattr(legacy, "preferred_examples", []) or []),
        "pace_preference": getattr(legacy, "pace_preference", "medium"),
        "interest_tags": list(getattr(legacy, "interest_tags", []) or []),
        "motivation_baseline": _score(getattr(legacy, "motivation_level", 3)),
        "confidence_baseline": _score(getattr(legacy, "confidence_level", 3)),
        "anxiety_baseline": _score(getattr(legacy, "anxiety_level", 2), 2),
        "self_regulation": _score(getattr(legacy, "self_regulation", 3)),
    }
    affective.update(extension.get("affective_defaults") or {})
    affective.pop("confidence_baseline", None)
    affective.pop("anxiety_baseline", None)
    affective.pop("daily_time_minutes", None)
    affective.pop("daily_minutes", None)
    return LearnerProfileV2(
        user_id=str(legacy.user_id),
        basic_info={
            "name": getattr(legacy, "name", "Pathly Learner"),
            "academic_level": getattr(legacy, "academic_level", "unspecified"),
            "domain": getattr(legacy, "domain", "user-defined"),
        },
        cognitive_traits=cognitive,
        affective_defaults=affective,
        known_topics=list(getattr(legacy, "known_topics", []) or []),
        mastery_vector=dict(getattr(legacy, "mastery_vector", {}) or {}),
        inference_records=dict(extension.get("inference_records") or {}),
        profile_version=int(extension.get("profile_version") or PROFILE_SCHEMA_VERSION),
    )


def build_path_context(
    *,
    path_id: str,
    user_id: str,
    goal_text: str,
    target_days: int,
    max_daily_minutes: int,
    profile_snapshot: dict[str, Any],
    plan: dict[str, Any] | None = None,
) -> LearningPathContext:
    plan = plan or {}
    return LearningPathContext(
        path_id=path_id,
        user_id=user_id,
        goal_text=goal_text,
        target_days=max(1, int(target_days)),
        max_daily_minutes=max(1, int(max_daily_minutes)),
        target_concepts=list(plan.get("target_topics") or []),
        target_mastery=dict(profile_snapshot.get("mastery_vector") or {}),
        current_affective_state={
            "motivation": profile_snapshot.get("motivation_level", 3),
            "confidence": profile_snapshot.get("confidence_level", 3),
            "anxiety": profile_snapshot.get("anxiety_level", 2),
        },
        profile_snapshot=profile_snapshot,
    )
