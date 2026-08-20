from __future__ import annotations

import math
import re
from typing import Any

from agents.planning_schema import DayPlan
from infra.kg_repository import KGRepository
from infra.profile_schema import LearnerProfile


class TimeAllocator:
    def __init__(self, repository: KGRepository):
        self.repository = repository

    def allocate(
        self,
        ordered_topics: list[str],
        profile: LearnerProfile,
        requested_days: int,
        daily_minutes: int,
    ) -> dict[str, Any]:
        if requested_days <= 0:
            requested_days = 1
        pace_factor = {"slow": 1.2, "medium": 1.0, "fast": 0.85}.get(profile.pace_preference, 1.0)
        allocation_items = []
        topic_adjustments = []
        total_minutes = 0
        for topic in ordered_topics:
            attrs = self.repository.get_topic(topic) or {"id": topic}
            base_minutes = self._estimate_minutes(attrs)
            difficulty = self._difficulty(attrs)
            difficulty_factor = 1 + 0.15 * (difficulty - 1)
            mastery_score = self._topic_score(profile.mastery_vector, topic)
            skill_tree_score = self._topic_score(profile.skill_tree, topic)
            mastery_factor = self._mastery_factor(mastery_score)
            skill_factor = self._skill_tree_factor(skill_tree_score)
            profile_factor = self._profile_factor(profile, difficulty)
            weighted_minutes = math.ceil(base_minutes * difficulty_factor * pace_factor * mastery_factor * skill_factor * profile_factor)
            allocation_items.append(
                {
                    "topic": topic,
                    "estimated_minutes": weighted_minutes,
                    "difficulty": difficulty,
                    "prerequisite_bridge": self.repository.get_prerequisites(topic),
                }
            )
            topic_adjustments.append(
                {
                    "topic": topic,
                    "base_minutes": base_minutes,
                    "difficulty": difficulty,
                    "difficulty_factor": round(difficulty_factor, 4),
                    "pace_factor": round(pace_factor, 4),
                    "mastery_score": mastery_score,
                    "mastery_factor": round(mastery_factor, 4),
                    "skill_tree_score": skill_tree_score,
                    "skill_tree_factor": round(skill_factor, 4),
                    "profile_factor": round(profile_factor, 4),
                    "adjusted_minutes": weighted_minutes,
                    "adjustment_reason": self._adjustment_reason(
                        profile,
                        mastery_score,
                        skill_tree_score,
                        difficulty,
                        pace_factor,
                        profile_factor,
                    ),
                }
            )
            total_minutes += weighted_minutes

        day_plans: list[DayPlan] = []
        current_topics = []
        current_minutes = 0
        current_difficulties = []
        day_index = 1
        overflow_topics = []
        exceeded_daily_topics = []

        for item in allocation_items:
            if day_index > requested_days:
                overflow_topics.append(item["topic"])
                continue

            if current_topics and current_minutes + item["estimated_minutes"] > daily_minutes:
                day_plans.append(
                    DayPlan(
                        day=day_index,
                        focus_topics=current_topics,
                        prerequisite_bridge=sorted({p for bridge in current_topics for p in self.repository.get_prerequisites(bridge)}),
                        estimated_minutes=current_minutes,
                        difficulty_mix=current_difficulties,
                        reason=self._build_reason(current_minutes, daily_minutes),
                    )
                )
                day_index += 1
                current_topics = []
                current_minutes = 0
                current_difficulties = []

            if day_index > requested_days:
                overflow_topics.append(item["topic"])
                continue

            current_topics.append(item["topic"])
            current_minutes += item["estimated_minutes"]
            current_difficulties.append(item["difficulty"])
            if item["estimated_minutes"] > daily_minutes:
                exceeded_daily_topics.append(item["topic"])

        if current_topics and day_index <= requested_days:
            day_plans.append(
                DayPlan(
                    day=day_index,
                    focus_topics=current_topics,
                    prerequisite_bridge=sorted({p for bridge in current_topics for p in self.repository.get_prerequisites(bridge)}),
                    estimated_minutes=current_minutes,
                    difficulty_mix=current_difficulties,
                    reason=self._build_reason(current_minutes, daily_minutes),
                )
            )

        while len(day_plans) < requested_days:
            day_plans.append(
                DayPlan(
                    day=len(day_plans) + 1,
                    focus_topics=[],
                    prerequisite_bridge=[],
                    estimated_minutes=0,
                    difficulty_mix=[],
                    reason="Reserved for review, rest, or buffer.",
                )
            )

        return {
            "days": [day.to_dict() for day in day_plans],
            "total_estimated_minutes": total_minutes,
            "overflow_topics": overflow_topics,
            "topic_adjustments": topic_adjustments,
            "feasibility_warning": self._build_warning(
                requested_days=requested_days,
                overflow_topics=overflow_topics,
                exceeded_daily_topics=exceeded_daily_topics,
            ),
        }

    def _estimate_minutes(self, attrs: dict[str, Any]) -> int:
        value = str(attrs.get("estimated_learning_time", "90")).strip().lower()
        hour_match = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*hour", value)
        chinese_hour_match = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*小时", value)
        minute_match = re.search(r"(\d+)\s*min", value)
        if hour_match:
            first = int(hour_match.group(1))
            second = int(hour_match.group(2)) if hour_match.group(2) else first
            return int(((first + second) / 2) * 60)
        if chinese_hour_match:
            first = int(chinese_hour_match.group(1))
            second = int(chinese_hour_match.group(2)) if chinese_hour_match.group(2) else first
            return int(((first + second) / 2) * 60)
        if minute_match:
            return int(minute_match.group(1))
        return 90

    def _difficulty(self, attrs: dict[str, Any]) -> int:
        value = attrs.get("difficulty_level", 3)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return 3

    def _canonical_topic_id(self, topic: str) -> str:
        node = self.repository.get_topic(topic) or {"id": topic}
        return node["id"]

    def _topic_score(self, scores: dict[str, float], topic: str) -> float | None:
        canonical = self._canonical_topic_id(topic).strip().lower()
        for raw_topic, raw_score in scores.items():
            raw_canonical = self._canonical_topic_id(raw_topic).strip().lower()
            if raw_canonical != canonical:
                continue
            try:
                return round(float(raw_score), 4)
            except (TypeError, ValueError):
                return None
        return None

    def _mastery_factor(self, mastery_score: float | None) -> float:
        if mastery_score is None:
            return 1.0
        return min(1.2, max(0.7, 1.2 - 0.6 * mastery_score))

    def _skill_tree_factor(self, skill_tree_score: float | None) -> float:
        if skill_tree_score is None:
            return 1.0
        return min(1.15, max(0.75, 1.15 - 0.4 * skill_tree_score))

    def _profile_factor(self, profile: LearnerProfile, difficulty: int) -> float:
        foundation_avg = (profile.math_foundation + profile.programming_foundation) / 2
        anxiety_penalty = max(profile.anxiety_level - profile.confidence_level, 0) * 0.03
        motivation_bonus = max(profile.motivation_level - 3, 0) * 0.02
        regulation_bonus = max(profile.self_regulation - 3, 0) * 0.015
        foundation_penalty = max(3 - foundation_avg, 0) * 0.04 * (1.0 if difficulty >= 3 else 0.5)
        confidence_bonus = max(profile.confidence_level - profile.anxiety_level, 0) * 0.015
        factor = 1.0 + anxiety_penalty + foundation_penalty - motivation_bonus - regulation_bonus - confidence_bonus
        return min(1.35, max(0.85, round(factor, 4)))

    def _adjustment_reason(
        self,
        profile: LearnerProfile,
        mastery_score: float | None,
        skill_tree_score: float | None,
        difficulty: int,
        pace_factor: float,
        profile_factor: float,
    ) -> str:
        reasons = [f"difficulty level {difficulty}"]
        if mastery_score is None:
            reasons.append("no mastery record")
        else:
            reasons.append(f"mastery score {mastery_score:.2f}")
        if skill_tree_score is None:
            reasons.append("no skill-tree score")
        else:
            reasons.append(f"skill-tree score {skill_tree_score:.2f}")
        reasons.append(f"pace factor {pace_factor:.2f}")
        reasons.append(
            f"profile factor {profile_factor:.2f} from confidence {profile.confidence_level}, anxiety {profile.anxiety_level}, motivation {profile.motivation_level}, self-regulation {profile.self_regulation}, math {profile.math_foundation}, programming {profile.programming_foundation}"
        )
        return "; ".join(reasons)

    def _build_reason(self, current_minutes: int, daily_minutes: int) -> str:
        if current_minutes <= daily_minutes:
            return f"Allocated within {daily_minutes} minutes based on prerequisite order and learner-adjusted workload."
        return f"This day exceeds the preferred {daily_minutes}-minute limit because one or more topics remain heavy after learner-aware adjustment."

    def _build_warning(
        self,
        requested_days: int,
        overflow_topics: list[str],
        exceeded_daily_topics: list[str],
    ) -> str | None:
        warnings = []
        if overflow_topics:
            warnings.append(
                f"Plan exceeds {requested_days} days; remaining topics: {', '.join(overflow_topics)}"
            )
        if exceeded_daily_topics:
            unique_topics = list(dict.fromkeys(exceeded_daily_topics))
            warnings.append(
                f"Some topics individually exceed the daily limit: {', '.join(unique_topics)}"
            )
        if not warnings:
            return None
        return " | ".join(warnings)
