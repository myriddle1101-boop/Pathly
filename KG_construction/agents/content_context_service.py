from __future__ import annotations

from typing import Any

from agents.resource_recommendation_service import ResourceRecommendationService
from infra.profile_schema import LearnerProfile


class ContentContextService:
    def __init__(self, kg_repository, rag_repository=None):
        self.kg_repository = kg_repository
        self.rag_repository = rag_repository
        self.resource_recommender = ResourceRecommendationService()

    def build_context(
        self,
        concept_id: str,
        top_k: int = 5,
        learner_profile: LearnerProfile | None = None,
    ) -> dict[str, Any]:
        kg_context = self.kg_repository.get_concept_context(concept_id, similar_limit=top_k)
        recommended_resources = []
        if learner_profile is not None:
            recommended_resources = self.resource_recommender.rank_resources(
                concept_id=concept_id,
                learner_profile=learner_profile,
                kg_context=kg_context,
                top_k=top_k,
            )

        rag_chunks = []
        if self.rag_repository is not None:
            if recommended_resources and hasattr(self.rag_repository, "get_chunks_by_resource_and_topic"):
                rag_chunks = self.rag_repository.get_chunks_by_resource_and_topic(
                    resource_id=str(recommended_resources[0]["id"]),
                    topic_name=concept_id,
                    top_k=top_k,
                )
            if not rag_chunks:
                rag_chunks = self.rag_repository.get_chunks_by_topic(concept_id, top_k=top_k)

        return {
            "concept_id": concept_id,
            "kg_context": kg_context,
            "recommended_resources": recommended_resources,
            "rag_chunks": rag_chunks,
            "generation_ready": bool(kg_context.get("concept")) and bool(rag_chunks),
            "boundaries": {
                "kg_layer": "Neo4j/JSON structure context only",
                "profile_store": "not accessed",
                "rag_layer": "retrieval only",
                "llm_generation": "not executed",
            },
        }
