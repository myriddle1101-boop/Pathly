"""Final, activity-level workload estimation for Pathly onboarding.

O4 deliberately estimates the work required to reach a goal before O5 asks
the learner to choose a duration or daily capacity.  The estimator is
deterministic by default, records every source, and can fall back to its
template policy if an optional model-backed activity generator fails.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pathly_backend import CALIBRATED_KG, GLOBAL_KG, PathlyBackend
from pathly_documents import PrivateDocumentStore
from pathly_goal_interpretation import GoalInterpretationStore
from pathly_onboarding import OnboardingDraftNotFoundError, OnboardingStore
from verified_golden_sources import GOLDEN_PATH, verified_goal_concepts_for_goal
from goal_chain_catalog import resolve_goal_chain

from agents.planning_agent import PlanningAgent


class WorkloadValidationError(ValueError):
    pass


class WorkloadEstimateNotFoundError(KeyError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round_minutes(value: float, *, minimum: int = 5) -> int:
    if value <= 0:
        return 0
    return max(minimum, int(math.ceil(value / 5.0) * 5))


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


class WorkloadStore:
    """Persists immutable estimate snapshots in the existing O0 table."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workload_estimates (
                    estimate_id TEXT PRIMARY KEY,
                    path_id TEXT NOT NULL,
                    estimate_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workload_estimates_path
                    ON workload_estimates(path_id, updated_at DESC);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, estimate: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        payload = dict(estimate)
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workload_estimates(
                    estimate_id, path_id, estimate_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(estimate_id) DO UPDATE SET
                    estimate_json=excluded.estimate_json,
                    updated_at=excluded.updated_at
                """,
                (
                    payload["estimate_id"],
                    payload["path_id"],
                    json.dumps(payload, ensure_ascii=False),
                    payload["created_at"],
                    now,
                ),
            )
        return payload

    def get(self, user_id: str, estimate_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT estimate_json FROM workload_estimates WHERE estimate_id = ?",
                (estimate_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["estimate_json"])
        return payload if payload.get("user_id") == user_id else None

    def latest_for_draft(self, user_id: str, draft_id: str) -> dict[str, Any] | None:
        path_id = f"onboarding:{draft_id}"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT estimate_json FROM workload_estimates
                WHERE path_id = ? ORDER BY updated_at DESC
                """,
                (path_id,),
            ).fetchall()
        for row in rows:
            payload = json.loads(row["estimate_json"])
            if payload.get("user_id") == user_id:
                return payload
        return None


class ActivityPlanner:
    """Turns source-grounded concept minutes into a complete activity mix."""

    def __init__(
        self,
        activity_generator: Callable[..., list[dict[str, Any]]] | None = None,
    ):
        self.activity_generator = activity_generator

    def plan(
        self,
        *,
        concept_path: list[dict[str, Any]],
        profile_snapshot: dict[str, Any],
        path_context: dict[str, Any],
        readings: list[dict[str, Any]],
        estimate_sources: list[dict[str, Any]],
        coverage_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        warnings = list(coverage_warnings or [])
        if not concept_path:
            raise WorkloadValidationError(
                "A final workload requires at least one confirmed concept"
            )
        generation_mode = "template"
        fallback_reason = None
        if self.activity_generator:
            try:
                generated = self.activity_generator(
                    concept_path=concept_path,
                    profile_snapshot=profile_snapshot,
                    path_context=path_context,
                    readings=readings,
                )
                if not isinstance(generated, list) or not generated:
                    raise ValueError("activity generator returned no activities")
                activities = self._validated_generated_activities(generated)
                generation_mode = "live_model"
            except Exception as exc:
                activities = self._template_activities(
                    concept_path, profile_snapshot, path_context
                )
                generation_mode = "fallback_template"
                fallback_reason = type(exc).__name__
                warnings.append(
                    "Activity model was unavailable; a deterministic template "
                    "produced the complete estimate."
                )
        else:
            activities = self._template_activities(
                concept_path, profile_snapshot, path_context
            )

        reading_activities, reading_sources = self._reading_activities(readings)
        activities.extend(reading_activities)
        estimate_sources.extend(reading_sources)
        deduplication = self._deduplicate_required_reading(activities, readings)
        self._apply_concept_display_names(activities, concept_path)

        totals = {
            "concept_minutes": 0,
            "example_minutes": 0,
            "practice_minutes": 0,
            "code_minutes": 0,
            "required_reading_minutes": 0,
            "review_minutes": 0,
            "assessment_minutes": 0,
            "project_minutes": 0,
            "reflection_minutes": 0,
        }
        bucket = {
            "explanation": "concept_minutes",
            "example": "example_minutes",
            "practice": "practice_minutes",
            "code": "code_minutes",
            "required_reading": "required_reading_minutes",
            "review": "review_minutes",
            "quiz": "assessment_minutes",
            "project": "project_minutes",
            "reflection": "reflection_minutes",
        }
        for activity in activities:
            totals[bucket[activity["activity_type"]]] += int(
                activity["estimated_minutes"]
            )

        total = sum(totals.values())
        concept_source_confidences = [
            float(item.get("confidence", 0.5))
            for item in estimate_sources
            if item.get("source_type") in {"kg_metadata", "private_concept_template"}
        ]
        document_confidences = [
            float(item.get("confidence", 0.75))
            for item in estimate_sources
            if item.get("source_type") == "document_word_count"
        ]
        confidence_values = concept_source_confidences + document_confidences
        confidence = (
            round(sum(confidence_values) / len(confidence_values), 3)
            if confidence_values
            else 0.5
        )
        return {
            **totals,
            "activity_minutes": total,
            "total_required_minutes": total,
            "estimate_scope": "complete_activity_workload",
            "estimate_is_final": True,
            "is_final": True,
            "estimate_confidence": confidence,
            "estimate_sources": estimate_sources,
            "coverage_warnings": list(dict.fromkeys(warnings)),
            "generation_mode": generation_mode,
            "fallback_reason": fallback_reason,
            "activities": activities,
            "activity_mix": self._activity_mix(totals, total),
            "deduplication": deduplication,
            "reason": (
                "Final workload includes explanation, examples, practice, code, "
                "required reading, review, quiz, project, and reflection. It is "
                "calculated before duration or daily capacity is negotiated."
            ),
        }

    @staticmethod
    def _apply_concept_display_names(
        activities: list[dict[str, Any]],
        concept_path: list[dict[str, Any]],
    ) -> None:
        labels = {
            str(node.get("concept_id")): str(
                node.get("display_name")
                or node.get("title")
                or node.get("concept_id")
            )
            for node in concept_path
            if node.get("concept_id")
        }
        for activity in activities:
            for field in ("title", "reason"):
                text = str(activity.get(field) or "")
                for concept_id, display_name in labels.items():
                    if concept_id.startswith("private:"):
                        text = text.replace(concept_id, display_name)
                activity[field] = text


    def _template_activities(
        self,
        concept_path: list[dict[str, Any]],
        profile: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cognitive = profile.get("cognitive_traits") or {}
        affective = profile.get("affective_defaults") or {}
        preference = {
            **affective,
            **(context.get("preference_overrides") or {}),
        }
        current = context.get("current_affective_state") or {}
        style = str(
            preference.get("activity_style")
            or preference.get("learning_style")
            or profile.get("preferred_style")
            or "mixed"
        ).lower()
        examples = {
            _normalized(item)
            for item in (
                preference.get("preferred_examples")
                or profile.get("preferred_examples")
                or []
            )
        }
        programming = int(
            cognitive.get("programming_ability")
            or profile.get("programming_foundation")
            or 3
        )
        mathematical = int(cognitive.get("mathematical_ability") or profile.get("math_foundation") or 3)
        abstract = int(cognitive.get("abstract_thinking") or profile.get("prior_knowledge_level") or 3)
        logical = int(cognitive.get("logical_reasoning") or profile.get("prior_knowledge_level") or 3)
        pace = str(preference.get("pace_preference") or profile.get("pace_preference") or "steady").lower()
        anxiety = int(
            current.get("anxiety")
            or affective.get("anxiety_baseline")
            or profile.get("anxiety_level")
            or 2
        )
        confidence = int(
            current.get("confidence")
            or affective.get("confidence_baseline")
            or profile.get("confidence_level")
            or 3
        )
        self_regulation = int(
            affective.get("self_regulation")
            or profile.get("self_regulation")
            or 3
        )

        example_factor = 0.28 if style in {"example", "visual"} else 0.18
        if style in {"theory", "theoretical"}:
            example_factor = 0.12
        practice_factor = 0.36 if style in {"hands_on", "project"} else 0.24
        if style in {"theory", "theoretical"}:
            practice_factor = 0.17
        code_factor = 0.2 if "code" in examples or style in {"code", "project"} else 0.08
        if programming <= 1:
            code_factor *= 0.6
        review_factor = 0.2 if anxiety > confidence else 0.13
        quiz_factor = 0.08 if anxiety >= 4 else 0.11
        project_factor = 0.3 if style == "project" else (0.18 if "code" in examples else 0.1)
        reflection_factor = 0.08 if self_regulation <= 2 else 0.05
        if mathematical <= 2:
            example_factor += 0.06
            practice_factor += 0.05
        if abstract <= 2:
            example_factor += 0.05
        if logical <= 2:
            quiz_factor += 0.08
            review_factor += 0.04
        if pace in {"slow", "flexible"}:
            review_factor += 0.03

        activities: list[dict[str, Any]] = []
        for order, concept in enumerate(concept_path, start=1):
            concept_id = str(concept["concept_id"])
            base = max(5, int(concept.get("estimated_total_minutes") or 90))
            source = concept.get("source_mode") or "template"
            reason_prefix = str(concept.get("planning_reason") or "Required for the goal")
            activities.extend(
                [
                    self._activity(
                        concept_id,
                        "explanation",
                        base,
                        order,
                        source,
                        f"{reason_prefix}; establishes the core mental model.",
                    ),
                    self._activity(
                        concept_id,
                        "example",
                        _round_minutes(base * example_factor),
                        order,
                        source,
                        f"Example allocation reflects the learner's {style} preference.",
                    ),
                    self._activity(
                        concept_id,
                        "practice",
                        _round_minutes(base * practice_factor),
                        order,
                        source,
                        f"Practice converts understanding into recall and application for {concept_id}.",
                    ),
                    self._activity(
                        concept_id,
                        "code",
                        _round_minutes(base * code_factor),
                        order,
                        source,
                        "Code/application time reflects programming foundation and example preference.",
                    ),
                    self._activity(
                        concept_id,
                        "review",
                        _round_minutes(base * review_factor),
                        order,
                        source,
                        "Review allocation increases when current anxiety exceeds confidence.",
                    ),
                    self._activity(
                        concept_id,
                        "quiz",
                        _round_minutes(base * quiz_factor),
                        order,
                        source,
                        "A short assessment checks whether the concept can be retrieved and applied.",
                    ),
                ]
            )

        total_base = sum(
            max(5, int(item.get("estimated_total_minutes") or 90))
            for item in concept_path
        )
        if concept_path:
            target = str(concept_path[-1]["concept_id"])
            activities.append(
                self._activity(
                    target,
                    "project",
                    _round_minutes(total_base * project_factor),
                    len(concept_path) + 1,
                    "profile_rule",
                    f"Project time reflects the learner's {style} activity preference.",
                )
            )
            activities.append(
                self._activity(
                    target,
                    "reflection",
                    _round_minutes(total_base * reflection_factor),
                    len(concept_path) + 2,
                    "profile_rule",
                    "Reflection time supports self-monitoring and transfer to the stated goal.",
                )
            )
        return activities

    @staticmethod
    def _activity(
        concept_id: str,
        activity_type: str,
        minutes: int,
        sequence: int,
        source: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "activity_id": f"{concept_id}::{activity_type}::{uuid.uuid4().hex[:8]}",
            "activity_type": activity_type,
            "concept_ids": [concept_id],
            "title": f"{activity_type.replace('_', ' ').title()}: {concept_id}",
            "estimated_minutes": int(minutes),
            "sequence": sequence,
            "source": source,
            "reason": reason,
            "required": True,
        }

    @staticmethod
    def _validated_generated_activities(
        activities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        allowed = {
            "explanation",
            "example",
            "practice",
            "code",
            "review",
            "quiz",
            "project",
            "reflection",
        }
        validated = []
        for index, item in enumerate(activities, start=1):
            activity_type = str(item.get("activity_type") or "")
            minutes = int(item.get("estimated_minutes") or 0)
            if activity_type not in allowed or minutes <= 0:
                raise ValueError("model activity failed schema validation")
            validated.append(
                {
                    **item,
                    "activity_id": str(
                        item.get("activity_id")
                        or f"model::{activity_type}::{uuid.uuid4().hex[:8]}"
                    ),
                    "concept_ids": list(item.get("concept_ids") or []),
                    "sequence": int(item.get("sequence") or index),
                    "source": str(item.get("source") or "live_model"),
                    "reason": str(item.get("reason") or "Generated for the learning goal"),
                    "required": True,
                }
            )
        present = {item["activity_type"] for item in validated}
        required = {
            "explanation",
            "example",
            "practice",
            "code",
            "review",
            "quiz",
            "project",
            "reflection",
        }
        if not required.issubset(present):
            raise ValueError("model activity set is incomplete")
        return validated

    def _reading_activities(
        self,
        readings: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        activities = []
        sources = []
        for index, reading in enumerate(readings, start=1):
            source_record = {
                "source_type": "document_word_count",
                "source_id": reading["document_id"],
                "display_name": reading["display_name"],
                "word_count": reading["word_count"],
                "reading_speed_wpm": reading["reading_speed_wpm"],
                "raw_minutes": reading["estimated_minutes"],
                "required": reading["required"],
                "scope": reading["scope"],
                "confidence": 0.82 if reading["word_count"] else 0.55,
                "reason": reading["reason"],
            }
            sources.append(source_record)
            if not reading["required"]:
                continue
            activities.append(
                {
                    "activity_id": f"{reading['document_id']}::required_reading",
                    "activity_type": "required_reading",
                    "concept_ids": reading["overlap_concept_ids"],
                    "document_id": reading["document_id"],
                    "title": f"Required reading: {reading['display_name']}",
                    "estimated_minutes": reading["estimated_minutes"],
                    "sequence": index,
                    "source": "private_document",
                    "source_refs": reading["source_refs"],
                    "reason": reading["reason"],
                    "required": True,
                }
            )
        return activities, sources

    @staticmethod
    def _deduplicate_required_reading(
        activities: list[dict[str, Any]],
        readings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        removed = 0
        replacements = []
        explanations = {
            concept_id: [
                activity
                for activity in activities
                if activity["activity_type"] == "explanation"
                and concept_id in activity.get("concept_ids", [])
            ]
            for reading in readings
            for concept_id in reading.get("overlap_concept_ids", [])
        }
        for reading in readings:
            if not reading["required"]:
                continue
            remaining = min(
                int(reading["estimated_minutes"]),
                sum(
                    int(activity["estimated_minutes"] * 0.35)
                    for concept_id in reading["overlap_concept_ids"]
                    for activity in explanations.get(concept_id, [])
                ),
            )
            original_remaining = remaining
            for concept_id in reading["overlap_concept_ids"]:
                for activity in explanations.get(concept_id, []):
                    if remaining <= 0:
                        break
                    maximum = max(0, activity["estimated_minutes"] - 5)
                    reduction = min(maximum, remaining)
                    activity["estimated_minutes"] -= reduction
                    activity["reason"] += (
                        f" {reduction} minute(s) are replaced by required reading "
                        "covering the same concept."
                    )
                    remaining -= reduction
                    removed += reduction
            replaced = original_remaining - remaining
            if replaced:
                replacements.append(
                    {
                        "document_id": reading["document_id"],
                        "replaced_explanation_minutes": replaced,
                        "concept_ids": reading["overlap_concept_ids"],
                    }
                )
        return {
            "duplicate_chunk_count": sum(
                int(reading.get("duplicate_chunk_count") or 0)
                for reading in readings
            ),
            "replaced_explanation_minutes": removed,
            "replacements": replacements,
            "policy": (
                "Reference documents add no independent time. Required reading "
                "replaces overlapping explanation time before any excess is added."
            ),
        }

    @staticmethod
    def _activity_mix(totals: dict[str, int], total: int) -> list[dict[str, Any]]:
        return [
            {
                "category": key.removesuffix("_minutes"),
                "minutes": value,
                "percentage": round(value / total * 100, 1) if total else 0.0,
            }
            for key, value in totals.items()
        ]


class WorkloadService:
    def __init__(
        self,
        *,
        store: WorkloadStore,
        onboarding_store: OnboardingStore,
        backend: PathlyBackend,
        goal_interpretations: GoalInterpretationStore,
        documents: PrivateDocumentStore,
        activity_planner: ActivityPlanner | None = None,
    ):
        self.store = store
        self.onboarding_store = onboarding_store
        self.backend = backend
        self.goal_interpretations = goal_interpretations
        self.documents = documents
        self.activity_planner = activity_planner or ActivityPlanner()

    def generate(self, *, user_id: str, draft_id: str) -> dict[str, Any]:
        draft = self.onboarding_store.get(user_id, draft_id)
        if not draft:
            raise OnboardingDraftNotFoundError(draft_id)
        if draft.get("status") != "profile_confirmed":
            raise WorkloadValidationError(
                "Profile must be confirmed before final workload estimation"
            )
        profile = self.backend.profiles.get_profile(user_id)
        if not profile:
            raise WorkloadValidationError("Confirmed learner profile was not found")
        context = dict(draft.get("path_context_preview") or {})
        profile_snapshot = dict(draft.get("profile_snapshot") or {})
        profile.mastery_vector = {
            **dict(profile.mastery_vector or {}),
            **dict(context.get("target_mastery") or {}),
        }
        interpretation = self._interpretation(user_id, draft)
        target_terms = self._target_terms(draft, interpretation)
        concept_result = self._build_concept_path(
            profile,
            target_terms,
            goal_text=str(draft.get("goal_text") or ""),
        )
        self._apply_private_concept_names(concept_result, interpretation)
        self._apply_knowledge_map_review(concept_result, draft)
        self._normalize_concept_roles_and_order(concept_result)
        readings = self._build_readings(user_id, interpretation, profile_snapshot, context)
        estimate = self.activity_planner.plan(
            concept_path=concept_result["concept_path"],
            profile_snapshot=profile_snapshot,
            path_context=context,
            readings=readings,
            estimate_sources=concept_result["estimate_sources"],
            coverage_warnings=concept_result["coverage_warnings"],
        )
        payload = {
            "estimate_id": str(uuid.uuid4()),
            "path_id": f"onboarding:{draft_id}",
            "draft_id": draft_id,
            "user_id": user_id,
            "goal_text": draft["goal_text"],
            "goal_interpretation_id": draft.get("goal_interpretation_id"),
            "concept_path": concept_result["concept_path"],
            "concept_units": concept_result["concept_units"],
            "kg_source": concept_result["kg_source"],
            "mode": "live" if concept_result["kg_source"] == "neo4j" else "fallback",
            "source_mode": (interpretation or {}).get("source_mode", "kg_only"),
            "knowledge_map_review": draft.get("knowledge_map_review"),
            "knowledge_map": concept_result.get("knowledge_map"),
            **estimate,
            "schema_version": 2,
        }
        saved = self.store.save(payload)
        draft["workload_estimate_id"] = saved["estimate_id"]
        draft["workload_estimate"] = {
            key: saved[key]
            for key in (
                "estimate_id",
                "total_required_minutes",
                "estimate_is_final",
                "estimate_confidence",
                "generation_mode",
                "mode",
            )
        }
        draft["updated_at"] = _now_iso()
        self.onboarding_store.save(draft)
        return saved

    @staticmethod
    def _normalize_concept_roles_and_order(concept_result: dict[str, Any]) -> None:
        path = list(concept_result.get("concept_path") or [])
        if not path:
            return
        if concept_result.get("knowledge_map_locked"):
            for order, node in enumerate(path, start=1):
                node["order"] = order
            concept_result["concept_path"] = path
            return
        by_id = {str(node.get("concept_id")): node for node in path}
        target_ids = {
            concept_id
            for concept_id, node in by_id.items()
            if bool(node.get("is_target"))
        }
        prerequisite_ids: set[str] = set()
        frontier = list(target_ids)
        while frontier:
            concept_id = frontier.pop()
            node = by_id.get(concept_id) or {}
            for prerequisite in node.get("prerequisite_ids") or []:
                prerequisite = str(prerequisite)
                if prerequisite in by_id and prerequisite not in prerequisite_ids:
                    prerequisite_ids.add(prerequisite)
                    frontier.append(prerequisite)
        original_index = {str(node.get("concept_id")): index for index, node in enumerate(path)}
        for node in path:
            concept_id = str(node.get("concept_id"))
            node["prerequisite_ids"] = [
                str(item)
                for item in node.get("prerequisite_ids") or []
                if str(item) in by_id
            ]
            if concept_id in target_ids:
                node["path_role"] = "target"
            elif concept_id in prerequisite_ids:
                node["path_role"] = "prerequisite"
            else:
                node["path_role"] = "supporting"
                node["prerequisite_ids"] = [
                    item for item in node["prerequisite_ids"] if item not in target_ids
                ]
                minutes = int(node.get("estimated_total_minutes") or 0)
                node["planning_reason"] = (
                    f"{concept_id} is a supporting concept related to the confirmed "
                    f"learning goal. It is included in the learning scope but is not "
                    f"claimed as a required prerequisite; estimated work is {minutes} minutes."
                )
        rank = {"prerequisite": 0, "supporting": 1, "target": 2}
        path.sort(
            key=lambda node: (
                rank.get(str(node.get("path_role")), 1),
                original_index.get(str(node.get("concept_id")), 0),
            )
        )
        for order, node in enumerate(path, start=1):
            node["order"] = order
        concept_result["concept_path"] = path

    @staticmethod
    def _apply_knowledge_map_review(
        concept_result: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        review = dict(draft.get("knowledge_map_review") or {})
        if review.get("status") != "confirmed":
            return
        excluded = {str(item) for item in review.get("excluded_concept_ids") or []}
        reviewed = {str(item.get("concept_id")): item for item in review.get("reviewed_concepts") or [] if item.get("concept_id")}
        target_ids = {concept_id for concept_id, item in reviewed.items() if item.get("is_target")}
        if excluded & target_ids:
            raise WorkloadValidationError("A learning target cannot be excluded")
        generated = {str(node.get("concept_id")): node for node in concept_result.get("concept_path") or []}
        active_reviewed = [item for concept_id, item in reviewed.items() if concept_id not in excluded]
        review_edges = []
        for raw_edge in review.get("edges") or []:
            source = str(raw_edge.get("source") or "").strip()
            target = str(raw_edge.get("target") or "").strip()
            if source in reviewed and target in reviewed and source not in excluded and target not in excluded and source != target:
                review_edges.append({"source": source, "target": target, "type": str(raw_edge.get("type") or "sequence_hint")})
        incoming = {}
        for edge in review_edges:
            incoming.setdefault(edge["target"], []).append(edge["source"])
        path = []
        for item in active_reviewed:
            concept_id = str(item["concept_id"])
            node = dict(generated.get(concept_id) or {"concept_id": concept_id, "title": item.get("display_name") or concept_id, "estimated_total_minutes": 5, "units": []})
            node["title"] = item.get("display_name") or node.get("title") or concept_id
            node["display_name"] = item.get("display_name") or node.get("display_name") or node["title"]
            node["is_target"] = bool(item.get("is_target"))
            node["path_role"] = str(item.get("path_role") or ("target" if node["is_target"] else "supporting"))
            node["prerequisite_ids"] = list(dict.fromkeys(incoming.get(concept_id, [])))
            path.append(node)
        concept_result["concept_path"] = path
        concept_result["knowledge_map"] = {"locked": True, "primary_target_id": next((str(item["concept_id"]) for item in active_reviewed if item.get("is_target")), None), "reviewed_concepts": list(reviewed.values()), "edges": review_edges, "excluded_concept_ids": sorted(excluded)}
        concept_result["knowledge_map_locked"] = True
        active_ids = {str(node.get("concept_id")) for node in path}
        concept_result["concept_units"] = [unit for unit in concept_result.get("concept_units") or [] if str(unit.get("concept_id") or unit.get("id")) in active_ids]
        concept_result["estimate_sources"] = [source for source in concept_result.get("estimate_sources") or [] if str(source.get("source_id")) in active_ids or source.get("source_type") == "document_word_count"]
        if not path:
            raise WorkloadValidationError("The confirmed map contains no learnable concepts")
        if excluded:
            concept_result.setdefault("coverage_warnings", []).append("Learner excluded from the Personal Knowledge Map: " + ", ".join(sorted(excluded)))
    def _interpretation(
        self,
        user_id: str,
        draft: dict[str, Any],
    ) -> dict[str, Any] | None:
        interpretation_id = draft.get("goal_interpretation_id")
        if not interpretation_id:
            return None
        interpretation = self.goal_interpretations.get(user_id, interpretation_id)
        if not interpretation or interpretation.get("status") != "confirmed":
            raise WorkloadValidationError(
                "A linked goal interpretation must remain confirmed"
            )
        return interpretation

    @staticmethod
    def _target_terms(
        draft: dict[str, Any],
        interpretation: dict[str, Any] | None,
    ) -> list[str]:
        if interpretation:
            terms = [
                item["concept_id"]
                for item in interpretation.get("canonical_concepts") or []
            ]
            terms.extend(
                item["private_concept_id"]
                for item in interpretation.get("private_concepts") or []
            )
            if terms:
                return list(dict.fromkeys(terms))
        return list(dict.fromkeys(draft.get("target_terms") or []))

    @staticmethod
    def _verified_goal_scope_from_terms(target_terms: list[str]) -> list[str]:
        requested = {
            _normalized(term)
            for term in target_terms
            if not str(term).startswith("private:")
        }
        golden = {_normalized(term) for term in GOLDEN_PATH}
        return list(GOLDEN_PATH) if len(requested & golden) >= 2 else []

    def _apply_verified_goal_scope(
        self,
        *,
        result: dict[str, Any],
        profile,
        verified_scope: list[str],
        source: str,
    ) -> None:
        if not verified_scope:
            return
        scope_keys = {_normalized(name) for name in verified_scope}
        existing_by_key: dict[str, dict[str, Any]] = {}
        for node in result.get("concept_path") or []:
            for value in (
                node.get("concept_id"),
                node.get("title"),
                node.get("display_name"),
            ):
                key = _normalized(value)
                if key:
                    existing_by_key.setdefault(key, node)

        merged: list[dict[str, Any]] = []
        for index, concept_name in enumerate(verified_scope, start=1):
            key = _normalized(concept_name)
            existing = existing_by_key.get(key)
            node = dict(existing) if existing else self._template_concept(concept_name, profile, index)
            previous = verified_scope[index - 2] if index > 1 else None
            node.update(
                {
                    "concept_id": concept_name,
                    "title": concept_name,
                    "display_name": concept_name,
                    "order": index,
                    "is_target": True,
                    "prerequisite_ids": [previous] if previous else [],
                    "source_mode": (
                        "neo4j_verified_public_source"
                        if existing and source == "neo4j"
                        else "verified_public_source_registry"
                    ),
                    "verified_goal_scope": True,
                    "verified_public_source_reusable": True,
                    "planning_reason": (
                        f"{concept_name} is part of the verified source-grounded "
                        "goal scope for this normal learner target; reviewed "
                        "public sources can be reused for v4 content generation."
                    ),
                }
            )
            merged.append(node)

        extras = [
            node
            for node in result.get("concept_path") or []
            if _normalized(node.get("concept_id")) not in scope_keys
            and not str(node.get("concept_id") or "").startswith("private:")
        ]
        if extras:
            result.setdefault("coverage_warnings", []).append(
                "Verified source-grounded goal scope replaced a sparse or noisy "
                "planner neighborhood with the reviewed canonical chain."
            )
        result["concept_path"] = merged
        result["concept_units"] = [
            unit
            for unit in (result.get("concept_units") or [])
            if _normalized(unit.get("concept_id") or unit.get("title")) in scope_keys
        ]
        result["verified_goal_scope"] = {
            "status": "applied",
            "concepts": list(verified_scope),
            "source": source,
        }

    def _apply_catalog_goal_scope(self, *, result: dict[str, Any], profile, spec: dict[str, Any], source: str) -> None:
        path = list(spec["canonical_path"])
        names = list(spec["display_names"])
        existing = {str(node.get("concept_id")): node for node in result.get("concept_path") or []}
        merged = []
        for index, (concept_id, name) in enumerate(zip(path, names), 1):
            node = dict(existing.get(concept_id) or self._template_concept(concept_id, profile, index))
            node.update({
                "concept_id": concept_id, "title": name, "display_name": name,
                "order": index, "is_target": concept_id == path[-1],
                "prerequisite_ids": [path[index - 2]] if index > 1 else [],
                "source_mode": "approved_goal_chain_catalog",
                "verified_goal_scope": True, "verified_public_source_reusable": True,
                "asset_scope": spec["asset_scope"], "source_version": spec["source_version"],
                "planning_reason": f"{name} is part of the approved full-experience canonical chain.",
            })
            merged.append(node)
        result["concept_path"] = merged
        result["concept_units"] = [unit for unit in result.get("concept_units") or [] if str(unit.get("concept_id")) in set(path)]
        result["verified_goal_scope"] = {"status": "applied", "concepts": path, "display_names": names, "source": source, "asset_scope": spec["asset_scope"]}

    def _build_concept_path(
        self,
        profile,
        target_terms: list[str],
        *,
        goal_text: str = "",
    ) -> dict[str, Any]:
        canonical_requested = [
            term for term in target_terms if not str(term).startswith("private:")
        ]
        private_requested = [
            term for term in target_terms if str(term).startswith("private:")
        ]
        graph_attempts = []
        if os.getenv("NEO4J_PASSWORD"):
            graph_attempts.append(("neo4j", None))
        graph_path = CALIBRATED_KG if CALIBRATED_KG.exists() else GLOBAL_KG
        graph_attempts.append(("json", str(graph_path)))
        errors = []
        result = None
        source = "template"
        for backend_name, path in graph_attempts:
            try:
                planner = PlanningAgent(graph_path=path, kg_backend=backend_name)
                targets = []
                for term in canonical_requested:
                    node = planner.repository.get_topic(term)
                    if node:
                        targets.append(str(node["id"]))
                targets = list(dict.fromkeys(targets))
                if canonical_requested and not targets:
                    raise WorkloadValidationError(
                        "No canonical target could be found in the knowledge graph"
                    )
                if targets:
                    learner_state = planner.build_learner_state(profile)
                    path_result = planner.path_planner.plan(
                        targets=targets,
                        known_topics=learner_state["excluded_topics"],
                        algorithm="astar",
                    )
                    ordered = path_result["ordered_topics"] or targets
                    # A target with sparse prerequisite metadata should still expose
                    # a useful goal-scoped public-KG neighborhood.  The planner
                    # previously returned only the exact target in this case,
                    # making a goal such as "machine learning" look empty even
                    # when the KG contained related concepts.  Expand only one
                    # bounded hop (dependents + similarity) and keep the target
                    # itself authoritative; this is not a full-KG dump.
                    if len(ordered) < 4:
                        related: list[str] = []
                        for target in targets:
                            get_dependents = getattr(planner.repository, "get_dependents", None)
                            if get_dependents:
                                related.extend(get_dependents(target) or [])
                            get_similar = getattr(planner.repository, "get_similar", None)
                            if get_similar:
                                related.extend(
                                    item.get("name")
                                    for item in (get_similar(target, limit=6) or [])
                                    if item.get("name")
                                )
                        ordered = list(dict.fromkeys([*ordered, *related]))[:12]
                        if len(ordered) > len(targets):
                            path_result["coverage_note"] = (
                                "Expanded a sparse target into a bounded related-concept neighborhood."
                            )
                    priority = planner.prioritize_topics_for_learner(
                        ordered_topics=ordered,
                        covered_prerequisites=path_result["covered_prerequisites"],
                        profile=profile,
                    )
                    result = planner.concept_expander.expand(
                        ordered_topics=priority["ordered_topics"] or ordered,
                        target_topics=targets,
                        profile=profile,
                        requested_days=1,
                        available_daily_minutes=480,
                    )
                else:
                    result = {
                        "concept_path": [],
                        "concept_units": [],
                        "coverage_warnings": [],
                    }
                source = backend_name
                break
            except Exception as exc:
                errors.append(f"{backend_name}:{type(exc).__name__}")

        if result is None:
            result = {
                "concept_path": [
                    self._template_concept(term, profile, index)
                    for index, term in enumerate(canonical_requested, start=1)
                ],
                "concept_units": [],
                "coverage_warnings": [
                    "Knowledge graph lookup failed; canonical targets use explicit "
                    "template estimates."
                ],
            }
        verified_scope = (
            verified_goal_concepts_for_goal(goal_text)
            or self._verified_goal_scope_from_terms(canonical_requested)
        )
        if verified_scope:
            self._apply_verified_goal_scope(
                result=result,
                profile=profile,
                verified_scope=verified_scope,
                source=source,
            )
        else:
            catalog = resolve_goal_chain(goal_text)
            if catalog:
                self._apply_catalog_goal_scope(result=result, profile=profile, spec=catalog[1], source=source)
        for index, term in enumerate(
            private_requested,
            start=len(result["concept_path"]) + 1,
        ):
            result["concept_path"].append(
                self._template_concept(term, profile, index, private=True)
            )
        if not result["concept_path"]:
            raise WorkloadValidationError(
                "No confirmed canonical or private concept is available for estimation"
            )
        estimate_sources = []
        for concept in result["concept_path"]:
            private = str(concept["concept_id"]).startswith("private:")
            estimate_sources.append(
                {
                    "source_type": (
                        "private_concept_template" if private else "kg_metadata"
                    ),
                    "source_id": concept["concept_id"],
                    "base_minutes": concept["estimated_total_minutes"],
                    "source_mode": concept.get("source_mode") or source,
                    "confidence": 0.58 if private or source == "template" else (
                        0.86 if source == "neo4j" else 0.76
                    ),
                    "reason": concept.get("planning_reason"),
                }
            )
        if errors:
            result["coverage_warnings"].append(
                "Graph fallback attempts: " + ", ".join(errors)
            )
        return {
            **result,
            "kg_source": source,
            "estimate_sources": estimate_sources,
        }

    @staticmethod
    def _apply_private_concept_names(
        concept_result: dict[str, Any],
        interpretation: dict[str, Any] | None,
    ) -> None:
        names = {
            item["private_concept_id"]: (
                item.get("display_name") or item.get("requested_term")
            )
            for item in (interpretation or {}).get("private_concepts") or []
            if item.get("private_concept_id")
        }
        for node in concept_result.get("concept_path") or []:
            display_name = names.get(node.get("concept_id"))
            if display_name:
                node["title"] = display_name
                node["display_name"] = display_name
                concept_id = str(node.get("concept_id") or "")
                node["planning_reason"] = str(
                    node.get("planning_reason") or ""
                ).replace(concept_id, str(display_name))
                for source in concept_result.get("estimate_sources") or []:
                    if source.get("source_id") == concept_id:
                        source["reason"] = str(source.get("reason") or "").replace(
                            concept_id, str(display_name)
                        )
    @staticmethod
    def _template_concept(
        concept_id: str,
        profile,
        order: int,
        private: bool = False,
    ) -> dict[str, Any]:
        mastery = float((profile.mastery_vector or {}).get(concept_id, 0.0))
        foundation = (
            float(profile.math_foundation) + float(profile.programming_foundation)
        ) / 2
        base = 90 if private else 100
        adjusted = _round_minutes(
            base
            * max(0.7, 1.15 - 0.5 * mastery)
            * max(0.85, 1.1 - 0.05 * (foundation - 1))
        )
        return {
            "concept_id": concept_id,
            "title": concept_id,
            "order": order,
            "is_target": True,
            "prerequisite_ids": [],
            "relationship_source": [],
            "difficulty": 3,
            "estimated_total_minutes": adjusted,
            "mastery_before": mastery,
            "planning_reason": (
                f"{concept_id} has no complete KG timing metadata; {adjusted} "
                "minutes are estimated from a transparent template, learner "
                "foundation, and target-specific mastery."
            ),
            "source_mode": "private_template" if private else "template",
            "units": [],
        }

    def _build_readings(
        self,
        user_id: str,
        interpretation: dict[str, Any] | None,
        profile: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not interpretation:
            return []
        evidence = self.goal_interpretations.evidence(
            user_id, interpretation["interpretation_id"]
        )
        evidence_by_document: dict[str, list[str]] = {}
        for item in evidence:
            if item.get("mapping_status") == "rejected" or not item.get("document_id"):
                continue
            concept_id = item.get("canonical_concept_id") or item.get("private_concept_id")
            if concept_id:
                evidence_by_document.setdefault(item["document_id"], []).append(concept_id)
        cognitive = profile.get("cognitive_traits") or {}
        affective = profile.get("affective_defaults") or {}
        current = context.get("current_affective_state") or {}
        foundation = sum(
            float(cognitive.get(key, 3))
            for key in (
                "mathematical_ability",
                "programming_ability",
                "abstract_thinking",
                "logical_reasoning",
                "general_learning_foundation",
            )
        ) / 5
        anxiety = float(
            current.get("anxiety")
            or affective.get("anxiety_baseline")
            or 2
        )
        reading_speed = int(max(140, min(240, 190 + (foundation - 3) * 12 - max(anxiety - 3, 0) * 10)))
        readings = []
        seen_chunks: set[str] = set()
        for selection in interpretation.get("documents") or []:
            document_id = selection["document_id"]
            document = self.documents.get_document(user_id, document_id)
            if not document:
                raise WorkloadValidationError(
                    f"Required source document is no longer available: {document_id}"
                )
            selected = self._scoped_chunks(user_id, document_id, selection)
            unique = []
            duplicate_count = 0
            for chunk in selected:
                if chunk["chunk_id"] in seen_chunks:
                    duplicate_count += 1
                    continue
                seen_chunks.add(chunk["chunk_id"])
                unique.append(chunk)
            word_count = sum(int(chunk.get("word_count") or 0) for chunk in unique)
            minutes = _round_minutes(word_count / reading_speed) if word_count else 5
            required = bool(selection.get("required"))
            readings.append(
                {
                    "document_id": document_id,
                    "display_name": selection.get("display_name")
                    or document.get("display_name")
                    or document_id,
                    "required": required,
                    "word_count": word_count,
                    "reading_speed_wpm": reading_speed,
                    "estimated_minutes": minutes,
                    "overlap_concept_ids": list(
                        dict.fromkeys(evidence_by_document.get(document_id, []))
                    ),
                    "duplicate_chunk_count": duplicate_count,
                    "scope": {
                        "included_pages": selection.get("included_pages") or [],
                        "excluded_pages": selection.get("excluded_pages") or [],
                        "included_sections": selection.get("included_sections") or [],
                        "excluded_sections": selection.get("excluded_sections") or [],
                    },
                    "source_refs": [
                        {
                            "chunk_id": chunk["chunk_id"],
                            "page_start": chunk.get("page_start"),
                            "page_end": chunk.get("page_end"),
                        }
                        for chunk in unique
                    ],
                    "reason": (
                        "Counted as independent required reading because the learner "
                        "confirmed this document scope as mandatory."
                        if required
                        else "Reference-only material is available for content and "
                        "retrieval but adds no independent workload."
                    ),
                }
            )
        return readings

    def _scoped_chunks(
        self,
        user_id: str,
        document_id: str,
        selection: dict[str, Any],
    ) -> list[dict[str, Any]]:
        included_pages = {int(value) for value in selection.get("included_pages") or []}
        excluded_pages = {int(value) for value in selection.get("excluded_pages") or []}
        included_sections = [
            _normalized(value) for value in selection.get("included_sections") or []
        ]
        excluded_sections = [
            _normalized(value) for value in selection.get("excluded_sections") or []
        ]
        selected = []
        for chunk in self.documents.get_chunks(user_id, document_id):
            page = int(chunk.get("page_start") or 0)
            if included_pages and page not in included_pages:
                continue
            if page in excluded_pages:
                continue
            try:
                metadata = json.loads(chunk.get("metadata_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            section = _normalized(
                metadata.get("section_path")
                or str(chunk.get("text") or "").splitlines()[0][:120]
            )
            if included_sections and not any(
                item in section or section in item for item in included_sections
            ):
                continue
            if excluded_sections and any(
                item in section or section in item for item in excluded_sections
            ):
                continue
            selected.append(chunk)
        return selected
