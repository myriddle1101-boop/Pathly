from __future__ import annotations

from typing import Any


class AdaptationCandidateService:
    def __init__(self, kg_repository):
        self.kg_repository = kg_repository

    def suggest_candidates(self, weak_concept: str, limit: int = 5) -> dict[str, Any]:
        context = self.kg_repository.get_concept_context(weak_concept, similar_limit=limit)
        candidates = []
        for item in context.get("similar", []):
            candidates.append(
                {
                    "concept_id": item["name"],
                    "source": "similarity",
                    "score": float(item.get("score", 0.0)),
                    "reason": f"Similar concept to {weak_concept}.",
                }
            )

        if not candidates:
            for concept_id in context.get("prerequisites", [])[:limit]:
                candidates.append(
                    {
                        "concept_id": concept_id,
                        "source": "prerequisite",
                        "score": 0.0,
                        "reason": f"Prerequisite bridge for {weak_concept}.",
                    }
                )

        return {
            "weak_concept": weak_concept,
            "concept_found": context.get("concept") is not None,
            "candidates": candidates[:limit],
            "decision_policy": "similarity_first_then_prerequisite_bridge",
            "boundaries": {
                "kg_layer": "read-only candidate retrieval",
                "profile_store": "not updated",
                "planning_calendar": "not reallocated",
                "llm_generation": "not executed",
            },
        }
