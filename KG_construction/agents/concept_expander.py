from __future__ import annotations

import math
import re
from typing import Any

from infra.profile_schema import LearnerProfile


class ConceptExpander:
    """Builds a source-grounded concept path and capacity-first workload estimate."""

    def __init__(self, repository, min_unit_minutes: int = 15, max_unit_minutes: int = 30):
        self.repository = repository
        self.min_unit_minutes = max(5, min_unit_minutes)
        self.max_unit_minutes = max(self.min_unit_minutes, max_unit_minutes)

    def expand(
        self,
        ordered_topics: list[str],
        target_topics: list[str],
        profile: LearnerProfile,
        requested_days: int,
        available_daily_minutes: int,
    ) -> dict[str, Any]:
        days = max(1, int(requested_days))
        daily_capacity = max(1, int(available_daily_minutes))
        targets = set(target_topics)
        concept_path = []
        concept_units = []
        coverage_warnings = []

        for order, topic in enumerate(dict.fromkeys(ordered_topics), start=1):
            attrs = self.repository.get_topic(topic) or {"id": topic}
            canonical = str(attrs.get("id") or topic)
            prerequisites = self._prerequisites(canonical)
            estimate = self._estimate_topic_minutes(canonical, attrs, profile)
            units = self._split_into_units(
                canonical,
                estimate["adjusted_minutes"],
                max_unit_minutes=min(self.max_unit_minutes, daily_capacity),
            )
            concept_units.extend(units)
            concept_path.append(
                {
                    "concept_id": canonical,
                    "title": canonical,
                    "order": order,
                    "is_target": canonical in targets,
                    "prerequisite_ids": prerequisites,
                    "relationship_source": [
                        {"type": "prerequisite", "from": prerequisite, "to": canonical}
                        for prerequisite in prerequisites
                    ],
                    "difficulty": estimate["difficulty"],
                    "estimated_total_minutes": estimate["adjusted_minutes"],
                    "mastery_before": estimate["mastery_score"],
                    "planning_reason": self._planning_reason(
                        canonical,
                        canonical in targets,
                        prerequisites,
                        estimate,
                    ),
                    "source_mode": self._source_mode(),
                    "units": units,
                }
            )

        if not concept_path:
            coverage_warnings.append("No source-grounded concept path could be built.")
        for target in sorted(targets):
            target_node = next((node for node in concept_path if node["concept_id"] == target), None)
            if target_node and not target_node["prerequisite_ids"] and len(concept_path) <= 2:
                coverage_warnings.append(
                    f"Knowledge graph coverage for {target} is sparse; no prerequisites were found."
                )

        concept_minutes = sum(unit["estimated_minutes"] for unit in concept_units)
        capacity = days * daily_capacity
        gap = capacity - concept_minutes
        if gap < 0:
            capacity_status = "insufficient"
        elif gap >= daily_capacity:
            capacity_status = "excess"
        else:
            capacity_status = "feasible"

        workload_estimate = {
            "concept_learning_minutes": concept_minutes,
            "activity_minutes": 0,
            "total_required_minutes": concept_minutes,
            "estimate_scope": "concept_path_only",
            "is_final": False,
            "requested_days": days,
            "available_daily_minutes": daily_capacity,
            "available_capacity_minutes": capacity,
            "recommended_daily_minutes": math.ceil(concept_minutes / days) if concept_minutes else 0,
            "minimum_recommended_days": math.ceil(concept_minutes / daily_capacity) if concept_minutes else 0,
            "capacity_gap_minutes": gap,
            "additional_minutes_needed": max(-gap, 0),
            "capacity_status": capacity_status,
            "reason": (
                "This provisional estimate includes source-grounded concept learning only. "
                "Practice, review, assessment, and project minutes will be added in Stage 4.2."
            ),
        }
        return {
            "concept_path": concept_path,
            "concept_units": concept_units,
            "workload_estimate": workload_estimate,
            "coverage_warnings": list(dict.fromkeys(coverage_warnings)),
        }

    def _source_mode(self) -> str:
        return "neo4j" if "neo4j" in type(self.repository).__name__.lower() else "json"

    def _prerequisites(self, topic: str) -> list[str]:
        getter = getattr(self.repository, "get_prerequisites", None)
        return sorted(dict.fromkeys(getter(topic) if getter else []))

    def _estimate_topic_minutes(
        self,
        topic: str,
        attrs: dict[str, Any],
        profile: LearnerProfile,
    ) -> dict[str, Any]:
        base_minutes = self._parse_minutes(attrs.get("estimated_learning_time", "90"))
        difficulty = self._difficulty(attrs)
        difficulty_factor = 1 + 0.15 * (difficulty - 1)
        pace_factor = {"slow": 1.2, "medium": 1.0, "fast": 0.85}.get(
            profile.pace_preference,
            1.0,
        )
        mastery_score = self._topic_score(profile.mastery_vector, topic)
        skill_tree_score = self._topic_score(profile.skill_tree, topic)
        mastery_factor = self._mastery_factor(mastery_score)
        skill_factor = self._skill_tree_factor(skill_tree_score)
        profile_factor = self._profile_factor(profile, difficulty)
        adjusted = max(
            self.min_unit_minutes,
            math.ceil(
                base_minutes
                * difficulty_factor
                * pace_factor
                * mastery_factor
                * skill_factor
                * profile_factor
            ),
        )
        return {
            "base_minutes": base_minutes,
            "difficulty": difficulty,
            "difficulty_factor": round(difficulty_factor, 4),
            "pace_factor": round(pace_factor, 4),
            "mastery_score": mastery_score,
            "mastery_factor": round(mastery_factor, 4),
            "skill_tree_score": skill_tree_score,
            "skill_tree_factor": round(skill_factor, 4),
            "profile_factor": round(profile_factor, 4),
            "adjusted_minutes": adjusted,
        }

    def _split_into_units(
        self,
        concept_id: str,
        total_minutes: int,
        max_unit_minutes: int | None = None,
    ) -> list[dict[str, Any]]:
        unit_limit = max(1, max_unit_minutes or self.max_unit_minutes)
        count = max(1, math.ceil(total_minutes / unit_limit))
        base, remainder = divmod(total_minutes, count)
        units = []
        for index in range(count):
            minutes = base + (1 if index < remainder else 0)
            units.append(
                {
                    "unit_id": f"{concept_id}::concept::{index + 1}",
                    "unit_type": "concept_segment",
                    "concept_id": concept_id,
                    "title": f"{concept_id} · Part {index + 1}/{count}",
                    "estimated_minutes": minutes,
                    "sequence": index + 1,
                    "source_mode": self._source_mode(),
                }
            )
        return units

    def _parse_minutes(self, value: Any) -> int:
        text = str(value or "90").strip().lower()
        hour_match = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*hour", text)
        chinese_hour_match = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*小时", text)
        minute_match = re.search(r"(\d+)\s*min", text)
        chinese_minute_match = re.search(r"(\d+)\s*分钟", text)
        if hour_match or chinese_hour_match:
            match = hour_match or chinese_hour_match
            first = int(match.group(1))
            second = int(match.group(2)) if match.group(2) else first
            return max(self.min_unit_minutes, int(((first + second) / 2) * 60))
        if minute_match or chinese_minute_match:
            match = minute_match or chinese_minute_match
            return max(self.min_unit_minutes, int(match.group(1)))
        return 90

    def _difficulty(self, attrs: dict[str, Any]) -> int:
        try:
            value = int(float(attrs.get("difficulty_level", 3)))
        except (TypeError, ValueError):
            value = 3
        return min(5, max(1, value))

    def _topic_score(self, scores: dict[str, float], topic: str) -> float | None:
        canonical = topic.strip().lower()
        for raw_topic, raw_score in scores.items():
            node = self.repository.get_topic(raw_topic)
            raw_canonical = str((node or {"id": raw_topic})["id"]).strip().lower()
            if raw_canonical != canonical:
                continue
            try:
                return round(float(raw_score), 4)
            except (TypeError, ValueError):
                return None
        return None

    def _mastery_factor(self, score: float | None) -> float:
        if score is None:
            return 1.0
        return min(1.2, max(0.7, 1.2 - 0.6 * score))

    def _skill_tree_factor(self, score: float | None) -> float:
        if score is None:
            return 1.0
        return min(1.15, max(0.75, 1.15 - 0.4 * score))

    def _profile_factor(self, profile: LearnerProfile, difficulty: int) -> float:
        foundation_avg = (profile.math_foundation + profile.programming_foundation) / 2
        anxiety_penalty = max(profile.anxiety_level - profile.confidence_level, 0) * 0.03
        motivation_bonus = max(profile.motivation_level - 3, 0) * 0.02
        regulation_bonus = max(profile.self_regulation - 3, 0) * 0.015
        foundation_penalty = max(3 - foundation_avg, 0) * 0.04 * (
            1.0 if difficulty >= 3 else 0.5
        )
        confidence_bonus = max(profile.confidence_level - profile.anxiety_level, 0) * 0.015
        factor = (
            1.0
            + anxiety_penalty
            + foundation_penalty
            - motivation_bonus
            - regulation_bonus
            - confidence_bonus
        )
        return min(1.35, max(0.85, round(factor, 4)))

    def _planning_reason(
        self,
        topic: str,
        is_target: bool,
        prerequisites: list[str],
        estimate: dict[str, Any],
    ) -> str:
        role = "core target" if is_target else "required prerequisite"
        prerequisite_text = (
            f"after {', '.join(prerequisites)}"
            if prerequisites
            else "with no recorded prerequisite"
        )
        return (
            f"{topic} is a {role}, scheduled {prerequisite_text}; "
            f"{estimate['base_minutes']} base minutes adjusted to "
            f"{estimate['adjusted_minutes']} minutes using difficulty, pace, "
            "foundation, mastery, and confidence signals."
        )
