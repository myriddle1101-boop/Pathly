"""Capacity-first feasibility negotiation and final path confirmation.

O5 consumes an immutable, final O4 workload estimate.  It never changes that
estimate when the learner changes duration.  A formal path and plan v1 are
created only after the learner confirms a feasible decision.
"""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pathly_backend import PathlyBackend
from pathly_documents import PrivateDocumentStore
from pathly_goal_interpretation import GoalInterpretationStore
from pathly_onboarding import OnboardingDraftNotFoundError, OnboardingStore
from pathly_workload import WorkloadStore


class FeasibilityValidationError(ValueError):
    pass


class FeasibilityDecisionNotFoundError(KeyError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeasibilityStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS feasibility_decisions (
                    decision_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    estimate_id TEXT NOT NULL,
                    draft_id TEXT NOT NULL,
                    path_id TEXT,
                    status TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feasibility_owner
                    ON feasibility_decisions(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_feasibility_estimate
                    ON feasibility_decisions(estimate_id, updated_at DESC);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, decision: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        payload = dict(decision)
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO feasibility_decisions(
                    decision_id, user_id, estimate_id, draft_id, path_id,
                    status, decision_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    path_id=excluded.path_id,
                    status=excluded.status,
                    decision_json=excluded.decision_json,
                    updated_at=excluded.updated_at
                """,
                (
                    payload["decision_id"],
                    payload["user_id"],
                    payload["estimate_id"],
                    payload["draft_id"],
                    payload.get("path_id"),
                    payload["status"],
                    json.dumps(payload, ensure_ascii=False),
                    payload["created_at"],
                    now,
                ),
            )
        return payload

    def get(self, user_id: str, decision_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT decision_json FROM feasibility_decisions
                WHERE decision_id = ? AND user_id = ?
                """,
                (decision_id, user_id),
            ).fetchone()
        return json.loads(row["decision_json"]) if row else None

    def latest_for_estimate(
        self,
        user_id: str,
        estimate_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT decision_json FROM feasibility_decisions
                WHERE estimate_id = ? AND user_id = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (estimate_id, user_id),
            ).fetchone()
        return json.loads(row["decision_json"]) if row else None
    def save_document_links(
        self,
        path_id: str,
        links: list[dict[str, Any]],
    ) -> None:
        if not links:
            return
        now = _now_iso()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO path_document_links(
                    path_id, document_id, link_json, created_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(path_id, document_id) DO UPDATE SET
                    link_json=excluded.link_json
                """,
                [
                    (
                        path_id,
                        link["document_id"],
                        json.dumps(link, ensure_ascii=False),
                        now,
                    )
                    for link in links
                ],
            )


class CapacityNegotiator:
    STATUSES = {"capacity_pending", "comfortable", "feasible", "tight", "insufficient"}

    def __init__(self, today_provider: Callable[[], date] | None = None):
        self.today_provider = today_provider or date.today

    def requested_days(
        self,
        *,
        requested_days: int | None,
        deadline: str | None,
    ) -> tuple[int, str | None, str]:
        if requested_days is None and not deadline:
            raise FeasibilityValidationError(
                "Either requested_days or deadline is required"
            )
        if requested_days is not None and deadline:
            raise FeasibilityValidationError(
                "Use requested_days or deadline, not both"
            )
        if requested_days is not None:
            days = int(requested_days)
            if days < 1 or days > 60:
                raise FeasibilityValidationError(
                    "requested_days must be between 1 and 60"
                )
            return days, None, "requested_days"
        try:
            target = date.fromisoformat(str(deadline))
        except ValueError as exc:
            raise FeasibilityValidationError(
                "deadline must use YYYY-MM-DD"
            ) from exc
        today = self.today_provider()
        if target < today:
            raise FeasibilityValidationError("deadline cannot be in the past")
        return (target - today).days + 1, target.isoformat(), "deadline"

    def evaluate(
        self,
        *,
        total_required_minutes: int,
        requested_days: int,
        max_available_daily_minutes: int | None,
    ) -> dict[str, Any]:
        total = max(1, int(total_required_minutes))
        days = max(1, int(requested_days))
        recommended = math.ceil(total / days)
        if max_available_daily_minutes is None:
            return {
                "requested_days": days,
                "recommended_daily_minutes": recommended,
                "max_available_daily_minutes": None,
                "available_capacity_minutes": None,
                "capacity_gap_minutes": None,
                "minimum_recommended_days": None,
                "status": "capacity_pending",
                "status_reason": (
                    f"The goal requires {total} minutes. Over {days} day(s), "
                    f"the recommended average is {recommended} minutes/day. "
                    "Maximum sustainable daily time is still required."
                ),
            }
        maximum = int(max_available_daily_minutes)
        if maximum < 1 or maximum > 1440:
            raise FeasibilityValidationError(
                "max_available_daily_minutes must be between 1 and 1440"
            )
        capacity = days * maximum
        gap = capacity - total
        ratio = capacity / total
        if gap < 0:
            status = "insufficient"
        elif ratio < 1.1:
            status = "tight"
        elif ratio < 1.3:
            status = "feasible"
        else:
            status = "comfortable"
        minimum_days = math.ceil(total / maximum)
        return {
            "requested_days": days,
            "recommended_daily_minutes": recommended,
            "max_available_daily_minutes": maximum,
            "available_capacity_minutes": capacity,
            "capacity_gap_minutes": gap,
            "minimum_recommended_days": minimum_days,
            "status": status,
            "status_reason": self._reason(
                status=status,
                total=total,
                days=days,
                recommended=recommended,
                maximum=maximum,
                gap=gap,
                minimum_days=minimum_days,
            ),
        }

    @staticmethod
    def _reason(
        *,
        status: str,
        total: int,
        days: int,
        recommended: int,
        maximum: int,
        gap: int,
        minimum_days: int,
    ) -> str:
        base = (
            f"The confirmed goal requires {total} minutes. Over {days} day(s), "
            f"the recommended average is {recommended} minutes/day; the learner "
            f"can sustain at most {maximum} minutes/day."
        )
        if status == "insufficient":
            return (
                f"{base} Capacity is short by {-gap} minutes; at least "
                f"{minimum_days} day(s) are recommended at this daily maximum."
            )
        if status == "tight":
            return f"{base} Capacity covers the goal with only {gap} buffer minutes."
        if status == "feasible":
            return f"{base} Capacity covers the goal with {gap} buffer minutes."
        return (
            f"{base} Capacity has {gap} surplus minutes, so the learner may "
            "consolidate across the full horizon or finish earlier."
        )

    @staticmethod
    def options(decision: dict[str, Any]) -> list[dict[str, Any]]:
        status = decision["status"]
        if status == "capacity_pending":
            return [
                {
                    "strategy": "set_daily_capacity",
                    "reason": "Confirm the maximum sustainable daily time.",
                },
            ]
        if status == "insufficient":
            return [
                {
                    "strategy": "extend_days",
                    "suggested_days": decision["minimum_recommended_days"],
                    "reason": "Keep the full goal and extend the horizon.",
                },
                {
                    "strategy": "increase_daily_time",
                    "required_daily_minutes": decision["recommended_daily_minutes"],
                    "reason": "Keep the full goal and increase daily capacity.",
                },
                {
                    "strategy": "narrow_scope",
                    "reason": "Create a separate partial-goal proposal; nothing is removed automatically.",
                },
                {
                    "strategy": "adjust_outcome",
                    "reason": "Return to goal interpretation and revise the expected outcome.",
                },
            ]
        if status == "comfortable":
            return [
                {
                    "strategy": "paced_consolidation",
                    "required_daily_minutes": decision["recommended_daily_minutes"],
                    "daily_capacity_minutes": decision["max_available_daily_minutes"],
                    "horizon_days": decision.get("effective_days", decision["requested_days"]),
                    "optional_consolidation_budget_minutes": max(
                        0, int(decision["capacity_gap_minutes"])
                    ),
                    "reason": "Use the full horizon for meaningful reinforcement in O6.",
                },
                {
                    "strategy": "early_completion",
                    "suggested_days": decision["minimum_recommended_days"],
                    "required_daily_minutes": (
                        int(decision["effective_total_minutes"])
                        + int(decision["minimum_recommended_days"])
                        - 1
                    )
                    // int(decision["minimum_recommended_days"]),
                    "freed_days": max(
                        0,
                        int(decision.get("effective_days", decision["requested_days"]))
                        - int(decision["minimum_recommended_days"]),
                    ),
                    "reason": "Finish in the shortest honest horizon at the confirmed daily maximum.",
                },
                {
                    "strategy": "proceed",
                    "required_daily_minutes": decision["recommended_daily_minutes"],
                    "unused_capacity_minutes": max(
                        0, int(decision["capacity_gap_minutes"])
                    ),
                    "reason": "Keep the requested horizon without adding optional workload.",
                },
            ]
        target_ratio_tenths = 11 if status == "tight" else 13
        total = int(decision["effective_total_minutes"])
        maximum = int(decision["max_available_daily_minutes"])
        ratio_denominator = 10 * maximum
        days_for_target_ratio = (
            total * target_ratio_tenths + ratio_denominator - 1
        ) // ratio_denominator
        suggested_days = min(
            60,
            max(
                int(decision["requested_days"]) + 1,
                days_for_target_ratio,
            ),
        )
        options = [
            {
                "strategy": "proceed",
                "reason": "Capacity covers the complete goal.",
            },
        ]
        if suggested_days > int(decision["requested_days"]):
            options.insert(
                1,
                {
                    "strategy": "extend_days",
                    "suggested_days": suggested_days,
                    "reason": "Add more buffer without changing the goal.",
                },
            )
        return options


class FeasibilityService:
    STRATEGIES = {
        "set_daily_capacity",
        "extend_days",
        "increase_daily_time",
        "narrow_scope",
        "adjust_outcome",
        "save_draft",
        "paced_consolidation",
        "early_completion",
        "proceed",
    }

    def __init__(
        self,
        *,
        store: FeasibilityStore,
        workload_store: WorkloadStore,
        onboarding_store: OnboardingStore,
        backend: PathlyBackend,
        goal_interpretations: GoalInterpretationStore,
        documents: PrivateDocumentStore,
        negotiator: CapacityNegotiator | None = None,
    ):
        self.store = store
        self.workload_store = workload_store
        self.onboarding_store = onboarding_store
        self.backend = backend
        self.goal_interpretations = goal_interpretations
        self.documents = documents
        self.negotiator = negotiator or CapacityNegotiator()

    def create(
        self,
        *,
        user_id: str,
        estimate_id: str,
        requested_days: int | None = None,
        deadline: str | None = None,
        max_available_daily_minutes: int | None = None,
    ) -> dict[str, Any]:
        estimate = self._estimate(user_id, estimate_id)
        days, normalized_deadline, input_mode = self.negotiator.requested_days(
            requested_days=requested_days,
            deadline=deadline,
        )
        capacity = self.negotiator.evaluate(
            total_required_minutes=estimate["total_required_minutes"],
            requested_days=days,
            max_available_daily_minutes=max_available_daily_minutes,
        )
        decision = {
            "decision_id": str(uuid.uuid4()),
            "path_id": estimate["path_id"],
            "draft_id": estimate["draft_id"],
            "estimate_id": estimate_id,
            "user_id": user_id,
            "workload_total_minutes": int(estimate["total_required_minutes"]),
            "effective_total_minutes": int(estimate["total_required_minutes"]),
            "deadline": normalized_deadline,
            "duration_input_mode": input_mode,
            "selected_strategy": None,
            "scope_change_draft": None,
            "user_confirmed_at": None,
            "plan_id": None,
            **capacity,
        }
        decision["options"] = self.negotiator.options(decision)
        saved = self.store.save(decision)
        draft = self.onboarding_store.get(user_id, estimate["draft_id"])
        if draft and draft.get("status") == "profile_confirmed":
            draft["feasibility_decision_id"] = saved["decision_id"]
            draft["updated_at"] = _now_iso()
            self.onboarding_store.save(draft)
        return saved

    def update(
        self,
        *,
        user_id: str,
        decision_id: str,
        requested_days: int | None = None,
        deadline: str | None = None,
        max_available_daily_minutes: int | None = None,
        selected_strategy: str | None = None,
        scope_remove_concept_ids: list[str] | None = None,
        scope_change_decision: str | None = None,
    ) -> dict[str, Any]:
        decision = self._decision(user_id, decision_id)
        if decision.get("user_confirmed_at"):
            raise FeasibilityValidationError(
                "A confirmed feasibility decision is read-only"
            )
        if selected_strategy and selected_strategy not in self.STRATEGIES:
            raise FeasibilityValidationError(
                f"Unsupported feasibility strategy: {selected_strategy}"
            )
        if requested_days is not None or deadline:
            days, normalized_deadline, input_mode = self.negotiator.requested_days(
                requested_days=requested_days,
                deadline=deadline,
            )
            decision["requested_days"] = days
            decision["deadline"] = normalized_deadline
            decision["duration_input_mode"] = input_mode
        if max_available_daily_minutes is not None:
            decision["max_available_daily_minutes"] = int(
                max_available_daily_minutes
            )
        if scope_change_decision:
            self._decide_scope_change(decision, scope_change_decision)
        if selected_strategy == "narrow_scope":
            decision["scope_change_draft"] = self._scope_change(
                user_id=user_id,
                estimate_id=decision["estimate_id"],
                removed_concept_ids=scope_remove_concept_ids or [],
            )
        elif scope_remove_concept_ids:
            raise FeasibilityValidationError(
                "scope_remove_concept_ids requires selected_strategy=narrow_scope"
            )
        if selected_strategy:
            decision["selected_strategy"] = selected_strategy
        total = self._effective_total(decision)
        capacity = self.negotiator.evaluate(
            total_required_minutes=total,
            requested_days=decision["requested_days"],
            max_available_daily_minutes=decision.get(
                "max_available_daily_minutes"
            ),
        )
        decision.update(capacity)
        decision["effective_total_minutes"] = total
        decision["options"] = self.negotiator.options(decision)
        return self.store.save(decision)

    def confirm(
        self,
        *,
        user_id: str,
        decision_id: str,
    ) -> dict[str, Any]:
        decision = self._decision(user_id, decision_id)
        if decision.get("user_confirmed_at"):
            return decision
        scope = decision.get("scope_change_draft")
        if scope and scope.get("status") == "pending":
            raise FeasibilityValidationError(
                "The scope change must be accepted or rejected before confirmation"
            )
        if decision["status"] in {"capacity_pending", "insufficient"}:
            raise FeasibilityValidationError(
                "Capacity must cover the selected goal before path confirmation"
            )
        if not decision.get("selected_strategy"):
            raise FeasibilityValidationError(
                "A feasibility strategy must be explicitly selected"
            )
        if decision["selected_strategy"] in {
            "save_draft",
            "adjust_outcome",
            "set_daily_capacity",
        }:
            raise FeasibilityValidationError(
                "The selected strategy does not authorize path creation"
            )
        if decision["selected_strategy"] == "narrow_scope" and (
            not scope or scope.get("status") != "accepted"
        ):
            raise FeasibilityValidationError(
                "The proposed narrower scope must be explicitly accepted"
            )

        estimate = self._estimate(user_id, decision["estimate_id"])
        draft = self.onboarding_store.get(user_id, decision["draft_id"])
        if not draft:
            raise OnboardingDraftNotFoundError(decision["draft_id"])
        if draft.get("status") != "profile_confirmed":
            raise FeasibilityValidationError(
                "Onboarding draft is not ready for path confirmation"
            )
        concept_path, activities = self._effective_scope(estimate, decision)
        if not concept_path or not activities:
            raise FeasibilityValidationError(
                "The confirmed scope must retain concepts and activities"
            )
        effective_days = int(decision["requested_days"])
        if decision["selected_strategy"] == "early_completion":
            effective_days = int(decision["minimum_recommended_days"])
        effective_goal_text = (
            scope["proposed_goal_text"]
            if scope and scope.get("status") == "accepted"
            else draft["goal_text"]
        )
        path_id = str(uuid.uuid4())
        plan_id = str(uuid.uuid4())
        plan = {
            "schema_version": 3,
            "plan_id": plan_id,
            "path_id": path_id,
            "goal": {
                "text": effective_goal_text,
                "outcome_type": "knowledge_and_application",
            },
            "target_topics": [
                item["concept_id"]
                for item in concept_path
                if item.get("is_target", True)
            ],
            "ordered_topics": [item["concept_id"] for item in concept_path],
            "concept_path": concept_path,
            "activities": activities,
            "workload_estimate": {
                "estimate_id": estimate["estimate_id"],
                "original_total_required_minutes": estimate[
                    "total_required_minutes"
                ],
                "total_required_minutes": decision["effective_total_minutes"],
                "estimate_is_final": True,
                "scope_change": scope,
            },
            "feasibility": {
                **{
                    key: decision.get(key)
                    for key in (
                        "decision_id",
                        "requested_days",
                        "deadline",
                        "recommended_daily_minutes",
                        "max_available_daily_minutes",
                        "available_capacity_minutes",
                        "capacity_gap_minutes",
                        "minimum_recommended_days",
                        "status",
                        "selected_strategy",
                    )
                },
                "effective_days": effective_days,
            },
            "days": [],
            "schedule_status": "pending_o6_activity_scheduling",
            "reasoning_trace": {
                "workload": estimate["reason"],
                "capacity": decision["status_reason"],
                "confirmation": (
                    "The learner explicitly confirmed the workload, capacity, "
                    "strategy, and any scope change before plan v1 was created."
                ),
            },
            "coverage_warnings": estimate.get("coverage_warnings") or [],
        }
        profile_snapshot = dict(draft.get("profile_snapshot") or {})
        sources = list(
            dict.fromkeys(
                str(item.get("source_type") or item.get("source_mode") or "unknown")
                for item in estimate.get("estimate_sources") or []
            )
        )
        record = self.backend.plans.save_plan(
            user_id,
            plan,
            estimate.get("mode") or "fallback",
            sources,
            path_id=path_id,
            goal_text=effective_goal_text,
            profile_snapshot=profile_snapshot,
        )
        context_preview = dict(draft.get("path_context_preview") or {})
        path_context = {
            "path_id": path_id,
            "user_id": user_id,
            "goal_text": effective_goal_text,
            "outcome_type": "knowledge_and_application",
            "target_concepts": [item["concept_id"] for item in concept_path],
            "target_mastery": dict(context_preview.get("target_mastery") or {}),
            "target_days": effective_days,
            "deadline": decision.get("deadline"),
            "max_daily_minutes": decision["max_available_daily_minutes"],
            "source_mode": estimate.get("source_mode") or "kg_only",
            "preference_overrides": dict(
                context_preview.get("preference_overrides") or {}
            ),
            "current_affective_state": dict(
                context_preview.get("current_affective_state") or {}
            ),
            "profile_snapshot": profile_snapshot,
            "workload_estimate_id": estimate["estimate_id"],
            "feasibility_decision_id": decision_id,
            "status": "awaiting_schedule",
            "schema_version": 2,
        }
        self.backend.contracts.save_path_context(record["plan_id"], path_context)
        links = self._document_links(user_id, draft, path_id)
        self.store.save_document_links(path_id, links)
        decision["path_id"] = path_id
        decision["plan_id"] = record["plan_id"]
        decision["effective_days"] = effective_days
        decision["user_confirmed_at"] = _now_iso()
        decision["status_before_confirmation"] = decision["status"]
        decision["status"] = "confirmed"
        decision["options"] = []
        saved = self.store.save(decision)
        draft["status"] = "path_confirmed"
        draft["path_id"] = path_id
        draft["plan_id"] = record["plan_id"]
        draft["feasibility_decision_id"] = decision_id
        draft["updated_at"] = _now_iso()
        self.onboarding_store.save(draft)
        return {
            "decision": saved,
            "plan": self.backend.plans.get_plan(record["plan_id"]),
            "path_context": path_context,
            "document_links": links,
        }

    def _estimate(self, user_id: str, estimate_id: str) -> dict[str, Any]:
        estimate = self.workload_store.get(user_id, estimate_id)
        if not estimate:
            raise FeasibilityValidationError(
                "Final workload estimate was not found for this user"
            )
        if not estimate.get("is_final") or not estimate.get("estimate_is_final"):
            raise FeasibilityValidationError(
                "Capacity negotiation requires a final workload estimate"
            )
        return estimate

    def _decision(self, user_id: str, decision_id: str) -> dict[str, Any]:
        decision = self.store.get(user_id, decision_id)
        if not decision:
            raise FeasibilityDecisionNotFoundError(decision_id)
        return decision

    def _scope_change(
        self,
        *,
        user_id: str,
        estimate_id: str,
        removed_concept_ids: list[str],
    ) -> dict[str, Any]:
        estimate = self._estimate(user_id, estimate_id)
        available = {
            str(item["concept_id"]) for item in estimate.get("concept_path") or []
        }
        removed = list(dict.fromkeys(str(item) for item in removed_concept_ids))
        if not removed:
            raise FeasibilityValidationError(
                "At least one concept is required for a scope-change draft"
            )
        unknown = set(removed) - available
        if unknown:
            raise FeasibilityValidationError(
                "Scope change contains concepts outside the current path: "
                + ", ".join(sorted(unknown))
            )
        if set(removed) == available:
            raise FeasibilityValidationError(
                "A scope change cannot remove every learning concept"
            )
        removed_set = set(removed)
        broken_dependents = [
            str(item["concept_id"])
            for item in estimate.get("concept_path") or []
            if item["concept_id"] not in removed_set
            and removed_set.intersection(item.get("prerequisite_ids") or [])
        ]
        if broken_dependents:
            raise FeasibilityValidationError(
                "Scope change would remove a prerequisite required by: "
                + ", ".join(sorted(broken_dependents))
                + ". Remove the dependent target too or keep its prerequisite."
            )
        remaining_activities = self._filter_activities(
            estimate.get("activities") or [], set(removed)
        )
        proposed_total = sum(
            int(item["estimated_minutes"]) for item in remaining_activities
        )
        original_total = int(estimate["total_required_minutes"])
        return {
            "scope_change_id": str(uuid.uuid4()),
            "status": "pending",
            "removed_concept_ids": removed,
            "remaining_concept_ids": sorted(available - set(removed)),
            "original_total_minutes": original_total,
            "proposed_total_minutes": proposed_total,
            "removed_minutes": original_total - proposed_total,
            "retained_required_reading": True,
            "proposed_goal_text": (
                "Partial goal: complete "
                + ", ".join(sorted(available - set(removed)))
                + "; defer "
                + ", ".join(sorted(removed))
            ),
            "impact": (
                "The removed concepts and their exclusive activities will be "
                "deferred. Mandatory reading remains unless its document scope "
                "is separately revised and reconfirmed."
            ),
            "created_at": _now_iso(),
        }

    @staticmethod
    def _decide_scope_change(
        decision: dict[str, Any],
        scope_change_decision: str,
    ) -> None:
        scope = decision.get("scope_change_draft")
        if not scope or scope.get("status") != "pending":
            raise FeasibilityValidationError(
                "No pending scope-change draft is available"
            )
        action = scope_change_decision.strip().lower()
        if action not in {"accept", "reject"}:
            raise FeasibilityValidationError(
                "scope_change_decision must be accept or reject"
            )
        scope["status"] = "accepted" if action == "accept" else "rejected"
        scope["decided_at"] = _now_iso()

    @staticmethod
    def _effective_total(decision: dict[str, Any]) -> int:
        scope = decision.get("scope_change_draft")
        if scope and scope.get("status") == "accepted":
            return int(scope["proposed_total_minutes"])
        return int(decision["workload_total_minutes"])

    @classmethod
    def _effective_scope(
        cls,
        estimate: dict[str, Any],
        decision: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        scope = decision.get("scope_change_draft")
        removed = (
            set(scope["removed_concept_ids"])
            if scope and scope.get("status") == "accepted"
            else set()
        )
        concepts = [
            dict(item)
            for item in estimate.get("concept_path") or []
            if item["concept_id"] not in removed
        ]
        if concepts and not any(item.get("is_target") for item in concepts):
            concepts[-1]["is_target"] = True
            concepts[-1]["planning_reason"] = (
                str(concepts[-1].get("planning_reason") or "")
                + " This node becomes the explicit endpoint of the accepted partial goal."
            ).strip()
        activities = cls._filter_activities(
            estimate.get("activities") or [], removed
        )
        return concepts, activities

    @staticmethod
    def _filter_activities(
        activities: list[dict[str, Any]],
        removed: set[str],
    ) -> list[dict[str, Any]]:
        filtered = []
        for activity in activities:
            concept_ids = set(activity.get("concept_ids") or [])
            if (
                activity.get("activity_type") != "required_reading"
                and concept_ids
                and concept_ids.issubset(removed)
            ):
                continue
            filtered.append(activity)
        return filtered

    def _document_links(
        self,
        user_id: str,
        draft: dict[str, Any],
        path_id: str,
    ) -> list[dict[str, Any]]:
        interpretation_id = draft.get("goal_interpretation_id")
        if not interpretation_id:
            return []
        interpretation = self.goal_interpretations.get(user_id, interpretation_id)
        if not interpretation or interpretation.get("status") != "confirmed":
            raise FeasibilityValidationError(
                "Linked goal interpretation is no longer confirmed"
            )
        links = []
        for selection in interpretation.get("documents") or []:
            document = self.documents.get_document(
                user_id, selection["document_id"]
            )
            if not document:
                if selection.get("required"):
                    raise FeasibilityValidationError(
                        "A required document is no longer available"
                    )
                continue
            links.append(
                {
                    "path_id": path_id,
                    "document_id": selection["document_id"],
                    "role": selection.get("role") or "supplementary",
                    "required": bool(selection.get("required")),
                    "included_pages": selection.get("included_pages") or [],
                    "excluded_pages": selection.get("excluded_pages") or [],
                    "included_sections": selection.get("included_sections") or [],
                    "excluded_sections": selection.get("excluded_sections") or [],
                    "source_priority": 1 if selection.get("required") else 0,
                }
            )
        return links
