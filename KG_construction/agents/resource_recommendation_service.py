from __future__ import annotations

from typing import Any

from infra.profile_schema import LearnerProfile


def _as_float(value: Any, default: float = 3.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _clamp_difficulty(value: float) -> float:
    return max(1.0, min(5.0, value))


class ResourceRecommendationService:
    def rank_resources(
        self,
        concept_id: str,
        learner_profile: LearnerProfile,
        kg_context: dict[str, Any],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        concept = kg_context.get("concept") or {}
        concept_difficulty = _clamp_difficulty(_as_float(concept.get("difficulty_level"), default=3.0))
        known_topics = {str(topic).lower() for topic in learner_profile.known_topics}
        prerequisites = {str(topic).lower() for topic in kg_context.get("prerequisites", [])}

        if concept_id.lower() in known_topics:
            target_difficulty = _clamp_difficulty(concept_difficulty + 1)
            reason = "Target concept already known; recommending slightly more advanced resources."
        elif known_topics & prerequisites or (not known_topics and learner_profile.prior_knowledge_level >= 4):
            target_difficulty = concept_difficulty
            reason = "Related prerequisite knowledge detected; matching concept difficulty."
        else:
            target_difficulty = _clamp_difficulty(concept_difficulty - 1)
            reason = "No related prerequisite knowledge detected; recommending more foundational resources."

        ranked = []
        for resource in kg_context.get("resources", []):
            if not resource.get("id"):
                continue
            resource_difficulty = _clamp_difficulty(
                _as_float(resource.get("resource_difficulty"), default=concept_difficulty)
            )
            difficulty_gap = abs(resource_difficulty - target_difficulty)
            item = dict(resource)
            item["resource_difficulty"] = round(resource_difficulty, 4)
            item["target_resource_difficulty"] = round(target_difficulty, 4)
            item["difficulty_gap"] = round(difficulty_gap, 4)
            item["match_reason"] = reason
            ranked.append(item)

        ranked.sort(
            key=lambda item: (
                item["difficulty_gap"],
                str(item.get("filename") or item.get("title") or item.get("id")),
                str(item.get("id")),
            )
        )
        return ranked[:top_k]
