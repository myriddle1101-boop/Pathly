from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.adaptation_candidate_service import AdaptationCandidateService
from agents.content_context_service import ContentContextService
from infra.config import GLOBAL_KG_JSON
from infra.kg_repository_factory import create_kg_repository
from infra.profile_schema import LearnerProfile


def run_agent_context_smoke(
    concept_id: str,
    backend: str = "json",
    graph_path: Path | None = None,
    top_k: int = 5,
    known_topics: list[str] | None = None,
    prior_knowledge_level: int = 1,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "backend": backend,
        "graph_path": str(graph_path) if graph_path else None,
        "concept_id": concept_id,
        "content_context": None,
        "adaptation_candidates": None,
        "checks": [],
        "passed": False,
        "error": None,
    }
    try:
        repository = create_kg_repository(graph_path=str(graph_path) if graph_path else None, backend=backend)
        smoke_profile = LearnerProfile(
            user_id="smoke",
            name="Smoke Test",
            academic_level="undergraduate",
            domain="ml",
            goal_text=f"learn {concept_id}",
            target_days=7,
            daily_minutes=60,
            prior_knowledge_level=prior_knowledge_level,
            math_foundation=1,
            programming_foundation=1,
            self_regulation=3,
            known_topics=known_topics or [],
        )
        content_context = ContentContextService(repository).build_context(
            concept_id,
            top_k=top_k,
            learner_profile=smoke_profile,
        )
        adaptation_candidates = AdaptationCandidateService(repository).suggest_candidates(concept_id, limit=top_k)

        result["content_context"] = {
            "concept_found": content_context["kg_context"].get("concept") is not None,
            "prerequisites": content_context["kg_context"].get("prerequisites", []),
            "similar": content_context["kg_context"].get("similar", []),
            "resources": content_context["kg_context"].get("resources", []),
            "recommended_resources": content_context.get("recommended_resources", []),
            "rag_chunks": len(content_context.get("rag_chunks", [])),
            "generation_ready": content_context.get("generation_ready", False),
            "boundaries": content_context.get("boundaries", {}),
        }
        result["adaptation_candidates"] = {
            "concept_found": adaptation_candidates.get("concept_found", False),
            "candidate_count": len(adaptation_candidates.get("candidates", [])),
            "candidates": adaptation_candidates.get("candidates", []),
            "decision_policy": adaptation_candidates.get("decision_policy"),
            "boundaries": adaptation_candidates.get("boundaries", {}),
        }

        checks = [
            {
                "name": "content_concept_found",
                "passed": result["content_context"]["concept_found"],
            },
            {
                "name": "adaptation_concept_found",
                "passed": result["adaptation_candidates"]["concept_found"],
            },
            {
                "name": "content_does_not_access_profile_store",
                "passed": result["content_context"]["boundaries"].get("profile_store") == "not accessed",
            },
            {
                "name": "adaptation_does_not_update_profile_store",
                "passed": result["adaptation_candidates"]["boundaries"].get("profile_store") == "not updated",
            },
            {
                "name": "llm_generation_not_executed",
                "passed": result["content_context"]["boundaries"].get("llm_generation") == "not executed"
                and result["adaptation_candidates"]["boundaries"].get("llm_generation") == "not executed",
            },
        ]
        result["checks"] = checks
        result["passed"] = all(check["passed"] for check in checks)
    except Exception as exc:
        result["error"] = str(exc)
        result["passed"] = False
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test Content/Adaptation KG context retrieval.")
    parser.add_argument("--concept", required=True, help="Concept id to inspect")
    parser.add_argument("--backend", default="json", choices=["json", "neo4j"], help="KG backend to use")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge_graph.json for JSON backend")
    parser.add_argument("--top-k", type=int, default=5, help="Number of similar/remediation candidates")
    parser.add_argument("--known-topic", action="append", default=[], help="Known topic for resource recommendation smoke")
    parser.add_argument("--prior-knowledge-level", type=int, default=1, help="Prior knowledge fallback level")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_agent_context_smoke(
        concept_id=args.concept,
        backend=args.backend,
        graph_path=Path(args.graph).resolve(),
        top_k=args.top_k,
        known_topics=args.known_topic,
        prior_knowledge_level=args.prior_knowledge_level,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
