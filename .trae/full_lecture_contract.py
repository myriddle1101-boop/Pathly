"""Full Lecture View v3 contract and compatibility helpers.

This module is deliberately independent from the existing annotated-session-v1
store.  It defines the richer, learner-facing lecture payload that later steps
will generate and render.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


FULL_LECTURE_CONTRACT_VERSION = "full-lecture-v3"
FULL_LECTURE_GENERATOR_VERSION = "full-lecture-related-pages-v5"


class FullLectureValidationError(ValueError):
    pass


REQUIRED_TOP_LEVEL = {
    "contract_version", "content_id", "path_id", "plan_id", "day",
    "scheduled_minutes", "lecture_overview", "source_materials",
    "lecture_sections", "practice_set", "knowledge_check", "citations",
    "generation_metadata",
}


def _require(mapping: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(key for key in keys if key not in mapping)
    if missing:
        raise FullLectureValidationError(f"{label} missing: {', '.join(missing)}")


def validate_full_lecture(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the stable v3 shape and return the original payload.

    Validation is intentionally structural, not semantic: later generators can
    use live or fallback content while the UI always receives the same shape.
    """
    if not isinstance(payload, dict):
        raise FullLectureValidationError("payload must be an object")
    _require(payload, REQUIRED_TOP_LEVEL, "lecture")
    if payload["contract_version"] != FULL_LECTURE_CONTRACT_VERSION:
        raise FullLectureValidationError("unsupported full lecture contract")
    for field in ("day", "scheduled_minutes"):
        if not isinstance(payload[field], int) or payload[field] < 1:
            raise FullLectureValidationError(f"{field} must be a positive integer")
    if not isinstance(payload["lecture_overview"], dict):
        raise FullLectureValidationError("lecture_overview must be an object")
    _require(payload["lecture_overview"], {"title", "why_this_matters", "objectives"}, "lecture_overview")
    if not isinstance(payload["lecture_overview"]["objectives"], list):
        raise FullLectureValidationError("lecture_overview.objectives must be an array")
    if not isinstance(payload["source_materials"], list):
        raise FullLectureValidationError("source_materials must be an array")
    if not isinstance(payload["lecture_sections"], list) or not payload["lecture_sections"]:
        raise FullLectureValidationError("lecture_sections must be a non-empty array")
    section_minutes = 0
    for index, section in enumerate(payload["lecture_sections"]):
        if not isinstance(section, dict):
            raise FullLectureValidationError(f"lecture_sections[{index}] must be an object")
        _require(section, {"section_id", "title", "estimated_minutes", "teaching", "source_refs"}, f"section[{index}]")
        if not isinstance(section["estimated_minutes"], int) or section["estimated_minutes"] < 1:
            raise FullLectureValidationError(f"section[{index}].estimated_minutes must be positive")
        if not isinstance(section["teaching"], dict):
            raise FullLectureValidationError(f"section[{index}].teaching must be an object")
        _require(section["teaching"], {"explanation", "worked_example", "misconceptions", "takeaway"}, f"section[{index}].teaching")
        if not isinstance(section["source_refs"], list):
            raise FullLectureValidationError(f"section[{index}].source_refs must be an array")
        page_sequence = section.get("page_sequence")
        if page_sequence is not None:
            if not isinstance(page_sequence, list):
                raise FullLectureValidationError(f"section[{index}].page_sequence must be an array")
            previous_page = 0
            for page_index, page in enumerate(page_sequence):
                if not isinstance(page, dict) or not isinstance(page.get("page_start"), int) or page["page_start"] < 1:
                    raise FullLectureValidationError(f"section[{index}].page_sequence[{page_index}] requires a positive page_start")
                if page["page_start"] < previous_page:
                    raise FullLectureValidationError(f"section[{index}].page_sequence must be ordered")
                previous_page = page["page_start"]
        page_led = section.get("page_led_lesson")
        if page_led is not None:
            if not isinstance(page_led, dict):
                raise FullLectureValidationError(f"section[{index}].page_led_lesson must be an object")
            _require(page_led, {"page_role", "prerequisite_recap", "guided_reading", "key_terms", "worked_example", "knowledge_check", "time_plan"}, f"section[{index}].page_led_lesson")
            if sum(int(item.get("minutes", 0)) for item in page_led["time_plan"]) != section["estimated_minutes"]:
                raise FullLectureValidationError(f"section[{index}].page_led_lesson time plan must equal section minutes")
        section_minutes += section["estimated_minutes"]
    if section_minutes > payload["scheduled_minutes"]:
        raise FullLectureValidationError("lecture sections exceed scheduled minutes")
    for field in ("practice_set", "knowledge_check", "citations", "generation_metadata"):
        if not isinstance(payload[field], (dict, list)):
            raise FullLectureValidationError(f"{field} must be an object or array")
    return payload


def from_annotated_session(session: dict[str, Any]) -> dict[str, Any]:
    """Create a valid v3 shell from annotated-session-v1 without losing source refs.

    This is a compatibility bridge only; it intentionally labels the payload as
    fallback until the real lecture generator is implemented in a later step.
    """
    overview = session.get("session_overview") or {}
    readings = session.get("reading_sequence") or []
    bridges = session.get("concept_bridges") or []
    sections: list[dict[str, Any]] = []
    remaining = int(session.get("scheduled_minutes") or 1)
    source_refs = [item.get("citation_id") or item.get("reading_id") for item in readings]
    source_refs = [ref for ref in source_refs if ref]
    for index, bridge in enumerate(bridges or readings[:1]):
        minutes = max(1, min(remaining, int(bridge.get("estimated_minutes") or 15)))
        title = bridge.get("title") or bridge.get("concept") or f"Concept {index + 1}"
        explanation = bridge.get("explanation") or bridge.get("plain_explanation") or "Review the source material and connect it to today's goal."
        sections.append({
            "section_id": f"lecture-section-{index + 1}",
            "title": title,
            "estimated_minutes": minutes,
            "concept_ids": bridge.get("concept_ids") or [],
            "teaching": {
                "explanation": explanation,
                "worked_example": bridge.get("example") or "Apply the idea to one concrete case from the source.",
                "misconceptions": bridge.get("misconceptions") or [],
                "takeaway": bridge.get("takeaway") or "State the concept and its use in your own words.",
            },
            "source_refs": source_refs,
        })
        remaining -= minutes
        if remaining <= 0:
            break
    if not sections:
        sections = [{
            "section_id": "lecture-section-1", "title": overview.get("title") or "Today's concept",
            "estimated_minutes": int(session.get("scheduled_minutes") or 1), "concept_ids": [],
            "teaching": {
                "explanation": "Read the source material and identify the central idea.",
                "worked_example": "Connect the idea to one example in the material.",
                "misconceptions": [], "takeaway": "Summarize the concept in your own words.",
            }, "source_refs": source_refs,
        }]
    payload = {
        "contract_version": FULL_LECTURE_CONTRACT_VERSION,
        "generator_version": FULL_LECTURE_GENERATOR_VERSION,
        "content_id": session.get("content_id") or session.get("annotated_session_id") or "compatibility-shell",
        "path_id": session.get("path_id"), "plan_id": session.get("plan_id"),
        "plan_version": session.get("plan_version"), "day": int(session.get("day") or 1),
        "scheduled_minutes": int(session.get("scheduled_minutes") or 1),
        "lecture_overview": {
            "title": overview.get("title") or f"Day {session.get('day', 1)} Lecture",
            "why_this_matters": overview.get("goal_for_today") or overview.get("opening_hook") or "Build understanding from the selected source material.",
            "objectives": overview.get("learning_objectives") or [],
            "prerequisite_recap": overview.get("prerequisite_recap") or [],
        },
        "source_materials": deepcopy(readings), "lecture_sections": sections,
        "practice_set": {"items": []}, "knowledge_check": {"items": []},
        "citations": deepcopy(session.get("citations") or []),
        "generation_metadata": {
            "generation_mode": "fallback", "cache_status": "compatibility_shell",
            "source_hash": session.get("source_hash"),
            "upstream_contract": session.get("contract_version"),
            "fallback_reason": "full lecture generator not yet enabled",
        },
    }
    return validate_full_lecture(payload)






