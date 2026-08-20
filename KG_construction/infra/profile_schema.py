from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class LearnerProfile:
    user_id: str
    name: str
    academic_level: str
    domain: str
    goal_text: str
    target_days: int
    daily_minutes: int
    prior_knowledge_level: int
    math_foundation: int
    programming_foundation: int
    self_regulation: int
    interest_tags: list[str] = field(default_factory=list)
    preferred_style: str = "balanced"
    motivation_level: int = 3
    confidence_level: int = 3
    anxiety_level: int = 2
    known_topics: list[str] = field(default_factory=list)
    skill_tree: dict[str, float] = field(default_factory=dict)
    preferred_examples: list[str] = field(default_factory=list)
    pace_preference: str = "medium"
    mastery_vector: dict[str, float] = field(default_factory=dict)
    completed_topics: list[str] = field(default_factory=list)
    current_day: int = 1
    last_practice: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
