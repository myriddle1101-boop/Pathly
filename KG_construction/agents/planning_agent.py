from __future__ import annotations

import uuid
from typing import Any

from agents.concept_expander import ConceptExpander
from agents.goal_parser import GoalParser
from agents.path_planner import PathPlanner
from agents.time_allocator import TimeAllocator
from agents.topic_mapper import TopicMapper
from infra.kg_repository_factory import create_kg_repository
from infra.profile_schema import LearnerProfile


class PlanningAgent:
    def __init__(self, graph_path: str | None = None, kg_backend: str | None = None):
        self.repository = create_kg_repository(graph_path=graph_path, backend=kg_backend)
        self.goal_parser = GoalParser()
        self.concept_expander = ConceptExpander(self.repository)
        self.topic_mapper = TopicMapper(self.repository)
        self.path_planner = PathPlanner(self.repository)
        self.time_allocator = TimeAllocator(self.repository)

    def _canonical_topic_id(self, topic: str) -> str | None:
        node = self.repository.get_topic(topic)
        if not node:
            return None
        return node["id"]

    def _existing_topics(self, topics: list[str]) -> list[str]:
        existing = []
        for topic in topics:
            canonical = self._canonical_topic_id(topic)
            if canonical:
                existing.append(canonical)
        return sorted(dict.fromkeys(existing))

    def _difficulty(self, topic: str) -> int:
        node = self.repository.get_topic(topic) or {"id": topic}
        value = node.get("difficulty_level", 3)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return 3

    def topic_mastery_score(self, profile: LearnerProfile, topic: str) -> float | None:
        canonical = self._canonical_topic_id(topic)
        if not canonical:
            return None
        for raw_topic, raw_score in profile.mastery_vector.items():
            raw_canonical = self._canonical_topic_id(raw_topic)
            if raw_canonical != canonical:
                continue
            try:
                return round(float(raw_score), 4)
            except (TypeError, ValueError):
                return None
        return None

    def topic_skill_score(self, profile: LearnerProfile, topic: str) -> float | None:
        canonical = self._canonical_topic_id(topic)
        if not canonical:
            return None
        for raw_topic, raw_score in profile.skill_tree.items():
            raw_canonical = self._canonical_topic_id(raw_topic)
            if raw_canonical != canonical:
                continue
            try:
                return round(float(raw_score), 4)
            except (TypeError, ValueError):
                return None
        return None

    def estimate_known_topics(self, profile: LearnerProfile) -> list[str]:
        return self._existing_topics(profile.known_topics)

    def estimate_completed_topics(self, profile: LearnerProfile) -> list[str]:
        return self._existing_topics(profile.completed_topics)

    def estimate_mastered_topics(self, profile: LearnerProfile, mastery_threshold: float = 0.8) -> list[str]:
        mastered = []
        for topic, score in profile.mastery_vector.items():
            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                continue
            if numeric_score >= mastery_threshold:
                canonical = self._canonical_topic_id(topic)
                if canonical:
                    mastered.append(canonical)
        return sorted(dict.fromkeys(mastered))

    def build_learner_state(self, profile: LearnerProfile, mastery_threshold: float = 0.8) -> dict[str, Any]:
        known_topics = self.estimate_known_topics(profile)
        completed_topics = self.estimate_completed_topics(profile)
        mastered_topics = self.estimate_mastered_topics(profile, mastery_threshold=mastery_threshold)
        excluded_topics = sorted(dict.fromkeys(known_topics + completed_topics + mastered_topics))

        mastery_scores = {}
        for topic in sorted(profile.mastery_vector.keys()):
            canonical = self._canonical_topic_id(topic)
            if not canonical:
                continue
            score = self.topic_mastery_score(profile, topic)
            if score is not None:
                mastery_scores[canonical] = score

        skill_tree_scores = {}
        for topic in sorted(profile.skill_tree.keys()):
            canonical = self._canonical_topic_id(topic)
            if not canonical:
                continue
            score = self.topic_skill_score(profile, topic)
            if score is not None:
                skill_tree_scores[canonical] = score

        return {
            "known_topics": known_topics,
            "completed_topics": completed_topics,
            "mastered_topics": mastered_topics,
            "excluded_topics": excluded_topics,
            "mastery_scores": mastery_scores,
            "skill_tree_scores": skill_tree_scores,
            "mastery_threshold": mastery_threshold,
        }

    def _priority_sort_key(self, profile: LearnerProfile, topic: str, original_index: dict[str, int]) -> tuple[float, int, int]:
        mastery_score = self.topic_mastery_score(profile, topic)
        skill_score = self.topic_skill_score(profile, topic)
        readiness_score = max(score for score in [mastery_score, skill_score, 0.0] if score is not None)
        difficulty_rank = -self._difficulty(topic)
        return (readiness_score, difficulty_rank, original_index[topic])

    def prioritize_topics_for_learner(
        self,
        ordered_topics: list[str],
        covered_prerequisites: dict[str, list[str]],
        profile: LearnerProfile,
    ) -> dict[str, Any]:
        topics = list(dict.fromkeys(ordered_topics))
        if not topics:
            return {"ordered_topics": [], "topic_priorities": []}

        original_index = {topic: index for index, topic in enumerate(topics)}
        prerequisites = {
            topic: [pre for pre in covered_prerequisites.get(topic, []) if pre in topics]
            for topic in topics
        }
        indegree = {topic: len(prerequisites[topic]) for topic in topics}
        dependents = {topic: [] for topic in topics}
        for topic, prereq_list in prerequisites.items():
            for prereq in prereq_list:
                dependents.setdefault(prereq, []).append(topic)

        available = [topic for topic in topics if indegree[topic] == 0]
        prioritized = []
        while available:
            available.sort(key=lambda topic: self._priority_sort_key(profile, topic, original_index))
            current = available.pop(0)
            prioritized.append(current)
            for dependent in dependents.get(current, []):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    available.append(dependent)

        if len(prioritized) != len(topics):
            prioritized = topics

        topic_priorities = []
        for new_index, topic in enumerate(prioritized):
            mastery_score = self.topic_mastery_score(profile, topic)
            skill_score = self.topic_skill_score(profile, topic)
            difficulty = self._difficulty(topic)
            readiness_score = max(score for score in [mastery_score, skill_score, 0.0] if score is not None)
            reasons = []
            if mastery_score is None:
                reasons.append("no mastery record")
            else:
                reasons.append(f"mastery {mastery_score:.2f}")
            if skill_score is None:
                reasons.append("no skill-tree score")
            else:
                reasons.append(f"skill-tree {skill_score:.2f}")
            reasons.append(f"difficulty {difficulty}")
            original_position = original_index[topic]
            if new_index < original_position:
                reasons.append("moved earlier within prerequisite-safe order")
            elif new_index > original_position:
                reasons.append("moved later because another ready topic has lower readiness")
            topic_priorities.append(
                {
                    "topic": topic,
                    "mastery_score": mastery_score,
                    "skill_tree_score": skill_score,
                    "readiness_score": round(readiness_score, 4),
                    "difficulty": difficulty,
                    "original_position": original_position,
                    "priority_position": new_index,
                    "priority_reason": "; ".join(reasons),
                }
            )

        return {"ordered_topics": prioritized, "topic_priorities": topic_priorities}

    def build_reasoning_trace(
        self,
        request,
        mapping: dict[str, Any],
        learner_state: dict[str, Any],
        path_result: dict[str, Any],
        priority_result: dict[str, Any],
        allocation: dict[str, Any],
    ) -> dict[str, Any]:
        matched_topics = [item["matched_name"] for item in mapping.get("matched_targets", [])]
        filtered_targets = [topic for topic in matched_topics if topic in learner_state["excluded_topics"]]
        summary_lines = [
            f"Parsed {len(request.target_concepts)} target concept(s) and mapped {len(mapping.get('matched_targets', []))} topic(s).",
            f"Filtered {len(learner_state['excluded_topics'])} topic(s) from direct study because they are already known, completed, or mastered.",
            f"Prioritized {len(priority_result.get('ordered_topics', []))} study topic(s) using prerequisite-safe readiness ranking.",
            f"Allocated {allocation.get('total_estimated_minutes', 0)} total minute(s) across {len(allocation.get('days', []))} day slot(s).",
        ]
        return {
            "presentation_summary": {
                "headline": "Learner-aware planning with prerequisite-safe prioritization",
                "decision_highlights": summary_lines,
            },
            "goal_parse": {
                "target_concepts": request.target_concepts,
                "requested_days": request.requested_days,
                "daily_minutes": request.daily_minutes,
                "constraints": request.constraints,
                "learning_style_hints": request.learning_style_hints,
            },
            "target_mapping": {
                "matched_targets": mapping.get("matched_targets", []),
                "unmatched_terms": mapping.get("unmatched_terms", []),
                "mapping_explanations": mapping.get("mapping_explanations", []),
            },
            "learner_filter": {
                "known_topics": learner_state["known_topics"],
                "completed_topics": learner_state["completed_topics"],
                "mastered_topics": learner_state["mastered_topics"],
                "excluded_topics": learner_state["excluded_topics"],
                "mastery_scores": learner_state["mastery_scores"],
                "skill_tree_scores": learner_state["skill_tree_scores"],
                "filtered_targets": filtered_targets,
                "mastery_threshold": learner_state["mastery_threshold"],
            },
            "path_planning": {
                "algorithm": path_result.get("algorithm"),
                "ordered_topics_before_priority": path_result.get("ordered_topics", []),
                "prerequisite_paths": path_result.get("prerequisite_paths", {}),
            },
            "topic_prioritization": {
                "ordered_topics_after_priority": priority_result.get("ordered_topics", []),
                "topic_priorities": priority_result.get("topic_priorities", []),
            },
            "time_allocation": {
                "total_estimated_minutes": allocation.get("total_estimated_minutes", 0),
                "overflow_topics": allocation.get("overflow_topics", []),
                "feasibility_warning": allocation.get("feasibility_warning"),
                "topic_adjustments": allocation.get("topic_adjustments", []),
            },
        }

    def generate_plan(
        self,
        goal_text: str,
        profile: LearnerProfile,
        confirmed_mappings: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request = self.goal_parser.parse(
            goal_text=goal_text,
            default_days=profile.target_days,
            default_daily_minutes=profile.daily_minutes,
        )
        if confirmed_mappings:
            mapping = self.topic_mapper.map_targets(
                request.target_concepts,
                confirmed_mappings=confirmed_mappings,
            )
        else:
            mapping = self.topic_mapper.map_targets(request.target_concepts)
        target_topics = [item["matched_name"] for item in mapping["matched_targets"]]
        learner_state = self.build_learner_state(profile)
        path_result = self.path_planner.plan(
            targets=target_topics,
            known_topics=learner_state["excluded_topics"],
            algorithm="astar",
        )
        priority_result = self.prioritize_topics_for_learner(
            ordered_topics=path_result["ordered_topics"],
            covered_prerequisites=path_result["covered_prerequisites"],
            profile=profile,
        )
        concept_result = self.concept_expander.expand(
            ordered_topics=priority_result["ordered_topics"],
            target_topics=target_topics,
            profile=profile,
            requested_days=request.requested_days,
            available_daily_minutes=request.daily_minutes,
        )
        allocation = self.time_allocator.allocate(
            ordered_topics=priority_result["ordered_topics"],
            profile=profile,
            requested_days=request.requested_days,
            daily_minutes=request.daily_minutes,
        )
        reasoning_trace = self.build_reasoning_trace(
            request=request,
            mapping=mapping,
            learner_state=learner_state,
            path_result=path_result,
            priority_result=priority_result,
            allocation=allocation,
        )

        reasoning_trace["concept_decomposition"] = {
            "concept_count": len(concept_result["concept_path"]),
            "unit_count": len(concept_result["concept_units"]),
            "workload_estimate": concept_result["workload_estimate"],
            "coverage_warnings": concept_result["coverage_warnings"],
        }

        return {
            "schema_version": 2,
            "plan_id": str(uuid.uuid4()),
            "goal": request.to_dict(),
            "profile_snapshot": profile.to_dict(),
            "learner_state": learner_state,
            "planning_method": {
                "goal_parser": "llm_or_rules",
                "topic_mapper": "exact_fuzzy_embedding",
                "learner_filter": "known_completed_mastery_threshold",
                "learner_prioritization": "prerequisite_safe_readiness_gap_then_difficulty",
                "path_algorithm": path_result["algorithm"],
                "time_allocator": "difficulty_pace_mastery_skill_tree_weighted",
            },
            "target_topics": target_topics,
            "mapping": mapping,
            "ordered_topics": priority_result["ordered_topics"],
            "prerequisite_paths": path_result["prerequisite_paths"],
            "covered_prerequisites": path_result["covered_prerequisites"],
            "topic_priorities": priority_result["topic_priorities"],
            "concept_path": concept_result["concept_path"],
            "concept_units": concept_result["concept_units"],
            "workload_estimate": concept_result["workload_estimate"],
            "coverage_warnings": concept_result["coverage_warnings"],
            "days": allocation["days"],
            "feasibility": {
                "requested_days": request.requested_days,
                "daily_minutes": request.daily_minutes,
                "total_estimated_minutes": allocation["total_estimated_minutes"],
                "warning": allocation["feasibility_warning"],
                "total_required_minutes": concept_result["workload_estimate"]["total_required_minutes"],
                "recommended_daily_minutes": concept_result["workload_estimate"]["recommended_daily_minutes"],
                "minimum_recommended_days": concept_result["workload_estimate"]["minimum_recommended_days"],
                "available_capacity_minutes": concept_result["workload_estimate"]["available_capacity_minutes"],
                "capacity_gap_minutes": concept_result["workload_estimate"]["capacity_gap_minutes"],
                "capacity_status": concept_result["workload_estimate"]["capacity_status"],
                "estimate_is_final": concept_result["workload_estimate"]["is_final"],
            },
            "uncovered_constraints": mapping["unmatched_terms"],
            "overflow_topics": allocation["overflow_topics"],
            "reasoning_trace": reasoning_trace,
        }
