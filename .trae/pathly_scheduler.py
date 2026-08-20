"""Deterministic activity scheduling for confirmed Pathly plans."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from copy import deepcopy
from typing import Any

from pathly_backend import PathlyBackend


class ScheduleValidationError(ValueError):
    pass


class ScheduleNotFoundError(KeyError):
    pass


ACTIVITY_PRIORITY = {
    "required_reading": 0,
    "explanation": 1,
    "example": 2,
    "practice": 3,
    "code": 4,
    "quiz": 5,
    "project": 6,
    "reflection": 7,
}


class ActivityScheduler:
    REVIEW_OFFSETS = (1, 3, 7, 14)

    def schedule(self, plan: dict[str, Any]) -> dict[str, Any]:
        feasibility = plan.get("feasibility") or {}
        days = int(
            feasibility.get("effective_days")
            or feasibility.get("requested_days")
            or 0
        )
        capacity = int(feasibility.get("max_available_daily_minutes") or 0)
        if days < 1 or capacity < 1:
            raise ScheduleValidationError(
                "Confirmed days and daily capacity are required"
            )
        self._current_capacity = capacity
        concept_path = deepcopy(plan.get("concept_path") or [])
        activities = deepcopy(plan.get("activities") or [])
        if not concept_path or not activities:
            raise ScheduleValidationError(
                "A confirmed concept path and activities are required"
            )
        slots = [
            {"day": day, "activities": [], "total_minutes": 0}
            for day in range(1, days + 1)
        ]
        concept_order = {
            item["concept_id"]: index for index, item in enumerate(concept_path)
        }
        reviews = [
            item for item in activities if item.get("activity_type") == "review"
        ]
        core = [
            item for item in activities if item.get("activity_type") != "review"
        ]
        core.sort(
            key=lambda item: (
                min(
                    (
                        concept_order.get(concept_id, len(concept_order))
                        for concept_id in item.get("concept_ids") or []
                    ),
                    default=len(concept_order),
                ),
                ACTIVITY_PRIORITY.get(item.get("activity_type"), 99),
                int(item.get("sequence") or 0),
                item.get("activity_id") or "",
            )
        )
        unscheduled: list[dict[str, Any]] = []
        concept_first_day: dict[str, int] = {}
        concept_last_day: dict[str, int] = {}
        cursor = 1
        for activity in core:
            concept_ids = list(activity.get("concept_ids") or [])
            prerequisite_days = []
            for concept_id in concept_ids:
                node = next(
                    (
                        item
                        for item in concept_path
                        if item["concept_id"] == concept_id
                    ),
                    {},
                )
                prerequisite_days.extend(
                    concept_last_day.get(prerequisite, 0)
                    for prerequisite in node.get("prerequisite_ids") or []
                )
            earliest = max([cursor, *prerequisite_days, 1])
            placed, cursor = self._place_activity(
                slots, activity, earliest_day=earliest
            )
            if placed:
                for concept_id in concept_ids:
                    concept_first_day.setdefault(concept_id, placed[0])
                    concept_last_day[concept_id] = placed[-1]
            else:
                unscheduled.append(
                    self._unscheduled(activity, "daily_capacity_or_horizon")
                )

        for review in reviews:
            concept_ids = list(review.get("concept_ids") or [])
            intro_day = min(
                (
                    concept_first_day[concept_id]
                    for concept_id in concept_ids
                    if concept_id in concept_first_day
                ),
                default=0,
            )
            if not intro_day:
                unscheduled.append(
                    self._unscheduled(review, "concept_introduction_not_scheduled")
                )
                continue
            offsets = [
                offset
                for offset in self.REVIEW_OFFSETS
                if intro_day + offset <= days
            ]
            if not offsets:
                unscheduled.append(
                    self._unscheduled(review, "review_interval_outside_horizon")
                )
                continue
            total = int(review.get("estimated_minutes") or 0)
            base, remainder = divmod(total, len(offsets))
            remaining = 0
            for index, offset in enumerate(offsets):
                minutes = base + (1 if index < remainder else 0)
                if minutes <= 0:
                    continue
                part = {
                    **review,
                    "activity_id": f"{review['activity_id']}::review+{offset}",
                    "estimated_minutes": minutes,
                    "review_offset_days": offset,
                    "parent_activity_id": review["activity_id"],
                }
                placed, _ = self._place_activity(
                    slots,
                    part,
                    earliest_day=intro_day + offset,
                    latest_day=intro_day + offset,
                )
                if not placed:
                    remaining += minutes
            if remaining:
                unscheduled.append(
                    {
                        **self._unscheduled(
                            review, "review_interval_capacity_conflict"
                        ),
                        "estimated_minutes": remaining,
                    }
                )

        optional = []
        if feasibility.get("selected_strategy") == "paced_consolidation":
            optional = self._add_consolidation(
                slots,
                concept_path,
                int(feasibility.get("capacity_gap_minutes") or 0),
                capacity,
            )

        timeline = []
        for slot in slots:
            if not slot["activities"]:
                continue
            topics = []
            for activity in slot["activities"]:
                topics.extend(activity.get("concept_ids") or [])
            timeline.append(
                {
                    **slot,
                    "focus_topics": list(dict.fromkeys(topics)),
                    "required_minutes": sum(
                        int(item["estimated_minutes"])
                        for item in slot["activities"]
                        if not item.get("optional")
                    ),
                    "optional_minutes": sum(
                        int(item["estimated_minutes"])
                        for item in slot["activities"]
                        if item.get("optional")
                    ),
                }
            )
        scheduled_required = sum(
            item["required_minutes"] for item in timeline
        )
        return {
            "days": timeline,
            "unscheduled_activities": unscheduled,
            "scheduled_required_minutes": scheduled_required,
            "scheduled_optional_minutes": sum(
                item["optional_minutes"] for item in timeline
            ),
            "optional_consolidation_activities": optional,
            "confirmed_horizon_days": days,
            "max_daily_minutes": capacity,
            "schedule_status": "complete" if not unscheduled else "partial",
            "review_offsets_supported": list(self.REVIEW_OFFSETS),
            "reason": (
                "Activities are scheduled deterministically in prerequisite-safe "
                "order. Reviews reuse O4 review minutes at available spaced "
                "intervals; unscheduled work is retained explicitly."
            ),
        }

    def _place_activity(
        self,
        slots: list[dict[str, Any]],
        activity: dict[str, Any],
        *,
        earliest_day: int,
        latest_day: int | None = None,
    ) -> tuple[list[int], int]:
        remaining = int(activity.get("estimated_minutes") or 0)
        if remaining <= 0:
            return [], earliest_day
        capacity = max(
            (
                int(slot.get("_capacity") or 0)
                for slot in slots
                if slot.get("_capacity")
            ),
            default=0,
        )
        if not capacity:
            # The caller's slots have equal capacity; infer it from a sentinel
            # placed temporarily by schedule().
            capacity = getattr(self, "_current_capacity", 0)
        placed_days = []
        end = latest_day or len(slots)
        for day in range(max(1, earliest_day), min(len(slots), end) + 1):
            slot = slots[day - 1]
            room = self._current_capacity - slot["total_minutes"]
            if room <= 0:
                continue
            minutes = min(room, remaining)
            part = {
                **activity,
                "activity_id": (
                    activity["activity_id"]
                    if minutes == int(activity.get("estimated_minutes") or 0)
                    else f"{activity['activity_id']}::part{len(placed_days) + 1}"
                ),
                "parent_activity_id": activity.get("parent_activity_id")
                or activity["activity_id"],
                "estimated_minutes": minutes,
            }
            slot["activities"].append(part)
            slot["total_minutes"] += minutes
            remaining -= minutes
            placed_days.append(day)
            if remaining <= 0:
                return placed_days, day
        if remaining and placed_days:
            # Keep the placed portion and report only the remainder upstream.
            activity["estimated_minutes"] = remaining
        return ([] if remaining else placed_days), min(end + 1, len(slots))

    def _add_consolidation(
        self,
        slots: list[dict[str, Any]],
        concept_path: list[dict[str, Any]],
        budget: int,
        capacity: int,
    ) -> list[dict[str, Any]]:
        remaining = max(0, budget)
        generated = []
        topics = [item["concept_id"] for item in concept_path]
        for slot in slots:
            if remaining <= 0:
                break
            room = capacity - slot["total_minutes"]
            if room <= 0:
                continue
            minimum = min(15, room, remaining)
            if not slot["activities"] and minimum <= 0:
                continue
            minutes = min(room, remaining, max(15, min(30, remaining)))
            if minutes <= 0:
                continue
            activity = {
                "activity_id": f"consolidation::day{slot['day']}",
                "activity_type": "consolidation",
                "concept_ids": topics,
                "title": f"Optional consolidation · Day {slot['day']}",
                "estimated_minutes": minutes,
                "source": "paced_consolidation",
                "reason": "Uses confirmed surplus capacity for meaningful reinforcement.",
                "required": False,
                "optional": True,
            }
            slot["activities"].append(activity)
            slot["total_minutes"] += minutes
            generated.append(activity)
            remaining -= minutes
        return generated

    @staticmethod
    def _unscheduled(activity: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "activity_id": activity.get("activity_id"),
            "activity_type": activity.get("activity_type"),
            "concept_ids": list(activity.get("concept_ids") or []),
            "estimated_minutes": int(activity.get("estimated_minutes") or 0),
            "reason": reason,
        }


class ScheduleService:
    def __init__(
        self,
        backend: PathlyBackend,
        scheduler: ActivityScheduler | None = None,
    ):
        self.backend = backend
        self.scheduler = scheduler or ActivityScheduler()

    def create(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        record = self.backend.plans.get_plan(plan_id)
        if not record or record["user_id"] != user_id:
            raise ScheduleNotFoundError(plan_id)
        plan = record["plan"]
        if plan.get("schedule_status") != "pending_o6_activity_scheduling":
            if plan.get("schedule", {}).get("input_hash"):
                return record
            raise ScheduleValidationError(
                "Only an O5-confirmed plan awaiting scheduling can be scheduled"
            )
        fingerprint = self._input_hash(record)
        for candidate in self.backend.plans.list_plans(user_id):
            if (
                candidate["path_id"] == record["path_id"]
                and candidate["plan"].get("schedule", {}).get("input_hash")
                == fingerprint
            ):
                return candidate
        self.scheduler._current_capacity = int(
            plan["feasibility"]["max_available_daily_minutes"]
        )
        result = self.scheduler.schedule(plan)
        scheduled_plan = deepcopy(plan)
        scheduled_plan["plan_id"] = str(uuid.uuid4())
        scheduled_plan["days"] = result["days"]
        scheduled_plan["unscheduled_activities"] = result[
            "unscheduled_activities"
        ]
        scheduled_plan["schedule_status"] = result["schedule_status"]
        scheduled_plan["schedule"] = {
            **result,
            "input_hash": fingerprint,
            "source_plan_id": record["plan_id"],
            "algorithm": "deterministic_prerequisite_capacity_scheduler_v1",
        }
        saved = self.backend.plans.save_plan(
            user_id,
            scheduled_plan,
            record["mode"],
            record["sources"],
            path_id=record["path_id"],
            goal_text=record["goal_text"],
            profile_snapshot=record["profile_snapshot"],
        )
        context = dict(record.get("path_context") or {})
        context["status"] = (
            "scheduled"
            if result["schedule_status"] == "complete"
            else "partially_scheduled"
        )
        context["scheduled_plan_id"] = saved["plan_id"]
        self.backend.contracts.save_path_context(saved["plan_id"], context)
        return self.backend.plans.get_plan(saved["plan_id"]) or saved

    def get(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        record = self.backend.plans.get_plan(plan_id)
        if not record or record["user_id"] != user_id:
            raise ScheduleNotFoundError(plan_id)
        candidates = [
            item
            for item in self.backend.plans.list_plans(user_id)
            if item["path_id"] == record["path_id"]
            and item["plan"].get("schedule", {}).get("input_hash")
        ]
        if not candidates:
            raise ScheduleNotFoundError(plan_id)
        return max(candidates, key=lambda item: item["version"])

    @staticmethod
    def _input_hash(record: dict[str, Any]) -> str:
        plan = record["plan"]
        payload = {
            "source_plan_id": record["plan_id"],
            "concept_path": plan.get("concept_path") or [],
            "activities": plan.get("activities") or [],
            "feasibility": plan.get("feasibility") or {},
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
