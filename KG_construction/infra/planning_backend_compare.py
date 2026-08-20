from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.path_planner import PathPlanner
from agents.planning_agent import PlanningAgent
from agents.planning_schema import PlanningRequest
from agents.time_allocator import TimeAllocator
from infra.config import GLOBAL_KG_JSON
from infra.kg_repository_factory import create_kg_repository
from infra.profile_schema import LearnerProfile


def _stable_day(day: dict[str, Any]) -> dict[str, Any]:
    return {
        "day": day.get("day"),
        "focus_topics": day.get("focus_topics", []),
        "prerequisite_bridge": day.get("prerequisite_bridge", []),
        "estimated_minutes": day.get("estimated_minutes"),
        "difficulty_mix": day.get("difficulty_mix", []),
    }


def stable_planning_view(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal": {
            "target_concepts": plan.get("goal", {}).get("target_concepts", []),
            "requested_days": plan.get("goal", {}).get("requested_days"),
            "daily_minutes": plan.get("goal", {}).get("daily_minutes"),
        },
        "target_topics": plan.get("target_topics", []),
        "ordered_topics": plan.get("ordered_topics", []),
        "prerequisite_paths": plan.get("prerequisite_paths", {}),
        "covered_prerequisites": plan.get("covered_prerequisites", {}),
        "days": [_stable_day(day) for day in plan.get("days", [])],
        "overflow_topics": plan.get("overflow_topics", []),
    }


def _map_targets_without_embeddings(repository, target_concepts: list[str]) -> dict[str, Any]:
    matched_targets = []
    unmatched_terms = []
    explanations = []
    for concept in target_concepts:
        exact = repository.get_topic(concept)
        if exact:
            matched_targets.append(
                {
                    "query": concept,
                    "matched_name": exact["id"],
                    "score": 1.0,
                    "method": "exact_match",
                }
            )
            explanations.append(f"{concept} -> {exact['id']} (exact_match)")
            continue

        candidates = repository.search_topics(concept, limit=1)
        if candidates:
            best = candidates[0]
            matched_targets.append(
                {
                    "query": concept,
                    "matched_name": best.name,
                    "score": best.score,
                    "method": best.reason,
                }
            )
            explanations.append(f"{concept} -> {best.name} ({best.reason})")
        else:
            unmatched_terms.append(concept)
            explanations.append(f"{concept} -> unmatched")
    return {
        "matched_targets": matched_targets,
        "unmatched_terms": unmatched_terms,
        "mapping_explanations": explanations,
    }


def _make_profile(
    goal_text: str,
    days: int,
    daily_minutes: int,
    known_topics: list[str] | None = None,
) -> LearnerProfile:
    return LearnerProfile(
        user_id="planning-backend-compare",
        name="Planning Backend Compare",
        academic_level="undergraduate",
        domain="machine learning",
        goal_text=goal_text,
        target_days=days,
        daily_minutes=daily_minutes,
        prior_knowledge_level=1,
        math_foundation=2,
        programming_foundation=2,
        self_regulation=3,
        known_topics=known_topics or [],
    )


def _run_deterministic_components(
    backend: str,
    goal_text: str,
    profile: LearnerProfile,
    graph_path: Path | None,
    target_concepts: list[str],
) -> dict[str, Any]:
    repository = create_kg_repository(graph_path=str(graph_path) if graph_path else None, backend=backend)
    request = PlanningRequest(
        goal_text=goal_text,
        target_concepts=target_concepts,
        requested_days=profile.target_days,
        daily_minutes=profile.daily_minutes,
        constraints=["target_concepts_supplied"],
        learning_style_hints=[],
    )
    mapping = _map_targets_without_embeddings(repository, target_concepts)
    target_topics = [item["matched_name"] for item in mapping["matched_targets"]]
    known_topics = [topic for topic in profile.known_topics if repository.get_topic(topic)]
    path_result = PathPlanner(repository).plan(
        targets=target_topics,
        known_topics=known_topics,
        algorithm="astar",
    )
    allocation = TimeAllocator(repository).allocate(
        ordered_topics=path_result["ordered_topics"],
        profile=profile,
        requested_days=request.requested_days,
        daily_minutes=request.daily_minutes,
    )
    return {
        "goal": request.to_dict(),
        "target_topics": target_topics,
        "mapping": mapping,
        "ordered_topics": path_result["ordered_topics"],
        "prerequisite_paths": path_result["prerequisite_paths"],
        "covered_prerequisites": path_result["covered_prerequisites"],
        "days": allocation["days"],
        "overflow_topics": allocation["overflow_topics"],
    }


def _run_agent(
    backend: str,
    goal_text: str,
    profile: LearnerProfile,
    graph_path: Path | None,
    target_concepts: list[str] | None,
) -> dict[str, Any]:
    if target_concepts:
        return _run_deterministic_components(
            backend=backend,
            goal_text=goal_text,
            profile=profile,
            graph_path=graph_path,
            target_concepts=target_concepts,
        )

    agent = PlanningAgent(graph_path=str(graph_path) if graph_path else None, kg_backend=backend)
    return agent.generate_plan(goal_text, profile)


def compare_planning_backends(
    goal_text: str,
    graph_path: Path | None = None,
    target_concepts: list[str] | None = None,
    known_topics: list[str] | None = None,
    days: int = 7,
    daily_minutes: int = 60,
) -> dict[str, Any]:
    profile = _make_profile(
        goal_text=goal_text,
        days=days,
        daily_minutes=daily_minutes,
        known_topics=known_topics,
    )
    result: dict[str, Any] = {
        "goal_text": goal_text,
        "graph_path": str(graph_path) if graph_path else None,
        "target_concepts": target_concepts or [],
        "known_topics": known_topics or [],
        "json": None,
        "neo4j": None,
        "passed": False,
        "error": None,
    }
    try:
        json_plan = _run_agent("json", goal_text, profile, graph_path, target_concepts)
        neo4j_plan = _run_agent("neo4j", goal_text, profile, graph_path, target_concepts)
        result["json"] = stable_planning_view(json_plan)
        result["neo4j"] = stable_planning_view(neo4j_plan)
        result["passed"] = result["json"] == result["neo4j"]
    except Exception as exc:
        result["error"] = str(exc)
        result["passed"] = False
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Planning Agent output between JSON and Neo4j KG backends.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge_graph.json for JSON backend")
    parser.add_argument("--goal", required=True, help="Natural language learning goal")
    parser.add_argument(
        "--target-concept",
        action="append",
        default=[],
        help="Stable target concept. Can be passed multiple times to avoid LLM goal parsing.",
    )
    parser.add_argument("--known-topic", action="append", default=[], help="Known topic to exclude from the plan")
    parser.add_argument("--days", type=int, default=7, help="Requested timeline in days")
    parser.add_argument("--daily-minutes", type=int, default=60, help="Available study minutes per day")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = compare_planning_backends(
        goal_text=args.goal,
        graph_path=Path(args.graph).resolve(),
        target_concepts=args.target_concept,
        known_topics=args.known_topic,
        days=args.days,
        daily_minutes=args.daily_minutes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
