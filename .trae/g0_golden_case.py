"""Provision and verify Pathly's source-grounded G0 demonstration path."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pathly_backend import PathlyBackend
from source_grounded_v4_generator import S4_GENERATOR_VERSION, generate_source_grounded_lecture_v4
from source_grounded_v4_store import SourceGroundedLectureV4Store
from verified_golden_sources import GOLDEN_PATH, GOLDEN_PATH_VERSION, VerifiedGoldenSourceRegistry


G0_VERSION = "g0-neural-foundations-v1"
G0_GOAL = "Understand the foundations of neural networks, from linear separability to gradient descent"
G0_MINUTES_PER_DAY = 45
G0_RESOURCE_ID = "01e27d8d07707beb3f8eb4ba3bfe4018f3dd4a2d14e2976aaba0ddf32c867207"


def g0_structured_model_generator(request: dict[str, Any]) -> dict[str, Any]:
    """Generate one G0 lecture from public source pages without transmitting learner profile data."""
    from openai import OpenAI

    def object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}

    schema = object_schema({
        "concept_introduction": object_schema({
            "hook": {"type": "string"}, "explanation": {"type": "string"},
            "mechanism": {"type": "array", "items": {"type": "string"}}, "boundaries": {"type": "string"},
        }, ["hook", "explanation", "mechanism", "boundaries"]),
        "prerequisite_recap": object_schema({
            "title": {"type": "string"}, "explanation": {"type": "string"}, "example": {"type": "string"},
        }, ["title", "explanation", "example"]),
        "page_walkthrough": {"type": "array", "items": object_schema({
            "page_number": {"type": "integer"}, "what_to_notice": {"type": "string"},
            "explanation": {"type": "string"}, "connection_to_previous": {"type": "string"},
        }, ["page_number", "what_to_notice", "explanation", "connection_to_previous"])},
        "key_terms": {"type": "array", "items": object_schema({
            "term": {"type": "string"}, "definition": {"type": "string"},
        }, ["term", "definition"])},
        "worked_example": object_schema({
            "problem": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}},
            "solution": {"type": "string"}, "why_it_works": {"type": "string"},
        }, ["problem", "steps", "solution", "why_it_works"]),
        "objective_exercise": object_schema({
            "instructions": {"type": "string"},
            "questions": {"type": "array", "items": object_schema({
                "question_id": {"type": "string"}, "type": {"type": "string", "enum": ["single_choice"]},
                "prompt": {"type": "string"},
                "options": {"type": "array", "items": object_schema({
                    "id": {"type": "string"}, "text": {"type": "string"}, "correct": {"type": "boolean"},
                }, ["id", "text", "correct"])},
                "explanation": {"type": "string"},
            }, ["question_id", "type", "prompt", "options", "explanation"])},
        }, ["instructions", "questions"]),
        "summary_connection": object_schema({
            "summary": {"type": "string"}, "next_concept_bridge": {"type": "string"},
        }, ["summary", "next_concept_bridge"]),
    }, ["concept_introduction", "prerequisite_recap", "page_walkthrough", "key_terms", "worked_example", "objective_exercise", "summary_connection"])

    source_pages = request.get("sources") or []
    concept_info = request.get("concept") or {}
    concept = str(concept_info.get("name") or concept_info.get("id") or "the concept")
    instructions = (
        f"Write a complete 45-minute lecture section about {concept}. Teach only the subject matter. "
        "Use 750-950 substantive words. Explain the mechanism and limits, not merely a definition. "
        "The worked example must have at least four solved steps and a solution longer than 90 words. "
        "Create four single-choice questions with at least three options and exactly one correct option each. "
        "Include one page_walkthrough item for every supplied page, preserving its exact page_number. "
        "Ground factual claims in the supplied page evidence. Do not mention Pathly, content agents, teaching methods, "
        "learning methods, lesson plans, learners, fallback sources, generation, prompts, or study strategy. "
        "Normalize OCR artifacts. Never copy mojibake or broken glyphs from the source. Write mathematical symbols "
        "in readable plain text such as theta, alpha, dL/dtheta, and x1 rather than corrupted characters."
    )
    payload = {"concept_name": concept, "source_pages": source_pages}
    response = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")).responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        instructions=instructions,
        input=json.dumps(payload, ensure_ascii=False),
        text={"format": {"type": "json_schema", "name": "g0_source_grounded_lecture", "strict": True, "schema": schema}},
        max_output_tokens=8000,
        timeout=120,
    )
    return json.loads(response.output_text)
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def _identity(user_id: str) -> tuple[str, str]:
    suffix = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
    path_id = f"g0-neural-foundations-{suffix}"
    return path_id, f"{path_id}-v1"


def build_g0_plan(user_id: str) -> dict[str, Any]:
    """Build the immutable five-day schedule used for G0 acceptance."""
    path_id, plan_id = _identity(user_id)
    prerequisites = {
        "Linear Separability": [],
        "XOR": ["Linear Separability"],
        "Neural Networks": ["XOR"],
        "Activation Functions": ["Neural Networks"],
        "Gradient Descent": ["Activation Functions"],
    }
    concept_path = []
    activities = []
    days = []
    for position, concept in enumerate(GOLDEN_PATH, 1):
        concept_id = concept
        activity_id = f"g0-day-{position}-{_slug(concept)}"
        activity = {
            "activity_id": activity_id,
            "activity_type": "explanation",
            "concept_ids": [concept_id],
            "title": f"Source-grounded lecture: {concept}",
            "estimated_minutes": G0_MINUTES_PER_DAY,
            "sequence": position,
            "source": "verified_public_resource",
        }
        concept_path.append({
            "concept_id": concept_id,
            "title": concept,
            "display_name": concept,
            "order": position,
            "is_target": True,
            "path_role": "learning_target",
            "prerequisite_ids": prerequisites[concept],
            "relationship_source": [
                {"type": "prerequisite", "from": prerequisite, "to": concept}
                for prerequisite in prerequisites[concept]
            ],
            "difficulty": 3,
            "estimated_total_minutes": G0_MINUTES_PER_DAY,
            "mastery_before": 0.0,
            "planning_reason": (
                f"Golden-path position {position}: {concept} follows the verified prerequisite chain "
                "and has page-level public source coverage."
            ),
            "source_mode": "verified_golden_resource",
        })
        activities.append(activity)
        days.append({
            "day": position,
            "focus_topics": [concept],
            "activities": [activity],
            "total_minutes": G0_MINUTES_PER_DAY,
            "reason": f"One focused, source-grounded lecture for {concept}.",
        })
    total = G0_MINUTES_PER_DAY * len(days)
    return {
        "schema_version": G0_VERSION,
        "plan_id": plan_id,
        "path_id": path_id,
        "goal": G0_GOAL,
        "target_topics": list(GOLDEN_PATH),
        "ordered_topics": list(GOLDEN_PATH),
        "concept_path": concept_path,
        "activities": activities,
        "workload_estimate": {"total_minutes": total, "method": "fixed_g0_verified_path"},
        "feasibility": {"requested_days": 5, "daily_minutes": G0_MINUTES_PER_DAY, "status": "feasible"},
        "days": days,
        "schedule_status": "scheduled",
        "reasoning_trace": [
            "Uses the verified Linear Separability to Gradient Descent prerequisite chain.",
            "Every day has an immutable page-level public source before lecture generation.",
        ],
        "coverage_warnings": [],
        "unscheduled_activities": [],
        "schedule": {"total_days": 5, "total_minutes": total, "daily_capacity_minutes": G0_MINUTES_PER_DAY},
        "golden_case": {"name": "G0", "version": G0_VERSION, "source_registry": GOLDEN_PATH_VERSION},
    }


class G0GoldenCaseService:
    def __init__(
        self,
        *,
        backend: PathlyBackend,
        daily_learning_service: Any,
        v4_store: SourceGroundedLectureV4Store,
        verified_registry: VerifiedGoldenSourceRegistry,
        kg_dir: str | Path,
    ):
        self.backend = backend
        self.daily_learning_service = daily_learning_service
        self.v4_store = v4_store
        self.verified_registry = verified_registry
        self.kg_dir = Path(kg_dir)

    @property
    def stage1_path(self) -> Path:
        return self.kg_dir / "web_data" / "runs" / "06_mlp" / "01e27d8d0770" / "stage1_chunks.json"

    def public_rag_status(self) -> dict[str, Any]:
        from infra.rag_repository import RAGRepository

        repository = RAGRepository(collection_name="kg_chunks", force_device="cpu")
        result = repository.collection.get(where={"resource_id": G0_RESOURCE_ID}, include=["metadatas"])
        ids = list(result.get("ids") or [])
        return {
            "resource_id": G0_RESOURCE_ID,
            "document": "06_mlp.pdf",
            "indexed_chunks": len(ids),
            "expected_chunks": 34,
            "ready": len(ids) == 34,
        }

    def ingest_public_rag(self) -> dict[str, Any]:
        from infra.rag_ingestion import ingest_stage1_chunks_with_report

        if not self.stage1_path.exists():
            raise FileNotFoundError(str(self.stage1_path))
        before = self.public_rag_status()
        report = ingest_stage1_chunks_with_report(self.stage1_path, collection_name="kg_chunks", force_device="cpu")
        after = self.public_rag_status()
        if not after["ready"]:
            raise RuntimeError(f"06_mlp.pdf public RAG ingestion incomplete: {after['indexed_chunks']}/34")
        return {"before": before, "ingestion": report, "after": after}

    def ensure_plan(self, user_id: str, *, activate: bool = True) -> dict[str, Any]:
        plan = build_g0_plan(user_id)
        existing = self.backend.plans.get_plan(plan["plan_id"])
        if existing is None:
            profile_snapshot = self.backend.get_profile_record(user_id) or {}
            existing = self.backend.plans.save_plan(
                user_id,
                plan,
                "verified_golden_case",
                ["public_chroma:06_mlp.pdf", "verified_page_registry"],
                path_id=plan["path_id"],
                goal_text=G0_GOAL,
                profile_snapshot=profile_snapshot,
            )
        elif existing.get("user_id") != user_id or (existing.get("plan") or {}).get("schema_version") != G0_VERSION:
            raise RuntimeError("G0 deterministic plan identity is occupied by incompatible data")
        if activate:
            self.daily_learning_service.activate(
                user_id=user_id,
                plan_id=plan["plan_id"],
                start_date=date.today().isoformat(),
                timezone_name="Asia/Shanghai",
            )
        return existing

    def _source_link(self, concept: str) -> dict[str, Any]:
        link = self.verified_registry.resolve(concept_id=concept, concept_name=concept)
        if not link:
            raise RuntimeError(f"Verified source unavailable for {concept}")
        return {
            **link,
            "concept_id": concept,
            "concept_name": concept,
            "source_version": G0_VERSION,
            "link_role": "primary",
        }

    def _v3_seed(self, plan: dict[str, Any], day: int, concept: str) -> dict[str, Any]:
        section_id = f"g0-section-{day}-{_slug(concept)}"
        return {
            "contract_version": "full-lecture-v3",
            "path_id": plan["path_id"],
            "plan_id": plan["plan_id"],
            "day": day,
            "lecture_overview": {
                "title": f"{concept}: a source-grounded lecture",
                "learning_objectives": [f"Explain and apply {concept} using the selected source pages."],
                "total_minutes": G0_MINUTES_PER_DAY,
            },
            "lecture_sections": [{
                "section_id": section_id,
                "concept_id": concept,
                "concept_name": concept,
                "title": concept,
                "estimated_minutes": G0_MINUTES_PER_DAY,
            }],
            "generation_metadata": {"generator_version": "g0-v3-structural-seed", "generation_mode": "structural_seed"},
        }

    def generate_lectures(self, user_id: str, *, force: bool = False, model_generator: Any | None = None) -> list[dict[str, Any]]:
        record = self.ensure_plan(user_id, activate=True)
        plan = record["plan"]
        profile = self.backend.get_profile_record(user_id) or {}
        generated: list[dict[str, Any]] = []
        for day, concept in enumerate(GOLDEN_PATH, 1):
            if not force:
                existing = self.v4_store.get(user_id, plan["plan_id"], day)
                metadata = (existing or {}).get("generation_metadata") or {}
                if existing and metadata.get("g0_version") == G0_VERSION:
                    generated.append(existing)
                    continue
            # G0 is a public, fixed demonstration. Reuse an approved public lecture
            # for a new anonymous session instead of issuing five new model calls.
            shared = self.v4_store.find_by_generation_metadata("g0_version", G0_VERSION, day)
            if shared and not force:
                lecture = copy.deepcopy(shared)
                lecture["path_id"] = plan["path_id"]
                lecture["plan_id"] = plan["plan_id"]
                lecture["day"] = day
                metadata = dict(lecture.get("generation_metadata") or {})
                metadata.update({"g0_version": G0_VERSION, "pre_generated_at": _now(), "session_template_reused": True})
                lecture["generation_metadata"] = metadata
                self.v4_store.save(user_id, plan["plan_id"], day, lecture)
                generated.append(lecture)
                continue
            link = self._source_link(concept)
            daily = {
                "user_id": user_id,
                "path_id": plan["path_id"],
                "plan_id": plan["plan_id"],
                "day": day,
                "concepts": [next(item for item in plan["concept_path"] if item["concept_id"] == concept)],
                "prepared_evidence": [],
                "citations": [],
                "resources": [],
            }
            lecture = generate_source_grounded_lecture_v4(
                v3_lecture=self._v3_seed(plan, day, concept),
                source_links=[link],
                daily=daily,
                user_id=user_id,
                profile=profile,
                verified_registry=self.verified_registry,
                model_generator=model_generator or g0_structured_model_generator,
            )
            metadata = dict(lecture.get("generation_metadata") or {})
            metadata.update({"g0_version": G0_VERSION, "pre_generated_at": _now()})
            lecture["generation_metadata"] = metadata
            lecture["golden_path_sources"] = self.verified_registry.audit()
            self.v4_store.save(user_id, plan["plan_id"], day, lecture)
            generated.append(lecture)
        return generated

    @staticmethod
    def quality_report(lectures: list[dict[str, Any]]) -> dict[str, Any]:
        banned = ("pathly", "teaching method", "learning method", "fallback source")
        rows = []
        for expected_day, (concept, lecture) in enumerate(zip(GOLDEN_PATH, lectures), 1):
            sections = lecture.get("lecture_sections") or []
            section = sections[0] if len(sections) == 1 else {}
            content = section.get("lecture_content") or {}
            serialized = json.dumps(content, ensure_ascii=False).lower()
            links = section.get("source_links") or []
            pages = section.get("source_pages") or []
            exercise = content.get("objective_exercise") or {}
            questions = exercise.get("questions") or []
            corrupt_markers = ("\u00a1\u00aa", "\u00a6", "\ufffd", "\u25a1")
            checks = {
                "ready": section.get("v4_status") == "ready",
                "concept_matches": str(section.get("concept_name") or "").lower() == concept.lower(),
                "verified_source": bool(links and links[0].get("review_status") == "verified"),
                "page_sequence_present": len(pages) >= 2,
                "worked_example_complete": len((content.get("worked_example") or {}).get("steps") or []) >= 3,
                "objective_questions_complete": len(questions) >= 3,
                "no_meta_language": not any(term in serialized for term in banned),
                "readable_symbols": not any(term in serialized for term in corrupt_markers),
            }
            rows.append({"day": expected_day, "concept": concept, "checks": checks, "passed": all(checks.values())})
        return {
            "g0_version": G0_VERSION,
            "generated_at": _now(),
            "passed": len(rows) == 5 and all(item["passed"] for item in rows),
            "days": rows,
        }

    def provision(
        self,
        user_id: str,
        *,
        force_rag: bool = False,
        force_lectures: bool = False,
        model_generator: Any | None = None,
    ) -> dict[str, Any]:
        rag_before = self.public_rag_status()
        rag_result = (
            self.ingest_public_rag()
            if force_rag or not rag_before["ready"]
            else {"before": rag_before, "ingestion": {"inserted": 0, "mode": "already_indexed"}, "after": rag_before}
        )
        plan = self.ensure_plan(user_id, activate=True)
        lectures = self.generate_lectures(user_id, force=force_lectures, model_generator=model_generator)
        quality = self.quality_report(lectures)
        return {
            "g0_version": G0_VERSION,
            "public_rag": rag_result,
            "plan": {
                "plan_id": plan["plan_id"],
                "path_id": plan["path_id"],
                "goal_text": plan["goal_text"],
                "days": len((plan.get("plan") or {}).get("days") or []),
            },
            "lectures_pre_generated": len(lectures),
            "quality": quality,
        }
    def status(self, user_id: str) -> dict[str, Any]:
        plan = build_g0_plan(user_id)
        record = self.backend.plans.get_plan(plan["plan_id"])
        lectures = [self.v4_store.get(user_id, plan["plan_id"], day) for day in range(1, 6)]
        available = [item for item in lectures if item]
        return {
            "g0_version": G0_VERSION,
            "path": list(GOLDEN_PATH),
            "plan_id": plan["plan_id"],
            "path_id": plan["path_id"],
            "plan_created": bool(record),
            "public_rag": self.public_rag_status(),
            "lectures_pre_generated": len(available),
            "quality": self.quality_report(available) if len(available) == 5 else None,
        }

