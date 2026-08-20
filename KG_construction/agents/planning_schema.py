from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PlanningRequest:
    goal_text: str
    target_concepts: list[str]
    requested_days: int
    daily_minutes: int
    constraints: list[str] = field(default_factory=list)
    learning_style_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DayPlan:
    day: int
    focus_topics: list[str]
    prerequisite_bridge: list[str]
    estimated_minutes: int
    difficulty_mix: list[int]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
