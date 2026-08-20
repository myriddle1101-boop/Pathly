"""Deterministic Full Lecture View v3 generator.

Step 2 intentionally has no model dependency. It turns an existing annotated
session into a complete learner-facing lecture while preserving its sources.
"""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
import re
from typing import Any

from full_lecture_contract import (
    FULL_LECTURE_GENERATOR_VERSION,
    from_annotated_session,
    validate_full_lecture,
)


_NOISE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:doi|arxiv):\S+", re.I)


def prepare_evidence(text: str, *, max_chars: int = 900) -> dict[str, Any]:
    """Bound and clean a retrieved excerpt before it reaches the lecture."""
    value = " ".join(str(text or "").split())
    value = _NOISE.sub("", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" -;,")
    flags: list[str] = []
    if len(value) > max_chars:
        value = value[:max_chars].rsplit(" ", 1)[0] + "..."
        flags.append("bounded_excerpt")
    if not value:
        flags.append("empty_after_cleaning")
    return {"clean_text": value, "quality_flags": flags, "safe_for_direct_excerpt": bool(value)}


def _label(reading: dict[str, Any]) -> str:
    links = reading.get("linked_concept_ids") or []
    return str(reading.get("section_title") or (links[0] if links else "today's concept"))


def _sentences(text: str, limit: int = 3) -> list[str]:
    values = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", " ".join(str(text or "").split())) if piece.strip()]
    return values[:limit] or ["Use the selected page to identify the concept, its mechanism, and one concrete implication."]


def _normalise_page_sequence(reading: dict[str, Any]) -> list[dict[str, Any]]:
    raw = reading.get("page_sequence") or []
    pages: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in raw:
        if not isinstance(item, dict) or not item.get("page_start"):
            continue
        page = int(item["page_start"])
        if page in seen:
            continue
        seen.add(page)
        pages.append({"page_start": page, "page_end": int(item.get("page_end") or page), "section_title": item.get("section_title") or reading.get("source_section_title") or reading.get("section_title"), "clean_excerpt": prepare_evidence(item.get("clean_excerpt") or "", max_chars=1200)["clean_text"], "role": item.get("role") or ("anchor" if page == int(reading.get("page_start") or page) else "supporting"), "alignment_score": item.get("alignment_score")})
    if not pages and reading.get("page_start"):
        start = int(reading["page_start"])
        end = min(int(reading.get("page_end") or start), start + 5)
        for page in range(start, end + 1):
            pages.append({"page_start": page, "page_end": page, "section_title": reading.get("source_section_title") or reading.get("section_title"), "clean_excerpt": prepare_evidence(reading.get("clean_excerpt") or "", max_chars=1200)["clean_text"] if page == start else "", "role": "anchor" if page == start else "context_after", "alignment_score": None})
    return sorted(pages, key=lambda item: int(item["page_start"]))[:6]


def _page_sequence_guide(page_sequence: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    guide = []
    for index, page in enumerate(page_sequence):
        excerpt = page.get("clean_excerpt") or ""
        role = page.get("role") or "supporting"
        purpose = (f"Use this anchor page to establish the central mechanism of {label}." if role == "anchor" else (f"Use this preceding page to recover the setup and definitions needed for {label}." if role == "context_before" else f"Use this following page to extend {label} with evidence, an example, or a consequence."))
        guide.append({"page_start": int(page["page_start"]), "page_end": int(page.get("page_end") or page["page_start"]), "role": role, "title": page.get("section_title") or f"Page {page['page_start']}", "purpose": purpose, "key_claims": _sentences(excerpt, 2) if excerpt else [], "transition": (f"Next, page {page_sequence[index + 1]['page_start']} continues the same explanation." if index + 1 < len(page_sequence) else f"This completes the selected page sequence for {label}.")})
    return guide

def _time_plan(minutes: int) -> list[dict[str, Any]]:
    if minutes < 5:
        return [{"phase": "Focused study", "minutes": minutes}]
    names = [("Recall", .12), ("Explain", .24), ("Read and observe", .25), ("Worked example", .24), ("Knowledge check", .15)]
    values = [max(1, round(minutes * weight)) for _, weight in names]
    delta = minutes - sum(values)
    values[2] += delta
    if values[2] < 1:
        for index in range(len(values)):
            if values[index] > 1 and values[2] < 1:
                values[index] -= 1
                values[2] += 1
    return [{"phase": name, "minutes": value} for (name, _), value in zip(names, values)]


def _page_led_lesson(*, label: str, minutes: int, evidence_text: str, teaching: dict[str, Any], annotation: dict[str, Any], source_title: str | None, page_start: Any) -> dict[str, Any]:
    lines = _sentences(evidence_text)
    core = lines[0]
    source_name = source_title or "the selected source page"
    page_label = f"page {page_start}" if page_start else "the selected source excerpt"
    terms = [term for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", label) if term.lower() not in {"the", "and", "for", "from", "with"}]
    if not terms:
        terms = [label]
    return {
        "page_role": f"{source_name}, {page_label}, is used to establish one concrete idea about {label}.",
        "prerequisite_recap": {
            "title": f"Before this page: what to recall about {label}",
            "content": teaching.get("prerequisite_bridge") or f"Recall the earlier concept that gives {label} its inputs, vocabulary, or purpose. You will use that connection to interpret this page rather than memorizing it in isolation.",
        },
        "guided_reading": {
            "opening_question": f"Before reading, ask: what claim does this page make about {label}?",
            "observation_steps": [
                f"Locate the title, diagram, or first sentence that names the mechanism related to {label}.",
                f"Identify what goes in, what changes, and what result the page shows.",
                "Compare the page evidence with the explanation below; keep only the claim the page actually supports.",
            ],
            "walkthrough": [
                {"source_text": line, "teaching_note": f"This line is evidence to interpret: connect it specifically to {label}, then state what it tells you about the mechanism or use case."}
                for line in lines
            ],
        },
        "key_terms": [
            {"term": term, "meaning": teaching.get("concept_intro") if index == 0 else f"A page-level term to connect to {label}; define it from the source context rather than treating it as a label."}
            for index, term in enumerate(terms[:3])
        ],
        "worked_example": {
            "scenario": f"Use the source claim to reason about a concrete case of {label}.",
            "steps": [
                f"Start with the page claim: {core}",
                f"Name the input, transformation, and outcome that the claim describes for {label}.",
                f"Explain one situation where this mechanism would be useful, and one condition that would make the explanation incomplete.",
            ],
            "solution": teaching.get("worked_interpretation") or f"A correct explanation of {label} connects the source evidence to a mechanism and a concrete consequence, not merely the concept name.",
        },
        "knowledge_check": {
            "prompt": f"Without looking back, what does this page show about {label}, and what evidence from the page supports your answer?",
            "expected_elements": [f"A precise statement about {label}", "One page detail (text, diagram, or relationship)", "A consequence, use case, or limitation"],
        },
        "transition": annotation.get("why_it_matters") or f"You can now use {label} as a building block for the next concept rather than treating this page as an isolated reading.",
        "time_plan": _time_plan(minutes),
    }


_META_PHRASES = ("identify what goes in", "locate the title", "this line is evidence", "a correct explanation", "complete the scheduled", "you should be able to", "treat the name", "learning method", "teaching method", "pathly", "learning concept in your path", "fallback source", "no suitable source page", "start by asking")
_LECTURE_CACHE: dict[str, dict[str, Any]] = {}


def _teaching_word_count(value: Any) -> int:
    return len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", json.dumps(value, ensure_ascii=False)))


def _validate_live_lesson(label: str, lesson: dict[str, Any], minutes: int, *, source_available: bool = True) -> None:
    required = {"page_role", "concept_explanation", "prerequisite_recap", "guided_reading", "key_terms", "worked_example", "knowledge_check", "transition"}
    if not required.issubset(lesson): raise ValueError("missing teaching fields")
    text = json.dumps(lesson, ensure_ascii=False).lower()
    if any(phrase in text for phrase in _META_PHRASES): raise ValueError("teacher-facing meta language")
    if _teaching_word_count(lesson) < max(260, min(850, int(minutes) * 12)): raise ValueError("lecture too thin")
    terms = re.findall(r"[A-Za-z]{4,}", label)
    if label.lower() not in text and not any(term.lower() in text for term in terms): raise ValueError("concept not taught")
    if source_available and len((lesson.get("guided_reading") or {}).get("walkthrough") or []) < 2: raise ValueError("source walkthrough too thin")
    if len((lesson.get("worked_example") or {}).get("steps") or []) < 3: raise ValueError("worked example too thin")


def _live_page_led_lesson(*, label: str, minutes: int, evidence_text: str, teaching: dict[str, Any], annotation: dict[str, Any], source_title: str | None, page_start: Any, source_available: bool = True) -> dict[str, Any]:
    fallback = _page_led_lesson(label=label, minutes=minutes, evidence_text=evidence_text, teaching=teaching, annotation=annotation, source_title=source_title, page_start=page_start)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: return {**fallback, "_generation_mode":"fallback", "_quality_status":"source_coverage_insufficient", "_fallback_reason":"missing_api_key"}
    cache_key=json.dumps({"v":FULL_LECTURE_GENERATOR_VERSION,"label":label,"minutes":minutes,"evidence":evidence_text,"teaching":teaching,"source":source_title,"page":page_start},ensure_ascii=False,sort_keys=True,default=str)
    if cache_key in _LECTURE_CACHE: return _LECTURE_CACHE[cache_key]
    from openai import OpenAI
    target_words=max(420,min(1000,minutes*16))
    request={"audience":"The student. Teach the subject now, in finished prose.","concept":label,"scheduled_minutes":minutes,"source":{"title":source_title,"page":page_start,"clean_excerpt":evidence_text},"upstream_knowledge":teaching,"target_words":target_words,"required_json":{"page_role":"specific source-supported domain claim, or empty when no source is available","concept_explanation":{"overview":"several substantive paragraphs that directly explain the concept","mechanism":"step-by-step account of how the concept works","assumptions_and_boundaries":"when it applies, when it fails, and why","concrete_example":"a domain example explained in prose"},"prerequisite_recap":{"title":"knowledge-specific title","content":"actual prerequisite explanation and concrete example"},"guided_reading":{"opening_question":"domain question","observation_steps":["concrete source observations"],"walkthrough":[{"source_text":"short exact excerpt","teaching_note":"substantive mechanism explanation"}]},"key_terms":[{"term":"domain term","meaning":"precise contextual definition"}],"worked_example":{"scenario":"concrete domain problem with values or named objects","steps":["at least three solved reasoning steps"],"solution":"complete worked answer and why it works"},"knowledge_check":{"prompt":"concept-specific question","expected_elements":["domain knowledge elements only"]},"transition":"substantive bridge to the next domain idea"},"rules":["Teach meaning, mechanism, assumptions, boundary cases, and consequences. Do not describe teaching or learning methods.","Use the excerpt only for claims it supports; use accurate general domain knowledge to complete the explanation.","Quote two to four short fragments from the supplied excerpt and explain each in domain terms.","Give a concrete fully solved example with at least three steps.","Do not use generic meta phrases: identify what goes in; locate the title; this line is evidence; a correct explanation; you should be able to.","Never mention Pathly, pedagogy, teaching methods, learning methods, mastery strategy, or content generation.","Do not invent quotations, page numbers, URLs, authors, results, or citations.","Put the main teaching in concept_explanation; source commentary is supporting evidence, not the lesson itself.","Return JSON only matching required_json."]}
    client=OpenAI(api_key=api_key,timeout=90.0,max_retries=1)
    last_error: Exception | None = None
    repair_note = ""
    for attempt in range(2):
        try:
            prompt = "Create a complete source-grounded lecture section.\n" + json.dumps(request,ensure_ascii=False,default=str)[:60000]
            if repair_note:
                prompt += "\nThe previous output failed validation. Repair it completely: " + repair_note
            response=client.responses.create(model=os.getenv("PATHLY_CONTENT_MODEL","gpt-5.4"),input=prompt,max_output_tokens=max(3600,min(7000,target_words*4)))
            raw=str(response.output_text or "").strip()
            if raw.startswith("```"): raw=raw.split("\n",1)[1].rsplit("```",1)[0]
            lesson=json.loads(raw); lesson["time_plan"]=_time_plan(minutes); _validate_live_lesson(label,lesson,minutes,source_available=source_available)
            lesson.update({"_generation_mode":"live","_quality_status":"complete","_fallback_reason":None,"_generation_attempts":attempt+1}); _LECTURE_CACHE[cache_key]=lesson; return lesson
        except Exception as exc:
            last_error = exc
            repair_note = f"{type(exc).__name__}: {str(exc)[:500]}. Return valid JSON with substantive domain teaching, not meta commentary."
    return {**fallback,"_generation_mode":"fallback","_quality_status":"source_coverage_insufficient","_fallback_reason":type(last_error).__name__ if last_error else "generation_failed","_generation_attempts":2}


def regenerate_full_lecture_section(session: dict[str, Any], section_id: str) -> dict[str, Any]:
    """Regenerate one scheduled section without changing its concept or the rest of the lecture."""
    match = re.fullmatch(r"lecture-section-(\d+)", str(section_id))
    readings = session.get("reading_sequence") or []
    if not match:
        raise ValueError("invalid lecture section id")
    index = int(match.group(1)) - 1
    if index < 0 or index >= len(readings):
        raise ValueError("lecture section not found")
    selected = deepcopy(readings[index])
    isolated = deepcopy(session)
    isolated["reading_sequence"] = [selected]
    isolated["scheduled_minutes"] = max(1, int(selected.get("estimated_minutes") or session.get("scheduled_minutes") or 1))
    section = generate_full_lecture(isolated)["lecture_sections"][0]
    section["section_id"] = section_id
    return section
def generate_full_lecture(session: dict[str, Any]) -> dict[str, Any]:
    """Generate a valid v3 lecture from annotated-session-v1 data."""
    payload = from_annotated_session(session)
    readings = session.get("reading_sequence") or []
    scheduled = int(session.get("scheduled_minutes") or 1)
    sections: list[dict[str, Any]] = []
    remaining = scheduled
    for index, reading in enumerate(readings, 1):
        if remaining <= 0:
            break
        minutes = int(reading.get("estimated_minutes") or max(1, scheduled // max(1, len(readings))))
        minutes = max(1, min(minutes, remaining))
        label = _label(reading)
        teaching = reading.get("teaching_expansion") or {}
        annotation = reading.get("pathly_annotation") or {}
        page_sequence = _normalise_page_sequence(reading)
        sequence_evidence = " ".join(f"[Page {page['page_start']}] {page.get('clean_excerpt') or ''}" for page in page_sequence if page.get("clean_excerpt")).strip()
        evidence = prepare_evidence(sequence_evidence or reading.get("clean_excerpt") or "", max_chars=4800)
        source_ref = reading.get("citation_id") or reading.get("reading_id")
        has_real_source = reading.get("source_type") in {"private_document", "public_rag"} and bool(evidence["clean_text"])
        page_lesson = _live_page_led_lesson(label=label, minutes=minutes, evidence_text=(evidence["clean_text"] if has_real_source else ""), teaching=teaching, annotation=annotation, source_title=(reading.get("document_title") if has_real_source else None), page_start=(reading.get("page_start") if has_real_source else None), source_available=has_real_source)
        page_lesson["page_sequence_guide"] = _page_sequence_guide(page_sequence, label) if has_real_source else []
        sections.append({
            "section_id": f"lecture-section-{index}",
            "title": f"{label}: from source to understanding",
            "estimated_minutes": minutes,
            "concept_ids": reading.get("linked_concept_ids") or [],
            "source_refs": ([source_ref] if source_ref and has_real_source else []),
            "document_id": (reading.get("document_id") if has_real_source else None),
            "document_title": (reading.get("document_title") if has_real_source else None),
            "page_start": (reading.get("page_start") if has_real_source else None),
            "page_end": (reading.get("page_end") if has_real_source else None),
            "page_sequence": (page_sequence if has_real_source else []),
            "teaching": {
                "explanation": teaching.get("concept_intro") or annotation.get("plain_explanation") or f"{label} is explained through the selected source.",
                "worked_example": teaching.get("worked_interpretation") or f"Use the excerpt to identify one concrete case of {label}.",
                "misconceptions": teaching.get("common_traps") or [f"Do not treat the name of {label} as an explanation of how it works."],
                "takeaway": annotation.get("why_it_matters") or f"You should be able to describe what {label} does and when it applies.",
            },
            "page_led_lesson": page_lesson,
            "source_grounding": {"has_real_source": has_real_source, "source_type": (reading.get("source_type") if has_real_source else "none")},
            "content_quality": {"status": page_lesson.get("_quality_status"), "generation_mode": page_lesson.get("_generation_mode"), "reason": page_lesson.get("_fallback_reason"), "teaching_words": _teaching_word_count(page_lesson)},
            "source_excerpt": (evidence["clean_text"] if has_real_source else ""),
            "reading_prompt": f"Read the excerpt, then explain {label} using your own words and one concrete example.",
        })
        remaining -= minutes
    if not sections:
        return validate_full_lecture(payload)
    payload["generator_version"] = FULL_LECTURE_GENERATOR_VERSION
    payload["lecture_sections"] = sections
    payload["practice_set"] = {
        "items": [
            {
                "type": "source_application",
                "prompt": f"Choose one section and apply {sections[0]['title'].split(':', 1)[0]} to a concrete case.",
                "source_refs": sections[0]["source_refs"],
            }
        ]
    }
    payload["knowledge_check"] = {
        "items": [
            {
                "type": "short_answer",
                "prompt": "What is the central mechanism described in today's source material?",
                "source_refs": [ref for section in sections for ref in section["source_refs"]],
            }
        ]
    }
    payload["generation_metadata"].update({
        "generation_mode": ("live" if all(s.get("content_quality", {}).get("generation_mode") == "live" for s in sections) else ("mixed" if any(s.get("content_quality", {}).get("generation_mode") == "live" for s in sections) else "fallback")),
        "cache_status": "miss",
        "generator_version": FULL_LECTURE_GENERATOR_VERSION,
        "evidence_prepared": len(sections),
        "fallback_reason": (None if all(s.get("content_quality", {}).get("generation_mode") == "live" for s in sections) else "one or more sections failed the teaching quality gate"),
    })
    return validate_full_lecture(payload)



def generate_full_lecture_from_daily(daily: dict[str, Any]) -> dict[str, Any]:
    """Build a v3 lecture directly from daily-content-v2 when v2 sources are absent."""
    overview = daily.get("session_overview") or {}
    blocks = daily.get("study_blocks") or []
    citations = daily.get("citations") or []
    scheduled = int(daily.get("scheduled_minutes") or overview.get("total_minutes") or 1)
    remaining = scheduled
    resources_by_id = {str(resource.get("resource_id")): resource for resource in (daily.get("required_resources") or []) if resource.get("resource_id")}
    sections = []
    for index, block in enumerate(blocks, 1):
        if remaining <= 0:
            break
        minutes = max(1, min(int(block.get("estimated_minutes") or 1), remaining))
        content = block.get("content") or {}
        resource = resources_by_id.get(str(content.get("resource_id") or block.get("resource_id") or ""), {})
        reading_scope = resource.get("reading_scope") or content.get("reading_scope") or {}
        title = block.get("title") or f"Learning section {index}"
        daily_page_sequence = _normalise_page_sequence({"page_start": reading_scope.get("page_start"), "page_end": reading_scope.get("page_end"), "section_title": reading_scope.get("section_title") or title, "clean_excerpt": content.get("guided_excerpt") or ""})
        sections.append({
            "section_id": f"daily-{block.get('block_id') or index}",
            "title": title, "estimated_minutes": minutes,
            "concept_ids": block.get("concept_ids") or [], "source_refs": block.get("source_refs") or [],
            "document_id": resource.get("document_id"),
            "document_title": resource.get("title") or resource.get("document_title"),
            "page_start": reading_scope.get("page_start"),
            "page_end": reading_scope.get("page_end"),
            "page_sequence": daily_page_sequence,
            "teaching": {
                "explanation": content.get("plain_explanation") or content.get("explanation") or content.get("body") or f"Work through {title} using today's learning session.",
                "worked_example": content.get("worked_example") or content.get("example") or "Apply the idea to one concrete case from today's topic.",
                "misconceptions": content.get("common_misconceptions") or [],
                "takeaway": content.get("takeaway") or content.get("summary") or f"Explain the main idea of {title} in your own words.",
            },
            "page_led_lesson": _page_led_lesson(label=title, minutes=minutes, evidence_text=content.get("guided_excerpt") or content.get("plain_explanation") or content.get("explanation") or "Use the scheduled source and activity to build this idea.", teaching=content, annotation={}, source_title=resource.get("title") or resource.get("document_title"), page_start=reading_scope.get("page_start")),
        })
        remaining -= minutes
    if not sections:
        sections = [{
            "section_id": "daily-session-overview", "title": overview.get("title") or "Today's learning session",
            "estimated_minutes": scheduled, "concept_ids": daily.get("topic_ids") or [], "source_refs": [],
            "teaching": {
                "explanation": overview.get("opening_hook") or "Use today's scheduled learning activities to build understanding.",
                "worked_example": "Connect the concept to one concrete problem.",
                "misconceptions": [], "takeaway": "State the concept and its practical use.",
            },
        }]
    payload = {
        "contract_version": "full-lecture-v3", "generator_version": FULL_LECTURE_GENERATOR_VERSION,
        "content_id": daily.get("content_id") or f"daily-{daily.get('plan_id')}-{daily.get('day')}",
        "path_id": daily.get("path_id"), "plan_id": daily.get("plan_id"), "plan_version": daily.get("plan_version"),
        "day": int(daily.get("day") or 1), "scheduled_minutes": scheduled,
        "lecture_overview": {
            "title": overview.get("title") or f"Day {daily.get('day', 1)} Full Lecture",
            "why_this_matters": overview.get("opening_hook") or overview.get("personalization_note") or "This lecture expands today's scheduled learning activities.",
            "objectives": overview.get("learning_objectives") or [], "prerequisite_recap": overview.get("prerequisite_recap") or [],
        },
        "source_materials": daily.get("required_resources") or [], "lecture_sections": sections,
        "practice_set": {"items": [{"type": "scheduled_practice", "prompt": "Complete the practice activity in today's learning session."}]},
        "knowledge_check": {"items": [{"type": "scheduled_check", "prompt": "Use the daily quiz to check today's objectives."}]},
        "citations": citations,
        "generation_metadata": {
            "generation_mode": "fallback", "cache_status": "daily_session_fallback",
            "generator_version": FULL_LECTURE_GENERATOR_VERSION,
            "fallback_reason": "annotated source session unavailable; generated from available daily session",
        },
    }
    return validate_full_lecture(payload)












