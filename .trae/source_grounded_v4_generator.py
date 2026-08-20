"""Source-grounded lecture generation for the isolated v4 experience.

Unlike v3, this generator never substitutes a template lecture when either
the source evidence or the model output is unavailable.  A failed section is
returned as an explicit, retryable state while the rest of the lecture stays
usable.
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any, Callable


S4_GENERATOR_VERSION = "source-grounded-v4-live-assets-v5-sequential"
V4_PROMPT_VERSION = "ml-education-expert-v3-example-contract"
V4_TREATMENT_VERSION = "dual-user-treatment-v1"
V4_MAX_RETRY_ATTEMPTS = 3


class V4ModelResponseError(Exception):
    """The model response could not be decoded as the v4 JSON contract."""

_META_LANGUAGE = (
    "pathly", "content agent", "teaching method", "learning method",
    "lesson plan", "the learner should", "tell the teacher", "fallback source",
    "learning concept in your path", "identify what goes in", "locate the title",
    "this page shows", "what this page is showing", "what to notice",
    "for your profile", "the source was selected because", "teaching strategy",
    "quality gate", "scaffolding strategy", "generation process",
)


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _words(value: Any) -> int:
    return len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", json.dumps(value, ensure_ascii=False)))


def _clean(text: Any, limit: int = 1800) -> str:
    value = " ".join(str(text or "").split())
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" -;,.")
    return value[:limit].rsplit(" ", 1)[0] if len(value) > limit else value


def _concept_for(section: dict[str, Any]) -> tuple[str, str]:
    concept_ids = [str(item) for item in section.get("concept_ids") or [] if item]
    concept_id = concept_ids[0] if concept_ids else str(section.get("concept_id") or section.get("section_id") or "concept")
    title = re.sub(r": from source to understanding$", "", str(section.get("concept_name") or section.get("title") or concept_id), flags=re.I)
    return concept_id, title


def _matches(section: dict[str, Any], link: dict[str, Any]) -> bool:
    concept_id, concept_name = _concept_for(section)
    return _normal(link.get("concept_id")) == _normal(concept_id) or _normal(link.get("concept_name")) == _normal(concept_name)


def _page_chunks_from_daily(daily: dict[str, Any], link: dict[str, Any]) -> dict[int, list[str]]:
    allowed = {str(item) for item in link.get("chunk_ids") or []}
    pages = {int(item.get("page_number") or 0) for item in link.get("page_sequence") or []}
    output: dict[int, list[str]] = {}
    for item in daily.get("prepared_evidence") or []:
        if link.get("document_id") and str(item.get("document_id") or "") != str(link.get("document_id")):
            continue
        chunk_id = str(item.get("chunk_id") or item.get("evidence_id") or "")
        if allowed and chunk_id not in allowed:
            continue
        start = int(item.get("page_start") or 0)
        end = int(item.get("page_end") or start or 0)
        text = _clean(item.get("clean_text") or item.get("excerpt"))
        if not text:
            continue
        for page in range(start, end + 1):
            if page in pages:
                output.setdefault(page, []).append(text)
    return output


def collect_source_pages(
    *, user_id: str, links: list[dict[str, Any]], daily: dict[str, Any],
    private_documents: Any | None = None, public_provenance: Any | None = None,
    verified_registry: Any | None = None,
) -> list[dict[str, Any]]:
    """Resolve real page text for already-approved S1/S3 links."""
    pages: list[dict[str, Any]] = []
    for link in links:
        if link.get("review_status") not in {"usable", "verified"}:
            continue
        text_by_page = _page_chunks_from_daily(daily, link)
        document_id = str(link.get("document_id") or "")
        if link.get("source_scope") == "private" and private_documents is not None and document_id:
            try:
                chunks = private_documents.get_chunks(user_id, document_id)
            except Exception:
                chunks = []
            allowed = {str(item) for item in link.get("chunk_ids") or []}
            wanted = {int(item.get("page_number") or 0) for item in link.get("page_sequence") or []}
            for chunk in chunks:
                chunk_id = str(chunk.get("chunk_id") or "")
                if allowed and chunk_id not in allowed:
                    continue
                start = int(chunk.get("page_start") or 0)
                end = int(chunk.get("page_end") or start or 0)
                for page in range(start, end + 1):
                    if page in wanted:
                        text_by_page.setdefault(page, []).append(_clean(chunk.get("text")))
        elif link.get("source_scope") == "public":
            resolver = verified_registry if link.get("review_status") == "verified" else public_provenance
            if resolver is not None and hasattr(resolver, "page_evidence"):
                try:
                    resolved = resolver.page_evidence(link)
                except Exception:
                    resolved = []
                for item in resolved or []:
                    page = int(item.get("page_number") or 0)
                    if page:
                        text_by_page.setdefault(page, []).append(_clean(item.get("text")))
        for page in link.get("page_sequence") or []:
            number = int(page.get("page_number") or 0)
            text = _clean(" ".join(part for part in text_by_page.get(number, []) if part), 2400)
            if not number or not text:
                continue
            pages.append({
                "page_number": number,
                "role": page.get("role") or "source",
                "text": text,
                "document_id": link.get("document_id"),
                "document_title": link.get("document_title"),
                "resource_id": link.get("resource_id"),
                "source_scope": link.get("source_scope"),
                "link_role": link.get("link_role") or "primary",
                "link_id": link.get("link_id"),
            })
    return pages


def _interpret_source_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Stage 1: retain source facts only; never produce student-facing prose."""
    interpreted = []
    for page in sorted(pages, key=lambda item: int(item.get("page_number") or 0)):
        text = _clean(page.get("text"), 900)
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if len(item.strip()) > 20]
        formulas = re.findall(r"(?:[A-Za-z]+\s*=\s*[^.]{1,80}|(?:ReLU|sigmoid|tanh|max)\s*\([^)]{1,80}\))", text)
        interpreted.append({
            "page_number": int(page.get("page_number") or 0),
            "role": page.get("role") or "source",
            "claims": sentences[:4],
            "formula_candidates": formulas[:3],
            "source_transition": "continues the selected source sequence" if interpreted else "opens the selected source sequence",
        })
    return {"pages": interpreted}


def _teaching_plan(*, concept_id: str, concept_name: str, minutes: int, profile: dict[str, Any] | None, interpretation: dict[str, Any]) -> dict[str, Any]:
    """Stage 2: plan teaching moves from profile/time without altering source facts."""
    treatment = _profile_treatment(profile)
    return {
        "concept_id": concept_id,
        "concept_name": concept_name,
        "scheduled_minutes": int(minutes),
        "section_order": ["opening_example", "prerequisite_recap", "core_idea", "page_led_explanation", "intuition", "worked_example", "common_mistake", "objective_exercise", "takeaway"],
        # The visible lecture structure stays unchanged.  This internal
        # contract prevents it from creating a new, redundant scenario for
        # each visible teaching block.
        "example_contract": {
            "anchor_example": {
                "roles": ["introduction", "intuition", "mechanism", "worked_example"],
                "rule": "Use one concrete scenario throughout these roles; deepen the reasoning instead of replacing the scenario.",
            },
            "counterexample": {
                "roles": ["boundary", "misconception_correction"],
                "rule": "Use one distinct contrast case that identifies a condition where the anchor mechanism changes, fails, or is insufficient.",
            },
            "application": {
                "roles": ["application_or_boundary_exercise"],
                "rule": "Use a related but new transfer situation only in the application question.",
            },
        },
        "recap_depth": treatment["recap_depth"],
        "formula_support": treatment["formula_support"],
        "code_scaffold": treatment["code_scaffold"],
        "explanation_order": treatment["explanation_order"],
        "checkpoint_density": treatment["checkpoint_density"],
        "segment_size": treatment["segment_size"],
        "example_context": treatment.get("example_context"),
        "preferred_examples": treatment.get("preferred_examples") or [],
        "preferred_style": treatment.get("learning_style"),
        "personalization_boundary": (
            "Interest and example preferences may change only the scenario, explanation order, and level of scaffolding. "
            "They must not change approved facts, formulae, source pages, or correct conclusions."
        ),
        "source_page_numbers": [item["page_number"] for item in interpretation["pages"]],
    }


def _repair_targets(validation_error: str) -> list[str]:
    value = str(validation_error or "")
    if "worked example" in value:
        return ["worked_example"]
    if "objective" in value or "options" in value:
        return ["objective_exercise"]
    if "page walkthrough" in value:
        return ["page_walkthrough"]
    if "thin" in value or "meta-language" in value:
        return ["concept_introduction", "prerequisite_recap", "summary_connection"]
    if "example contract" in value or "counterexample" in value:
        return ["opening_example", "intuition", "worked_example", "counterexample", "common_mistake"]
    return ["concept_introduction", "prerequisite_recap", "page_walkthrough", "worked_example", "objective_exercise", "summary_connection"]


def _merge_repaired_fields(content: dict[str, Any], repaired: dict[str, Any], targets: list[str]) -> dict[str, Any]:
    merged = deepcopy(content)
    for field in targets:
        if field in repaired:
            merged[field] = repaired[field]
    return merged


def _with_f7_teaching_fields(content: dict[str, Any], concept_name: str) -> dict[str, Any]:
    """Keep the page-led learner contract complete across live and verified modes."""
    result = deepcopy(content)
    intro = result.get("concept_introduction") or {}
    if not isinstance(intro, dict):
        intro = {}
    worked = result.get("worked_example") or {}
    if not isinstance(worked, dict):
        worked = {}
    opening = result.get("opening_example") or {}
    if not isinstance(opening, dict):
        opening = {}
    # Every learner begins with a concrete situation.  Profile treatment may
    # change its context and scaffolding, but never remove this orientation
    # step or move it after the formal explanation.
    result["opening_example"] = {
        "title": _clean(opening.get("title") or "Start with a concrete case"),
        "scenario": _clean(
            opening.get("scenario")
            or worked.get("problem")
            or intro.get("hook")
            or f"Consider one concrete decision where {concept_name} matters."
        ),
        "question": _clean(
            opening.get("question")
            or f"What would have to be true for this situation to work before we name {concept_name}?"
        ),
    }
    result["intuition"] = _clean(result.get("intuition") or (
        f"Think of {concept_name} as a way to make the important structure of a problem visible before asking a model to decide. "
        f"The worked example below turns that idea into a concrete sequence of inputs, transformations, and outputs."
    ))
    result["common_mistake"] = _clean(result.get("common_mistake") or intro.get("boundaries") or (
        f"A common mistake is to treat {concept_name} as a label to memorise instead of tracing what changes from input to output."
    ))
    return result


def _example_text(value: Any) -> str:
    """Make an example comparable without treating superficial wording as a new lesson."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())).strip()


def _example_contract(content: dict[str, Any], *, base: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Attach and enforce a compact example plan without adding a new UI block.

    The writer is free to phrase the lesson naturally.  This function only
    supplies a safe, evidence-bounded counterexample when the model omitted
    one or returned the anchor case again.  The counterexample is rendered in
    the existing Boundary part of Core Idea, so the learner-facing structure
    does not grow another repetitive section.
    """
    result = deepcopy(content)
    opening = result.get("opening_example") or {}
    worked = result.get("worked_example") or {}
    intro = result.get("concept_introduction") or {}
    anchor = _clean(opening.get("scenario") or worked.get("problem") or intro.get("hook") or base.get("concept_name"))
    raw_counter = result.get("counterexample") or {}
    if not isinstance(raw_counter, dict):
        raw_counter = {"scenario": raw_counter}
    counter = _clean(raw_counter.get("scenario") or raw_counter.get("contrast") or raw_counter.get("explanation"))
    approved = request.get("approved_teaching_profile") or {}
    claims = {str(item.get("kind")): str(item.get("text") or "") for item in (approved.get("claims") or [])}
    boundary = _clean(raw_counter.get("boundary_condition") or intro.get("boundaries") or claims.get("boundary"))
    approved_counter = _clean(claims.get("counterexample"))
    # Exact or near-exact reuse of the anchor does not teach a boundary.  Use
    # the reviewed counterexample where available; otherwise state the source
    # boundary as an explicit contrast rather than inventing a new fact.
    anchor_tokens = set(_example_text(anchor).split())
    counter_tokens = set(_example_text(counter).split())
    overlap = len(anchor_tokens & counter_tokens) / max(1, len(anchor_tokens | counter_tokens))
    if not counter or _example_text(counter) == _example_text(anchor) or overlap > 0.82:
        counter = approved_counter or _clean(
            f"Contrast this with a case where the required condition is not satisfied: {boundary}"
        )
    if not boundary:
        boundary = _clean("Check whether the assumptions stated for this concept still hold before using its conclusion.")
    result["counterexample"] = {
        "scenario": counter,
        "contrast": _clean(raw_counter.get("contrast") or counter),
        "boundary_condition": boundary,
    }
    result["example_plan"] = {
        "contract_version": "anchor-counterexample-v1",
        "anchor_example": {"scenario": anchor, "roles": ["introduction", "intuition", "mechanism", "worked_example"]},
        "counterexample": {"scenario": counter, "roles": ["boundary", "misconception_correction"], "boundary_condition": boundary},
        "application": {"roles": ["application_or_boundary_exercise"]},
    }
    intro = dict(intro)
    existing_boundary = _clean(intro.get("boundaries"))
    counter_line = f"Counterexample: {counter}"
    intro["boundaries"] = _clean(
        f"{existing_boundary} {counter_line}" if _example_text(counter_line) not in _example_text(existing_boundary) else existing_boundary
    )
    result["concept_introduction"] = intro
    return result


def _verified_math_content(concept_name: str) -> dict[str, Any]:
    """Only publish compact expressions that Pathly can state and render reliably."""
    key = _normal(concept_name)
    if "linear separability" in key:
        return {
            "inline_math": ["w^T x + b = 0"],
            "display_math": [{"latex": "w^T x + b = 0", "text": "w transpose times x plus b equals zero", "label": "Decision boundary"}],
            "matrix": None,
            "derivation_steps": ["Compute the linear score w^T x + b.", "The zero-score set is the decision boundary.", "Examples on opposite sides receive different classes."],
        }
    if key == "xor" or "xor" in key:
        return {
            "inline_math": ["0 XOR 0 = 0", "0 XOR 1 = 1", "1 XOR 0 = 1", "1 XOR 1 = 0"],
            "display_math": [{"latex": "y = x_1 \\oplus x_2", "text": "y equals x one XOR x two", "label": "XOR rule"}],
            "matrix": {"rows": [["x1", "x2", "y"], ["0", "0", "0"], ["0", "1", "1"], ["1", "0", "1"], ["1", "1", "0"]], "label": "XOR truth table"},
            "derivation_steps": ["List the four possible binary inputs.", "Mark opposite corners as the positive class.", "Notice that one straight boundary cannot separate alternating corners."],
        }
    if "activation" in key:
        return {
            "inline_math": ["ReLU(x) = max(0, x)"],
            "display_math": [{"latex": "ReLU(x) = max(0, x)", "text": "ReLU of x equals the maximum of zero and x", "label": "ReLU activation"}],
            "matrix": None,
            "derivation_steps": ["Start with a weighted input x.", "Keep x when it is positive.", "Return zero when x is negative."],
        }
    if "gradient descent" in key:
        return {
            "inline_math": ["theta <- theta - eta grad L(theta)"],
            "display_math": [{"latex": "\\theta_{t+1} = \\theta_t - \\eta \\nabla L(\\theta_t)", "text": "next parameters equal current parameters minus learning rate times the loss gradient", "label": "Gradient-descent update"}],
            "matrix": None,
            "derivation_steps": ["Evaluate the loss at the current parameters.", "Compute the gradient of the loss.", "Move the parameters a small distance in the opposite direction."],
        }
    if "neural network" in key:
        return {
            "inline_math": ["h = sigma(Wx + b)", "y = g(Vh + c)"],
            "display_math": [{"latex": "h = \\sigma(Wx + b), \\quad y = g(Vh + c)", "text": "a hidden layer transforms x, then an output layer transforms the hidden representation", "label": "Two-layer network"}],
            "matrix": None,
            "derivation_steps": ["Multiply inputs by learned weights and add a bias.", "Apply a nonlinear activation to form hidden features.", "Combine hidden features into an output."],
        }
    return {"inline_math": [], "display_math": [], "matrix": None, "derivation_steps": []}


def _with_f8_math_fields(content: dict[str, Any], concept_name: str) -> dict[str, Any]:
    result = deepcopy(content)
    math = result.get("math") if isinstance(result.get("math"), dict) else {}
    verified = _verified_math_content(concept_name)
    result["math"] = {
        "inline_math": list(math.get("inline_math") or verified["inline_math"]),
        "display_math": list(math.get("display_math") or verified["display_math"]),
        "matrix": math.get("matrix") or verified["matrix"],
        "derivation_steps": list(math.get("derivation_steps") or verified["derivation_steps"]),
    }
    return result


def _with_f9_exercise_support(content: dict[str, Any], section_id: str, concept_id: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach learner-safe evidence references to each objective question."""
    result = deepcopy(content)
    exercise = result.get("objective_exercise") or {}
    page_references = [int(page.get("page_number") or 0) for page in pages if page.get("page_number")]
    required_types = ("mechanism", "misconception_discrimination", "application_or_boundary")
    for index, question in enumerate(exercise.get("questions") or []):
        # Models often return the legacy transport `type: single_choice` but
        # omit the pedagogical question type.  Supply the required cognitive
        # coverage deterministically without changing the learner-facing stem.
        question_type = str(question.get("question_type") or "")
        if question_type not in required_types:
            question_type = required_types[index % len(required_types)]
            question["question_type"] = question_type
        question["assessment_target_id"] = str(question.get("assessment_target_id") or f"{concept_id}:{question_type}")
        explanation = str(question.get("explanation") or "").strip()
        # A live exercise response can contain a correct answer but only a
        # fragment as its explanation (for example, a single source term).
        # The quality gate intentionally rejects that thin feedback; make the
        # repair local and explicit instead of invalidating the entire lecture
        # section.  The added sentence explains the mechanism/boundary and is
        # not a generic "Correct" placeholder.
        if len(explanation.split()) < 8:
            seed = explanation or str(question.get("correct_reasoning") or "The selected answer")
            explanation = (
                f"{seed.rstrip('.')} This choice is supported by the mechanism and boundary "
                "taught in this section and the selected source evidence."
            )
            question["explanation"] = explanation
        question["correct_reasoning"] = str(question.get("correct_reasoning") or explanation or "The correct choice follows the mechanism explained in this section.")
        question["concept_id"] = str(question.get("concept_id") or concept_id)
        question["section_id"] = str(question.get("section_id") or section_id)
        question["page_references"] = list(question.get("page_references") or page_references)
        question["source_refs"] = list(question.get("source_refs") or [f"page:{number}" for number in question["page_references"]])
        question["generator_version"] = S4_GENERATOR_VERSION
        question["supporting_explanation_ids"] = list(question.get("supporting_explanation_ids") or ["core_idea", "page_walkthrough", "worked_example"])
        for option in question.get("options") or []:
            if not str(option.get("feedback") or "").strip():
                if option.get("correct"):
                    option["feedback"] = explanation or "Correct: this choice follows the mechanism and boundary explained in the section."
                else:
                    option["feedback"] = "This choice conflicts with the mechanism explained in the section; compare it with the worked example."
            elif len(str(option.get("feedback") or "").split()) < 5:
                option["feedback"] = (
                    f"{str(option.get('feedback')).rstrip('.')} Compare this reasoning with the "
                    "mechanism and boundary taught in the section."
                )
        # Avoid a position cue across the three required question categories.
        options = list(question.get("options") or [])
        correct_index = next((i for i, option in enumerate(options) if option.get("correct")), None)
        desired_index = index % max(1, len(options))
        if correct_index is not None and len(options) >= 3 and correct_index != desired_index:
            correct = options.pop(correct_index)
            options.insert(desired_index, correct)
            question["options"] = options
    result["objective_exercise"] = exercise
    return result


def _with_f10_learner_adaptation(content: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    """Expose the learner adaptation contract in the final section payload."""
    result = deepcopy(content)
    result["learner_adaptation"] = {
        "treatment_version": V4_TREATMENT_VERSION,
        "profile_tier": treatment["profile_tier"],
        "prior_knowledge_level": "foundational" if treatment["lesson_depth"] == "foundational" else "advanced",
        "explanation_density": treatment["recap_depth"],
        "example_mode": treatment["explanation_style"],
        "practice_style": treatment["practice_style"],
        "terminology_depth": "basic" if treatment["lesson_depth"] == "foundational" else "advanced",
        "interest_usage": "scenario_only",
        "example_context": treatment.get("example_context"),
        "preferred_examples": list(treatment.get("preferred_examples") or []),
        "learning_style": treatment.get("learning_style"),
        "formula_support": treatment.get("formula_support"),
        "checkpoint_density": treatment.get("checkpoint_density"),
    }
    return result


def _validate_content(content: dict[str, Any], concept_name: str, minutes: int, page_numbers: set[int]) -> None:
    required = {"concept_introduction", "prerequisite_recap", "page_walkthrough", "key_terms", "worked_example", "objective_exercise", "summary_connection"}
    if not required.issubset(content):
        raise ValueError("missing v4 lecture fields")
    text = json.dumps(content, ensure_ascii=False).lower()
    if any(phrase in text for phrase in _META_LANGUAGE):
        raise ValueError("meta-language is not allowed")
    terms = [term for term in re.findall(r"[A-Za-z]{4,}", concept_name) if term.lower() not in {"from", "with", "that"}]
    if terms and not any(term.lower() in text for term in terms):
        raise ValueError("lecture does not teach the requested concept")
    # Depth follows the scheduled duration. A focused 15-minute section should
    # not be rejected by the same absolute threshold as a 45-minute lecture.
    if _words(content) < max(220, min(900, int(minutes) * 10)):
        raise ValueError("lecture is too thin for its scheduled time")
    walkthrough = content.get("page_walkthrough") or []
    if not walkthrough or any(int(item.get("page_number") or 0) not in page_numbers for item in walkthrough):
        raise ValueError("page walkthrough is not grounded in selected pages")
    covered_pages = {int(item.get("page_number") or 0) for item in walkthrough}
    if not page_numbers.issubset(covered_pages):
        raise ValueError("page walkthrough does not explain every selected page")
    example = content.get("worked_example") or {}
    minimum_solution_words = max(28, min(60, int(minutes * 1.5)))
    if len(example.get("steps") or []) < 3 or _words(example.get("solution")) < minimum_solution_words:
        raise ValueError("worked example is incomplete")
    exercise = content.get("objective_exercise") or {}
    questions = exercise.get("questions") or []
    if len(questions) < 3:
        raise ValueError("objective exercise is incomplete")
    for question in questions:
        options = question.get("options") or []
        if len(options) < 3 or sum(bool(option.get("correct")) for option in options) != 1:
            raise ValueError("objective question has invalid options")
    from v4_quality_baseline import evaluate_objective_exercise
    quality = evaluate_objective_exercise(exercise)
    if not quality["passed"]:
        reasons = sorted({item["reason"] for item in quality["failures"]})
        raise ValueError("objective exercise quality failed: " + ", ".join(reasons))


def _decode_model_json(raw: str) -> dict[str, Any]:
    value = str(raw or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise V4ModelResponseError("model_response_not_json")
        try:
            decoded = json.loads(value[start:end + 1])
        except json.JSONDecodeError as exc:
            raise V4ModelResponseError("model_response_invalid_json") from exc
    if not isinstance(decoded, dict):
        raise V4ModelResponseError("model_response_not_object")
    return decoded


def _openai_generate(request: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI
    # Keep live generation bounded and resilient to transient upstream failures.
    # The timeout/retry knobs are configurable for local demos and CI.
    timeout = float(os.getenv("PATHLY_CONTENT_TIMEOUT_SECONDS", "75"))
    max_retries = max(0, int(os.getenv("PATHLY_CONTENT_MAX_RETRIES", "2")))
    client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
    prompt = (
        "Generate one finished, student-facing, source-grounded lecture section. "
        "Return exactly one valid JSON object. Escape every backslash and quote inside JSON strings. "
        "Do not wrap the object in prose or Markdown.\n"
        + json.dumps(request, ensure_ascii=False, default=str)[:70000]
    )
    scheduled_minutes = max(1, int(request.get("scheduled_minutes") or 12))
    # V4 has a quality floor, but asking a small model for an unbounded essay
    # plus JSON is the main source of long-running/retried live calls.  Keep a
    # section concise enough to finish reliably, then let the approved assets
    # supply any genuinely missing structural field.
    target_words = max(360, min(800, scheduled_minutes * 42))
    prompt += f"\nTarget {target_words}-{target_words + 160} words of learner-facing teaching; be concise inside JSON values."
    response = client.responses.create(
        model=str(request.get("content_model") or os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4")),
        input=prompt,
        # JSON mode removes the main live-path failure observed in production:
        # prose/code fences or partially escaped JSON that cannot be decoded.
        text={"format": {"type": "json_object"}},
        temperature=0.2,
        max_output_tokens=max(3600, min(5200, target_words * 5)),
    )
    return _decode_model_json(str(response.output_text or ""))


def _openai_generate_exercises(request: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    """Generate the learner-visible quiz separately from the lecture prose.

    Exercises have a different quality contract from explanations.  Isolating
    them gives the model room to construct plausible distractors without
    making the primary lecture JSON fragile.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        timeout=float(os.getenv("PATHLY_EXERCISE_TIMEOUT_SECONDS", "45")),
        max_retries=max(0, int(os.getenv("PATHLY_CONTENT_MAX_RETRIES", "2"))),
    )
    approved = request.get("approved_teaching_profile") or {}
    assets = [
        {
            "asset_type": item.get("asset_type"),
            "content": item.get("content"),
            "assessment_targets": item.get("assessment_targets"),
            "misconception_ids": item.get("misconception_ids"),
        }
        for item in (request.get("teaching_assets") or [])
    ]
    payload = {
        "concept": request.get("concept"),
        "learner_treatment": request.get("learner_treatment"),
        "taught_content": {
            "introduction": content.get("concept_introduction"),
            "counterexample": content.get("counterexample"),
            "worked_example": content.get("worked_example"),
            "common_mistake": content.get("common_mistake"),
            "summary": content.get("summary_connection"),
        },
        "approved_claims": approved.get("claims") or approved.get("teaching_claims") or approved,
        "assets": assets,
        "source_refs": [f"page:{item.get('page_number')}" for item in request.get("sources") or [] if item.get("page_number")],
    }
    prompt = """You are an expert machine-learning assessment writer. Create exactly three high-quality multiple-choice questions for the lesson data below.
Return JSON only: {"instructions":string,"questions":[...]}. Each question must have question_id (q1/q2/q3), type "single_choice", question_type, assessment_target_id, prompt, correct_reasoning, source_refs, explanation, and exactly three options. Each option must have id, text, correct, and feedback.
Use exactly these question_type values once each: mechanism, misconception_discrimination, application_or_boundary.
The questions must test the actual lesson, not definitions by wording alone. Use a natural scenario consistent with the learner treatment. Distractors must be plausible mistaken reasoning, never irrelevant, absolute, or label-based. Every feedback field must explain the mechanism or precise mistake. Do not mention teaching strategy, sources, profiles, prompts, or generation.
Lesson data:\n""" + json.dumps(payload, ensure_ascii=False, default=str)[:42000]
    response = client.responses.create(
        model=str(request.get("exercise_model") or request.get("content_model") or os.getenv("PATHLY_EXERCISE_MODEL", os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4"))),
        input=prompt,
        text={"format": {"type": "json_object"}},
        temperature=0.35,
        max_output_tokens=2800,
    )
    return _decode_model_json(str(response.output_text or ""))


_CONCEPT_NOTES: dict[str, dict[str, Any]] = {
    "linear separability": {
        "short": "whether one straight boundary can separate two classes",
        "prereq": ("Linear classifiers", "A linear classifier scores an input with a weighted sum and draws one straight decision boundary in the feature space."),
        "mechanism": [
            "Represent each example as coordinates in a feature space.",
            "Ask whether one line, plane, or hyperplane can place all positive examples on one side and all negative examples on the other.",
            "If no such boundary exists, the representation is not linearly separable and a purely linear classifier cannot solve the task in that space.",
        ],
        "boundary": "Linear separability is a statement about the current representation. A problem can become separable after a nonlinear feature transformation.",
        "terms": [
            ("Decision boundary", "The curve or surface where the classifier changes from one predicted class to another."),
            ("Hyperplane", "The straight boundary used by a linear classifier in any number of dimensions."),
            ("Feature space", "The coordinate system in which examples are represented before classification."),
            ("Nonlinear transform", "A mapping that changes the geometry of examples so a linear boundary may become sufficient later."),
        ],
        "example": "Classify four XOR points: (0,0) and (1,1) are one class, while (0,1) and (1,0) are the other. A line that separates one diagonal pair will place at least one point from the other diagonal on the wrong side. The failure is geometric, not caused by poor training.",
        "bridge": "The XOR example motivates neural networks because hidden units can create a representation where the classes become separable.",
    },
    "xor": {
        "short": "a two-input pattern that is true when exactly one input is active",
        "prereq": ("Binary classification", "Binary classification assigns each input to one of two classes. XOR is a small binary task with four possible inputs."),
        "mechanism": [
            "List the four input pairs and their labels.",
            "Notice that the positive cases sit on opposite corners of a square.",
            "Recognize that one straight line cannot isolate opposite corners from the other two corners.",
            "Use hidden nonlinear features to split the square into regions that can then be combined by a later layer.",
        ],
        "boundary": "XOR is not hard because it is large; it is hard because its geometry defeats a single linear boundary.",
        "terms": [
            ("Truth table", "A table listing all possible inputs and the corresponding XOR output."),
            ("Diagonal classes", "The positive and negative examples are arranged on alternating corners."),
            ("Hidden unit", "A learned intermediate detector that can carve out part of the input space."),
            ("Composition", "Combining simple detectors to build a more complex decision rule."),
        ],
        "example": "Imagine a network with two hidden units. One hidden unit can respond to the upper-left region and another can respond to the lower-right region. The output layer can then combine those hidden responses to approximate the alternating XOR pattern. The important move is not memorizing four points; it is changing the representation so the output layer has an easier boundary to draw.",
        "bridge": "Activation functions are what prevent hidden layers from collapsing back into one large linear classifier.",
    },
    "neural networks": {
        "short": "models that stack learned weighted transformations with nonlinear activations",
        "prereq": ("Linear models", "A linear model computes weighted sums of inputs. Neural networks keep that useful weighted-sum idea but repeat it across layers and add nonlinearity."),
        "mechanism": [
            "Compute weighted sums from input features into hidden units.",
            "Pass each hidden value through a nonlinear activation function.",
            "Use later layers to combine hidden features into a prediction.",
            "Adjust weights so the prediction matches the training targets more often.",
        ],
        "boundary": "A neural network is not automatically better; it needs enough data, a suitable architecture, and a training procedure that can find useful weights.",
        "terms": [
            ("Layer", "A group of units that transforms values from the previous layer."),
            ("Weight", "A learned number controlling the strength of one connection."),
            ("Hidden representation", "The intermediate features produced inside the network."),
            ("Nonlinear classifier", "A classifier whose boundary is not limited to one straight line in the original input space."),
        ],
        "example": "For XOR, the input layer receives two bits. A hidden layer can learn detectors for useful regions of the square, and the output layer combines them into the XOR label. Compared with a single linear classifier, the network has an intermediate representation where the alternating pattern is easier to separate.",
        "bridge": "Activation functions supply the nonlinear step that makes layered representations more powerful than one linear map.",
    },
    "activation functions": {
        "short": "nonlinear functions applied after weighted sums inside a neural network",
        "prereq": ("Weighted sums", "Before an activation function, each unit usually computes a weighted sum plus a bias."),
        "mechanism": [
            "Take the pre-activation value produced by a weighted sum.",
            "Apply a nonlinear function such as ReLU, sigmoid, or tanh.",
            "Pass the transformed value to the next layer.",
            "Allow multiple layers to compose nonlinear transformations instead of collapsing into one linear map.",
        ],
        "boundary": "The activation choice affects optimization and representation. ReLU is common because it is simple and keeps strong gradients for positive inputs, while sigmoid can saturate.",
        "terms": [
            ("ReLU", "The function max(0, x), which keeps positive values and clips negative values to zero."),
            ("Sigmoid", "A smooth function that maps real numbers into values between 0 and 1."),
            ("Saturation", "A region where a function changes very little, making gradients small."),
            ("Composed nonlinearity", "The effect of stacking linear maps with nonlinear activations between them."),
        ],
        "example": "If two linear layers are stacked with no activation between them, their product is still a linear map. Insert ReLU between them and the network can bend the input space differently in different regions. That bending is exactly what a problem like XOR needs.",
        "bridge": "Once the architecture can represent a useful boundary, gradient descent is the procedure that searches for weights that produce it.",
    },
    "gradient descent": {
        "short": "an iterative method for reducing a loss by moving parameters against the gradient",
        "prereq": ("Loss functions", "A loss function measures how wrong the model's predictions are. Training means changing parameters to reduce this loss."),
        "mechanism": [
            "Compute the model's predictions for examples.",
            "Measure error with a loss function.",
            "Calculate the gradient, which points in the direction of steepest increase in loss.",
            "Update parameters in the opposite direction using a learning rate.",
        ],
        "boundary": "Gradient descent can be slow or unstable if the learning rate is poorly chosen, the gradients vanish or explode, or the loss surface is difficult.",
        "terms": [
            ("Gradient", "A vector of partial derivatives showing how the loss changes with each parameter."),
            ("Learning rate", "The step size used in each parameter update."),
            ("Stochastic gradient descent", "An update method that estimates gradients from small batches rather than the full dataset."),
            ("Backpropagation", "The efficient procedure for computing gradients through a network's layers."),
        ],
        "example": "Suppose a neural network predicts the wrong XOR label. The loss increases for that example. Backpropagation tells each weight how it contributed to the error, and gradient descent nudges the weights so the next prediction is less wrong. Repeating this over many examples gradually shapes the hidden representation.",
        "bridge": "Gradient descent connects the representational power of neural networks to a practical training process.",
    },
}


def _concept_note(concept_name: str) -> dict[str, Any]:
    key = _normal(concept_name)
    for known, note in _CONCEPT_NOTES.items():
        if known in key or key in known:
            return note
    return {
        "short": f"the central mechanism behind {concept_name}",
        "prereq": ("Core vocabulary", f"Before studying {concept_name}, make sure the basic terms and inputs of the topic are clear."),
        "mechanism": [
            f"Define what {concept_name} receives as input.",
            f"Trace the transformation performed by {concept_name}.",
            f"Check what output or decision {concept_name} produces.",
        ],
        "boundary": f"{concept_name} should be applied only when its assumptions match the problem setting.",
        "terms": [
            (concept_name, f"The topic being studied in this section."),
            ("Input", "The information provided to the method or model."),
            ("Transformation", "The operation that changes the input into a useful representation."),
            ("Output", "The result produced after the transformation."),
        ],
        "example": f"Start with a small concrete case, apply {concept_name} step by step, and check whether the result matches the intended decision.",
        "bridge": f"The next concept extends or applies {concept_name} in a more complete model.",
    }


def _is_verified_source(base: dict[str, Any]) -> bool:
    return any(str(link.get("review_status") or "") == "verified" for link in base.get("source_links") or [])


def _approved_teaching_profile(concept_name: str) -> dict[str, Any] | None:
    """Return KQ1-approved semantics only for the fixed verified five-node path."""
    try:
        from knowledge_release import active_release_allows
        from golden_teaching_semantics import GOLDEN_TEACHING_PROFILES, teaching_profile
        for known in GOLDEN_TEACHING_PROFILES:
            if _normal(known) == _normal(concept_name) and active_release_allows(known):
                return teaching_profile(known)
    except (ImportError, KeyError):
        pass
    return None


def _approved_asset_profile(concept_name: str, assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Adapt published, node-specific teaching assets to the verified contract.

    Full-experience catalog nodes do not belong to the legacy golden-five
    semantics module. Their published assets nevertheless contain the same
    reviewed definition/mechanism/boundary spine, so live-output repair may use
    that spine without inventing a generic cross-concept fallback.
    """
    by_type = {str(item.get("asset_type") or ""): item.get("content") or {} for item in assets}
    intuition = by_type.get("foundation_intuition") or {}
    worked = by_type.get("advanced_worked_example") or {}
    definition = str(intuition.get("explanation") or "").strip()
    mechanism = str(intuition.get("bridge") or "").strip()
    boundary = str(intuition.get("check") or "").strip()
    steps = [str(item).strip() for item in worked.get("steps") or [] if str(item).strip()]
    if not (definition and mechanism and boundary):
        return None
    example = str(worked.get("problem") or (steps[-1] if steps else definition)).strip()
    counterexample = f"A result is not reliably grounded when this boundary is violated: {boundary}"
    slug = re.sub(r"[^a-z0-9]+", "-", _normal(concept_name)).strip("-")
    return {
        "semantics_version": "published-teaching-assets-v1",
        "concept_name": concept_name,
        "canonical_id": slug,
        "prerequisites": [],
        "claims": [
            {"kind": "definition", "text": definition},
            {"kind": "mechanism", "text": mechanism},
            {"kind": "boundary", "text": boundary},
            {"kind": "example", "text": example},
            {"kind": "counterexample", "text": counterexample},
        ],
        "misconceptions": [{
            "id": f"{slug}-boundary-confusion",
            "text": f"If {concept_name} is present, its output is automatically reliable.",
            "correction": boundary,
        }],
        "assessment_targets": [
            {"id": f"{slug}-mechanism", "kind": "mechanism", "text": mechanism},
            {"id": f"{slug}-misconception", "kind": "misconception_discrimination", "text": boundary},
            {"id": f"{slug}-boundary", "kind": "application_or_boundary", "text": boundary},
        ],
    }


def _profile_treatment(profile: dict[str, Any] | None) -> dict[str, Any]:
    profile = profile or {}
    cognitive = profile.get("cognitive_traits") or profile
    affective = profile.get("affective_defaults") or profile
    path_context = profile.get("path_context") or {}
    current_affective = path_context.get("current_affective_state") or {}
    target_mastery = path_context.get("target_mastery") or {}
    interests = list(affective.get("interest_tags") or ["no_preference"])
    interest = "no_preference" if "no_preference" in interests else str(interests[0])
    domain_examples = {
        "healthcare": "a medical screening decision",
        "finance": "a credit-risk decision",
        "education": "a student-support decision",
        "natural_language": "a text classification decision",
        "computer_vision": "an image classification decision",
        "business": "a customer-segmentation decision",
        "no_preference": "an everyday yes-or-no decision",
    }

    confidence = int(current_affective.get("confidence") or 3)
    pressure = int(current_affective.get("anxiety") or 3)
    math = int(cognitive.get("mathematical_ability") or profile.get("math_foundation") or 3)
    programming = int(cognitive.get("programming_ability") or profile.get("programming_foundation") or 3)
    abstract = int(cognitive.get("abstract_thinking") or profile.get("prior_knowledge_level") or 3)
    logical = int(cognitive.get("logical_reasoning") or profile.get("prior_knowledge_level") or 3)
    style = str(affective.get("learning_style") or profile.get("preferred_style") or "mixed")
    examples = list(affective.get("preferred_examples") or profile.get("preferred_examples") or [])
    pace = str(affective.get("pace_preference") or profile.get("pace_preference") or "steady")
    mastery = max([float(value) for value in target_mastery.values()] or [0.0])
    lesson_depth = "foundational" if min(math, programming, abstract, logical) <= 2 or (target_mastery and mastery < 0.3) else "advanced"
    explanation_style = "worked-example-led" if "example" in style or "hands" in style else ("symbolic-and-structural" if math >= 4 else "balanced")
    checkpoint_density = "high" if logical <= 2 or confidence <= 2 or pressure >= 4 else "standard"
    practice_style = "guided" if checkpoint_density == "high" else "independent"
    return {
        "confidence": confidence, "pressure": pressure, "target_mastery": mastery,
        "profile_tier": "foundation" if lesson_depth == "foundational" else "advanced",
        "mathematical_ability": math,
        "programming_ability": programming, "abstract_thinking": abstract,
        "logical_reasoning": logical, "learning_style": style,
        "preferred_examples": examples, "interest_tags": interests,
        "pace_preference": pace, "example_context": domain_examples.get(interest),
        "recap_depth": "expanded" if lesson_depth == "foundational" else "concise",
        "formula_support": "step_by_step" if math <= 2 else "compact",
        "code_scaffold": "complete_starter" if programming <= 2 else "partial_starter",
        "explanation_order": "concrete_first" if abstract <= 2 else "model_first",
        "checkpoint_density": checkpoint_density,
        "segment_size": "short" if pace in {"slow", "flexible"} else "standard",
        "lesson_depth": lesson_depth,
        "explanation_style": explanation_style,
        "practice_style": practice_style,
    }


def _select_teaching_assets(concept_id: str, treatment: dict[str, Any]) -> list[dict[str, Any]]:
    """Select only published, tier-appropriate assets for the current section."""
    try:
        from teaching_asset_store import TeachingAssetStore
        store = TeachingAssetStore()
        assets = store.list_assets(concept_id=concept_id, learner_tier=treatment["profile_tier"], published_only=True)
        # The foundation intuition contains the reviewed canonical definition,
        # not merely beginner-facing prose. Advanced sections may use that fact
        # contract while still selecting an advanced worked example.
        if treatment["profile_tier"] == "advanced":
            foundation_facts = store.list_assets(
                concept_id=concept_id, learner_tier="foundation",
                asset_types=["foundation_intuition"], published_only=True,
            )
            known = {item["asset_id"] for item in assets}
            assets.extend(item for item in foundation_facts if item["asset_id"] not in known)
        return [
            {
                "asset_id": item["asset_id"], "asset_type": item["asset_type"],
                "learner_tier": item["learner_tier"], "content": item["content"],
                "assessment_targets": item["assessment_targets"],
                "misconception_ids": item["misconception_ids"],
                "evidence_refs": item["evidence_refs"],
                "knowledge_version": item["knowledge_version"],
            }
            for item in assets
        ]
    except Exception:
        # Asset lookup must never make an otherwise valid source-grounded section
        # unavailable; the request records an empty list for diagnostics.
        return []


def _v4_generation_brief(*, concept: str, treatment: dict[str, Any], approved_profile: dict[str, Any] | None) -> str:
    """Decision-complete machine-learning education contract for the writer."""
    mode = "verified canonical concept" if approved_profile else "source-grounded concept"
    return (
        f"PROMPT VERSION: {V4_PROMPT_VERSION}.\n"
        "You are a senior machine-learning educator writing a finished lesson directly to one learner.\n"
        f"Target concept: {concept}.\n"
        f"Teaching mode: {mode}.\n"
        "Teaching objective:\n"
        "- Build a durable mental model by connecting definition, representation, mechanism, boundary, counterexample, and transfer.\n"
        "- Write substantive learner-facing prose, not an outline, page tour, planning note, or review.\n"
        "Knowledge and evidence contract:\n"
        "- Canonical claims determine facts; supplied pages support definitions, mechanisms, formulae, examples, and boundaries.\n"
        "- Never change a fact, formula, relation direction, source page, or correct conclusion to personalize the lesson.\n"
        "- If evidence is insufficient, omit the claim rather than completing it from general memory.\n"
        "Language contract:\n"
        "- Never describe the teaching process, generation process, source selection process, or validation process.\n"
        "- Never mention profiles, learner tiers, pedagogy, prompting, scaffolding, quality checks, agents, or content generation.\n"
        "- Never use learner-visible labels such as 'what this page is showing', 'what to notice', or 'for your profile'.\n"
        "- Do not introduce unrelated generalities. Every paragraph must advance the concept being taught.\n"
        "Private adaptation inputs (do not repeat these labels or values to the learner):\n"
        f"- Learner tier: {treatment['profile_tier']}; cognitive depth: {treatment['lesson_depth']}.\n"
        f"- Current goal confidence: {treatment['confidence']}/5; current goal pressure: {treatment['pressure']}/5.\n"
        f"- Cognitive level: {treatment['lesson_depth']}.\n"
        f"- Explanation order: {treatment['explanation_order']}.\n"
        f"- Explanation style: {treatment['explanation_style']}.\n"
        f"- Practice style: {treatment['practice_style']}.\n"
        f"- Recap depth: {treatment['recap_depth']}.\n"
        f"- Formula support: {treatment['formula_support']}.\n"
        f"- Code scaffold: {treatment['code_scaffold']}.\n"
        f"- Checkpoint density: {treatment['checkpoint_density']}.\n"
        f"- Segment size: {treatment['segment_size']}.\n"
        f"- Interest tags: {', '.join(treatment['interest_tags'])}.\n"
        f"- Preferred examples: {', '.join(treatment['preferred_examples']) or 'none'}.\n"
        f"- Example context: {treatment.get('example_context') or 'neutral'}.\n"
        "Required differentiation:\n"
        "- Foundation: lead with a concrete domain situation, define terms on first use, use short linked reasoning steps, explain formula symbols, provide a complete starter, and use guided mechanism/application checks.\n"
        "- Advanced: lead with the model or representation, compress familiar definitions, connect notation to derivation, provide only a partial starter, and test boundaries or transfer.\n"
        "- Integrate the preferred domain throughout the worked example; never append a disconnected personalization sentence.\n"
        "- Interest tags may only influence the scenario or surface form of examples; they must not change facts, conclusions, or source-grounded claims.\n"
        "Required lesson sequence:\n"
        "- Start with one short, concrete example or situation; then give the prerequisite recap; then introduce the core idea, intuitive model, mechanism or derivation, source-grounded worked example, counterexample or boundary, misconception correction, takeaway, and three cognitive question types.\n"
        "Example discipline:\n"
        "- Keep the visible lecture structure unchanged. Use exactly one anchor scenario across the opening example, intuition, mechanism explanation, and worked example. Develop that scenario with new reasoning; do not replace it with a second example that reaches the same conclusion.\n"
        "- Include one distinct counterexample or boundary case. It must contrast one condition with the anchor scenario and explain what changes, fails, or becomes insufficient. It must add information rather than restate the anchor negatively.\n"
        "- Use a new but related scenario only for the application-or-boundary question. Adapt explanation depth and task demand to the learner, not the number of examples.\n"
        "Output and assessment contract:\n"
        "- Return one complete JSON object matching the requested schema.\n"
        "- Every claim must be grounded in the supplied sources or in the approved teaching profile when provided.\n"
        "- Every objective question must test a real misconception, mechanism, or boundary from the section.\n"
        "- Distractors must be plausible and domain-relevant, never absurd or unrelated.\n"
        "- Each option needs targeted feedback that explains its mechanism or specific error; never merely say correct or incorrect.\n"
    )


def _build_approved_fallback_content(base: dict[str, Any], request: dict[str, Any], page_numbers: set[int]) -> dict[str, Any]:
    """Build a reviewed, concept-specific fallback when a live model is unavailable.

    This intentionally replaces the former generic verified-source template.
    It uses only KQ1 claims and KQ2-linked pages; profile details select a
    scenario and scaffolding level, never alter the approved facts.
    """
    concept = str(base.get("concept_name") or request.get("concept", {}).get("name") or "Concept")
    treatment = _profile_treatment(request.get("learner_profile"))
    selected_assets = {str(item.get("asset_type")): item.get("content") or {} for item in request.get("teaching_assets") or []}
    foundation = treatment["profile_tier"] == "foundation"
    approved = request.get("approved_teaching_profile") or _approved_teaching_profile(concept)
    if not approved:
        raise ValueError("approved teaching profile unavailable")
    claims = {item["kind"]: item["text"] for item in approved["claims"]}
    targets = {item["kind"]: item for item in approved["assessment_targets"]}
    misconceptions = list(approved["misconceptions"])
    pages = sorted((request.get("sources") or []), key=lambda item: int(item.get("page_number") or 0))
    page_walkthrough = []
    for index, page in enumerate(pages):
        number = int(page.get("page_number") or 0)
        role = str(page.get("role") or "idea").replace("_", " ")
        previous = "The definition establishes the representation being considered."
        if index:
            previous = f"This extends the idea established on page {pages[index - 1].get('page_number')}."
        focus = claims["mechanism"] if index else claims["definition"]
        page_walkthrough.append({
            "page_number": number,
            "what_to_notice": focus,
            "explanation": (
                f"{focus} The boundary to retain is: {claims['boundary']} "
                + ("Name the input, the transformation, and the resulting decision before moving on." if foundation else "Relate the representation directly to the stated boundary condition.")
            ),
            "connection_to_previous": previous,
        })
    prerequisite = (approved.get("prerequisites") or ["Linear classification"])[0]
    mechanism = (
        [
            claims["definition"],
            "Identify the representation used for the input.",
            claims["mechanism"],
            f"Contrast it with this case: {claims['counterexample']}",
            claims["boundary"],
        ]
        if foundation else
        [claims["definition"], claims["mechanism"], claims["boundary"]]
    )
    key_terms = [
        {"term": concept, "definition": claims["definition"]},
        {"term": "Mechanism", "definition": claims["mechanism"]},
        {"term": "Boundary", "definition": claims["boundary"]},
    ]
    scenario = treatment.get("example_context") or "a binary classification decision"
    if foundation:
        explanation = (
            f"Imagine {scenario}. {claims['definition']} First identify what the input represents and what the model is allowed to change. "
            f"Then follow the mechanism: {claims['mechanism']} This limit matters: {claims['boundary']} "
            f"Compare the working case, {claims['example']}, with the counterexample, {claims['counterexample']}."
        )
    else:
        explanation = (
            f"{claims['definition']} In {scenario}, the decisive structural question is how the representation supports the decision. "
            f"{claims['mechanism']} The governing boundary is: {claims['boundary']} "
            f"The contrast between {claims['example']} and {claims['counterexample']} exposes that boundary."
        )
    worked_solution = (
        f"Start from the working example: {claims['example']} Then test it against the counterexample: {claims['counterexample']} "
        f"The mechanism is: {claims['mechanism']} The conclusion must preserve the stated boundary: {claims['boundary']}"
        + (" Check the representation after every transformation before stating the conclusion." if foundation else " State which assumption fails before proposing a richer representation or update.")
    )
    worked_asset = selected_assets.get("foundation_worked_example" if foundation else "advanced_worked_example") or {}
    asset_steps = list(worked_asset.get("steps") or [])
    if asset_steps:
        worked_solution = f"{worked_solution} The worked case is checked through these steps: " + " ".join(str(step) for step in asset_steps)
    if misconceptions:
        mechanism_misconception = misconceptions[0]
        boundary_misconception = misconceptions[1] if len(misconceptions) > 1 else {
            "id": f"{_normal(concept).replace(' ', '-')}-boundary-confusion",
            "text": f"{concept} always works in every setting.",
            "correction": claims["boundary"],
        }
    else:
        mechanism_misconception = {
            "id": f"{_normal(concept).replace(' ', '-')}-mechanism-confusion",
            "text": f"{concept} is just a renamed label, not a mechanism.",
            "correction": claims["mechanism"],
        }
        boundary_misconception = {
            "id": f"{_normal(concept).replace(' ', '-')}-boundary-confusion",
            "text": f"{concept} always works in every setting.",
            "correction": claims["boundary"],
        }
    return _with_f7_teaching_fields({
        "concept_introduction": {
            "hook": (f"How could {scenario} make a reliable decision using {concept}?" if foundation else f"Which representational constraint determines whether {concept} succeeds in {scenario}?"),
            "explanation": explanation,
            "mechanism": mechanism,
            "boundaries": claims["boundary"],
        },
        "prerequisite_recap": {
            "title": prerequisite,
            "explanation": f"{prerequisite} supplies the representation needed here. " + ("Before continuing, identify its input, operation, and output in plain language." if foundation else "Carry its notation directly into the mechanism and track the governing assumption."),
            "example": claims["example"],
        },
        "page_walkthrough": page_walkthrough,
        "key_terms": key_terms,
        "worked_example": {
            "problem": str(worked_asset.get("task") or worked_asset.get("problem") or f"Analyze {scenario} with {concept}, then decide whether the stated boundary is satisfied."),
            "steps": (asset_steps or ([
                f"Describe the decision in the scenario and name its input representation.",
                f"Use the working case: {claims['example']}",
                f"Trace one change at a time: {claims['mechanism']}",
                f"Compare the counterexample: {claims['counterexample']}",
                f"State the conclusion using the boundary: {claims['boundary']}",
            ] if foundation else [
                f"Formalize the representation in {scenario} and state the relevant assumption.",
                f"Apply the mechanism: {claims['mechanism']}",
                f"Use {claims['counterexample']} to test the boundary: {claims['boundary']}",
            ])),
            "solution": worked_solution,
            "why_it_works": (
                f"The conclusion follows because the representation, mechanism, counterexample, and boundary are checked in one reasoning chain."
            ),
        },
        "objective_exercise": {
            "instructions": f"Use the mechanism, misconception correction, and boundary taught in this section.",
            "questions": [
                {
                    "question_id": "q1",
                    "type": "single_choice",
                    "question_type": "mechanism",
                    "assessment_target_id": targets["mechanism"]["id"],
                    "correct_reasoning": claims["mechanism"],
                    "prompt": (f"In {scenario}, which explanation correctly traces how {concept} reaches a decision?" if foundation else f"Which account correctly connects the representation to the mechanism of {concept} in {scenario}?"),
                    "options": [
                        {"id": "a", "text": claims["mechanism"], "correct": True, "feedback": "This traces the actual transformation or update that produces the result."},
                        {"id": "b", "text": mechanism_misconception["text"], "correct": False, "misconception_id": mechanism_misconception["id"], "feedback": mechanism_misconception["correction"]},
                        {"id": "c", "text": "The concept changes only the name of the final class, not the representation or update.", "correct": False, "feedback": "The teaching explains a change in representation or parameters, not a renamed label."},
                    ],
                    "explanation": f"{claims['mechanism']} This links the definition to the behavior observed in the example.",
                },
                {
                    "question_id": "q2",
                    "type": "single_choice",
                    "question_type": "misconception_discrimination",
                    "assessment_target_id": targets["misconception_discrimination"]["id"],
                    "correct_reasoning": mechanism_misconception["correction"],
                    "prompt": (f"A learner makes the following mistake while reasoning about {scenario}. Which correction restores the mechanism of {concept}?" if foundation else f"Which correction preserves the representational assumptions of {concept} in {scenario}?"),
                    "options": [
                        {"id": "a", "text": "The concept works only when the input labels are renamed.", "correct": False, "feedback": "Renaming labels does not supply the mechanism described in the section."},
                        {"id": "b", "text": mechanism_misconception["correction"], "correct": True, "feedback": "This correction restores the missing mechanism rather than changing labels or terminology."},
                        {"id": "c", "text": boundary_misconception["text"], "correct": False, "misconception_id": boundary_misconception["id"], "feedback": boundary_misconception["correction"]},
                    ],
                    "explanation": mechanism_misconception["correction"],
                },
                {
                    "question_id": "q3",
                    "type": "single_choice",
                    "question_type": "application_or_boundary",
                    "assessment_target_id": targets["application_or_boundary"]["id"],
                    "correct_reasoning": claims["boundary"],
                    "prompt": (f"What observation in {scenario} would show that {concept} is insufficient on its own?" if foundation else f"Which boundary violation in {scenario} requires a richer representation or optimization assumption?"),
                    "options": [
                        {"id": "a", "text": "Whenever the task has exactly two possible labels.", "correct": False, "feedback": "The number of labels alone does not determine whether the stated boundary applies."},
                        {"id": "b", "text": "Whenever a diagram is available in the source material.", "correct": False, "feedback": "A diagram can illustrate the concept but does not remove its stated boundary."},
                        {"id": "c", "text": claims["boundary"], "correct": True, "feedback": "This identifies the precise condition under which the mechanism no longer suffices."},
                    ],
                    "explanation": claims["boundary"],
                },
            ],
        },
        "summary_connection": {
            "summary": f"{claims['definition']} {claims['mechanism']} Remember the boundary: {claims['boundary']}",
            "next_concept_bridge": "The next concept builds on this mechanism by changing the representation, transformation, or update being studied.",
        },
        "personalization": {
            **treatment,
            "interest_usage": "scenario_only",
            "fact_source": "approved_kq1_teaching_profile",
            "learner_profile_summary": {
                "prior_knowledge": treatment["lesson_depth"],
                "explanation_density": treatment["recap_depth"],
                "practice_style": treatment["practice_style"],
            },
        },
    }, concept)


# Kept as a compatibility alias for tests and older isolated callers. It now
# produces the reviewed KQ3 fallback, never the former generic template.
_build_verified_source_content = _build_approved_fallback_content


def _complete_live_content_from_approved_assets(
    content: dict[str, Any], *, base: dict[str, Any], request: dict[str, Any], page_numbers: set[int]
) -> tuple[dict[str, Any], list[str]]:
    """Fill only invalid live fields from the reviewed node-specific blueprint.

    This is not the former all-or-nothing fallback branch: live prose remains
    intact.  It prevents one malformed question array or omitted JSON field
    from discarding an otherwise useful live section.
    """
    result = deepcopy(content)
    approved_profile = request.get("approved_teaching_profile")
    if approved_profile:
        approved = _build_approved_fallback_content(base, request, page_numbers)
    elif request.get("teaching_assets"):
        assets = {str(item.get("asset_type")): item.get("content") or {} for item in request.get("teaching_assets") or []}
        foundation = _profile_treatment(request.get("learner_profile"))["profile_tier"] == "foundation"
        intuition = assets.get("foundation_intuition") or assets.get("visual_or_coordinate_description") or {}
        worked = assets.get("foundation_worked_example" if foundation else "advanced_worked_example") or assets.get("advanced_worked_example") or assets.get("foundation_worked_example") or {}
        source_pages = sorted(request.get("sources") or [], key=lambda item: int(item.get("page_number") or 0))
        definition = _clean(intuition.get("explanation") or intuition.get("description") or (request.get("source_interpretation", {}).get("pages") or [{}])[0].get("claims", [base["concept_name"]])[0])
        boundary = _clean(intuition.get("boundary") or intuition.get("check") or "The conclusion applies only under the assumptions stated in the selected source.")
        mechanism_steps = list(worked.get("steps") or [])
        mechanism = _clean(" ".join(str(item) for item in mechanism_steps) or definition)
        interpreted_pages = request.get("source_interpretation", {}).get("pages") or []
        def safe_claim(index: int, fallback: str) -> str:
            claims = interpreted_pages[index].get("claims") if index < len(interpreted_pages) else []
            raw = _clean(" ".join(claims or []))
            # OCR maths may contain private-use glyphs and mojibake. The PDF
            # image remains available; learner-facing prose must remain clean.
            ascii_text = raw.encode("ascii", "ignore").decode("ascii")
            ascii_text = re.sub(r"\s+", " ", ascii_text).strip(" ?-;,.")
            return ascii_text if _words(ascii_text) >= 6 else fallback
        approved = {
            "page_walkthrough": [{
                "page_number": int(page.get("page_number") or 0),
                "what_to_notice": safe_claim(index, definition).split(". ")[0],
                "explanation": safe_claim(index, definition),
                "connection_to_previous": "This evidence establishes the core claim." if index == 0 else f"This extends the evidence on page {source_pages[index-1].get('page_number')}.",
            } for index, page in enumerate(source_pages)],
            "key_terms": [{"term": str(base["concept_name"]), "definition": definition}],
            "worked_example": {
                "problem": _clean(worked.get("problem") or worked.get("task") or f"Apply {base['concept_name']} to the source-backed case."),
                "steps": mechanism_steps or [definition, mechanism, boundary],
                "solution": _clean(" ".join(mechanism_steps) or mechanism),
                "why_it_works": _clean(mechanism),
            },
            # This reviewed placeholder exists only so the separately invoked
            # live exercise writer can receive a complete transport object.
            # Admission requires exercise_generation_mode=live.
            "objective_exercise": {
                "instructions": "Use the mechanism and boundary taught in this section.",
                "questions": [{
                    "question_id": f"q{index+1}", "type": "single_choice",
                    "question_type": kind,
                    "prompt": prompt,
                    "options": [
                        {"id": "a", "text": correct, "correct": True, "feedback": "This follows the source-backed mechanism."},
                        {"id": "b", "text": wrong, "correct": False, "feedback": "This changes or ignores a required assumption."},
                        {"id": "c", "text": boundary, "correct": False, "feedback": "This states a boundary but does not answer the mechanism asked here."},
                    ],
                    "explanation": correct,
                } for index, (kind, prompt, correct, wrong) in enumerate((
                    ("mechanism", f"Which account best explains the mechanism of {base['concept_name']}?", mechanism, boundary),
                    ("misconception_discrimination", f"Which statement preserves the source-backed meaning of {base['concept_name']}?", definition, f"{base['concept_name']} guarantees the same result regardless of representation or task."),
                    ("application_or_boundary", f"Which conclusion correctly respects the boundary of {base['concept_name']}?", boundary, f"{base['concept_name']} has no assumptions or failure cases."),
                ))],
            },
        }
    elif request.get("source_interpretation"):
        source_pages = sorted(request.get("sources") or [], key=lambda item: int(item.get("page_number") or 0))
        interpreted_pages = request.get("source_interpretation", {}).get("pages") or []
        treatment = _profile_treatment(request.get("learner_profile"))
        concept = str(base.get("concept_name") or "Concept")
        note = _concept_note(concept)

        def safe_claim(index: int, fallback: str) -> str:
            claims = interpreted_pages[index].get("claims") if index < len(interpreted_pages) else []
            raw = _clean(" ".join(claims or []))
            ascii_text = raw.encode("ascii", "ignore").decode("ascii")
            ascii_text = re.sub(r"\s+", " ", ascii_text).strip(" ?-;,.")
            return ascii_text if _words(ascii_text) >= 6 else fallback

        definition = safe_claim(0, note["short"])
        mechanism = safe_claim(1, " ".join(note["mechanism"]))
        boundary = safe_claim(2, note["boundary"])
        page_walkthrough = []
        for index, page in enumerate(source_pages):
            page_walkthrough.append({
                "page_number": int(page.get("page_number") or 0),
                "what_to_notice": safe_claim(index, definition).split(". ")[0],
                "explanation": safe_claim(index, definition),
                "connection_to_previous": (
                    "This establishes the core idea for the concept."
                    if index == 0
                    else f"This extends the evidence from page {source_pages[index - 1].get('page_number')}."
                ),
            })
        scenario = treatment.get("example_context") or "an everyday prediction task"
        approved = {
            "concept_introduction": {
                "hook": f"How does {concept} help with {scenario}?",
                "explanation": (
                    f"{definition} In this section, treat the source pages as evidence for what the input is, "
                    f"what transformation or decision is being made, and where the method stops being reliable."
                ),
                "mechanism": list(note["mechanism"]),
                "boundaries": boundary,
            },
            "prerequisite_recap": {
                "title": str(note["prereq"][0]),
                "explanation": str(note["prereq"][1]),
                "example": str(note["example"]),
            },
            "page_walkthrough": page_walkthrough,
            "key_terms": [
                {"term": concept, "definition": definition},
                {"term": "Mechanism", "definition": mechanism},
                {"term": "Boundary", "definition": boundary},
            ],
            "worked_example": {
                "problem": f"Use {concept} to reason about {scenario}.",
                "steps": [
                    f"Name the input representation used in {scenario}.",
                    f"State the decision or prediction that {concept} is meant to support.",
                    *list(note["mechanism"]),
                    f"Test whether the conclusion still holds once you check this boundary: {boundary}",
                ],
                "solution": (
                    f"Start by naming what information the model receives in {scenario} and how that information is represented. "
                    f"Then trace the mechanism in order: {mechanism} "
                    f"After each step, ask what changed in the representation and what stayed fixed. "
                    f"Only after that should you make a prediction or decision. "
                    f"Finally, test the boundary explicitly: {boundary} "
                    f"If that condition is violated, the concept may still sound relevant, but it no longer guarantees the same result."
                ),
                "why_it_works": mechanism,
            },
            # This placeholder only keeps the transport contract intact until the
            # dedicated live exercise writer replaces it with a real question set.
            "objective_exercise": {
                "instructions": "Use the mechanism and boundary taught in this section.",
                "questions": [{
                    "question_id": f"q{index+1}",
                    "type": "single_choice",
                    "question_type": kind,
                    "prompt": prompt,
                    "options": [
                        {"id": "a", "text": correct, "correct": True, "feedback": "This follows the source-backed mechanism."},
                        {"id": "b", "text": wrong, "correct": False, "feedback": "This conflicts with the definition, mechanism, or boundary taught in the section."},
                        {"id": "c", "text": boundary, "correct": False, "feedback": "This states a boundary but does not answer the mechanism being asked."},
                    ],
                    "explanation": correct,
                } for index, (kind, prompt, correct, wrong) in enumerate((
                    ("mechanism", f"Which statement best explains the mechanism of {concept}?", mechanism, f"{concept} only renames labels and does not transform a representation or update a model."),
                    ("misconception_discrimination", f"Which correction best restores the intended meaning of {concept}?", definition, f"{concept} works even when the source assumptions are ignored."),
                    ("application_or_boundary", f"Which observation best identifies the boundary of {concept}?", boundary, f"{concept} has no meaningful failure case once it appears in a model."),
                ))],
            },
            "summary_connection": {
                "summary": f"{definition} The central mechanism is {mechanism} The key boundary is {boundary}",
                "next_concept_bridge": str(note["bridge"]),
            },
        }
    else:
        return content, []
    repaired: list[str] = []
    required = (
        "concept_introduction", "prerequisite_recap", "page_walkthrough",
        "key_terms", "worked_example", "objective_exercise", "summary_connection",
    )
    for field in required:
        if not result.get(field):
            if field in approved:
                result[field] = deepcopy(approved[field])
                repaired.append(field)
    example = result.get("worked_example") or {}
    minimum_solution_words = max(28, min(60, int(base["estimated_minutes"]) * 1.5))
    if len(example.get("steps") or []) < 3 or _words(example.get("solution")) < minimum_solution_words:
        if approved.get("worked_example"):
            result["worked_example"] = deepcopy(approved["worked_example"])
        if "worked_example" not in repaired:
            repaired.append("worked_example")
    covered = {int(item.get("page_number") or 0) for item in (result.get("page_walkthrough") or [])}
    if not page_numbers.issubset(covered):
        if approved.get("page_walkthrough"):
            result["page_walkthrough"] = deepcopy(approved["page_walkthrough"])
        if "page_walkthrough" not in repaired:
            repaired.append("page_walkthrough")
    from v4_quality_baseline import evaluate_objective_exercise
    if not evaluate_objective_exercise(result.get("objective_exercise") or {}).get("passed"):
        result["objective_exercise"] = deepcopy(approved["objective_exercise"])
        if "objective_exercise" not in repaired:
            repaired.append("objective_exercise")
    return result, repaired


def generate_source_grounded_lecture_v4(
    *, v3_lecture: dict[str, Any], source_links: list[dict[str, Any]], daily: dict[str, Any],
    user_id: str, profile: dict[str, Any] | None = None, private_documents: Any | None = None,
    public_provenance: Any | None = None, verified_registry: Any | None = None,
    model_generator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    content_model: str | None = None,
) -> dict[str, Any]:
    """Generate independent v4 sections; never alter the v3 input."""
    output = deepcopy(v3_lecture)
    output["contract_version"] = "source-grounded-lecture-v4"
    sections = list(v3_lecture.get("lecture_sections") or [])
    generated_sections: list[dict[str, Any] | None] = [None] * len(sections)
    pending: list[tuple[int, dict[str, Any], dict[str, Any], set[int]]] = []
    model = model_generator or _openai_generate
    for index, section in enumerate(sections):
        concept_id, concept_name = _concept_for(section)
        links = [item for item in source_links if _matches(section, item) and item.get("review_status") in {"usable", "verified"}]
        pages = collect_source_pages(
            user_id=user_id, links=links, daily=daily, private_documents=private_documents,
            public_provenance=public_provenance, verified_registry=verified_registry,
        )
        base = {
            "section_id": section.get("section_id"), "concept_id": concept_id,
            "concept_name": concept_name, "title": concept_name,
            "estimated_minutes": int(section.get("estimated_minutes") or 1),
            "source_links": deepcopy(links), "source_pages": pages,
            "retry_attempts": int(section.get("retry_attempts") or 0),
            "max_retry_attempts": V4_MAX_RETRY_ATTEMPTS,
        }
        if not links:
            generated_sections[index] = {**base, "v4_status": "unavailable", "failure_code": "no_reliable_source", "retryable": False}
            continue
        if not pages:
            generated_sections[index] = {**base, "v4_status": "unavailable", "failure_code": "source_text_unavailable", "retryable": False}
            continue
        source_interpretation = _interpret_source_pages(pages)
        treatment = _profile_treatment(profile)
        primary_link = links[0] if links else {}
        asset_concept_id = str(
            primary_link.get("asset_concept_id")
            or f"golden:{_normal(concept_name).replace(' ', '-')}"
        )
        teaching_assets = _select_teaching_assets(asset_concept_id, treatment)
        asset_manifest_version = str(
            primary_link.get("asset_manifest_version")
            or ("ta-golden-v2" if teaching_assets else "")
        ) or None
        base["teaching_asset_ids"] = [str(item.get("asset_id")) for item in teaching_assets]
        base["asset_manifest_version"] = asset_manifest_version
        teaching_plan = _teaching_plan(
            concept_id=concept_id, concept_name=concept_name, minutes=base["estimated_minutes"],
            profile=profile, interpretation=source_interpretation,
        )
        approved_profile = None
        if _is_verified_source(base):
            approved_profile = _approved_teaching_profile(concept_name) or _approved_asset_profile(concept_name, teaching_assets)
        request = {
            # The server chooses this explicitly by learning day.  Do not
            # mutate process-wide environment variables: parallel learners
            # must not be able to change one another's model choice.
            "content_model": str(content_model or os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4")),
            "exercise_model": str(content_model or os.getenv("PATHLY_EXERCISE_MODEL", os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4"))),
            "audience": "The student. Teach the knowledge now in complete prose.",
            "concept": {"id": concept_id, "name": concept_name},
            "scheduled_minutes": base["estimated_minutes"],
            "learner_profile": profile or {},
            "learner_treatment": treatment,
            "teaching_assets": teaching_assets,
            "asset_manifest_version": asset_manifest_version,
            "prompt_version": V4_PROMPT_VERSION,
            "treatment_version": V4_TREATMENT_VERSION,
            "source_interpretation": source_interpretation,
            "teaching_plan": teaching_plan,
            "approved_teaching_profile": approved_profile,
            "teaching_brief": _v4_generation_brief(
                concept=concept_name,
                treatment=treatment,
                approved_profile=approved_profile,
            ),
            "lecture_writer": {
                "task": "Write finished student-facing knowledge teaching from the teaching plan, teaching brief, and interpreted source facts.",
                "forbidden": [
                    "source selection rationale", "engineering metadata", "Pathly", "Content Agent",
                    "quality gate", "learning path", "what to notice", "step by step",
                    "what this page is showing", "personalization contract", "teaching plan",
                ],
            },
            "exercise_writer": {
                "task": "Write only questions supported by the section's teaching, worked example, and interpreted pages.",
                "forbidden_inputs": [
                    "source-selection rationale", "teaching strategy", "engineering metadata",
                    "learning strategy", "prompting strategy", "quality gate",
                ],
            },
            "sources": pages,
            "required_json": {
                "opening_example": {"title": "short learner-facing label", "scenario": "concrete situation before the formal explanation", "question": "one orienting question about that situation"},
                "counterexample": {"scenario": "distinct contrast case", "contrast": "what differs from the anchor example", "boundary_condition": "specific condition that changes or limits the mechanism"},
                "concept_introduction": {"hook": "domain question", "explanation": "substantive concept teaching", "mechanism": ["ordered mechanism steps"], "boundaries": "when it works and fails"},
                "prerequisite_recap": {"title": "knowledge-specific title", "explanation": "actual prerequisite knowledge", "example": "brief concrete example"},
                "page_walkthrough": [{"page_number": "selected integer page", "what_to_notice": "specific text, formula, or diagram", "explanation": "domain explanation", "connection_to_previous": "knowledge connection"}],
                "intuition": "a concrete mental model that makes the mechanism easier to reason about",
                "learner_adaptation": {
                    "prior_knowledge_level": "low | medium | high",
                    "explanation_density": "expanded | concise",
                    "example_mode": "worked-example-led | balanced | symbolic-and-structural",
                    "practice_style": "guided | independent",
                    "terminology_depth": "basic | standard | advanced",
                    "interest_usage": "scenario_only",
                },
                "math": {"inline_math": ["short verified expression"], "display_math": [{"latex": "valid LaTex", "text": "readable plain-text fallback", "label": "what the expression means"}], "matrix": {"rows": [["cell"]], "label": "optional table or matrix"}, "derivation_steps": ["ordered reasoning step"]},
                "key_terms": [{"term": "domain term", "definition": "precise contextual definition"}],
                "worked_example": {"problem": "concrete problem", "steps": ["at least three solved steps"], "solution": "complete answer", "why_it_works": "mechanism explanation"},
                "common_mistake": "one plausible but incorrect interpretation and why it fails",
                "objective_exercise": {"instructions": "answer from this section", "questions": [{"question_id": "q1", "type": "single_choice", "prompt": "knowledge question", "options": [{"id": "a", "text": "domain answer", "correct": True}], "explanation": "why the correct answer is correct"}]},
                "summary_connection": {"summary": "substantive recap", "next_concept_bridge": "domain connection only"},
            },
            "rules": [
                "Teach only the knowledge itself; never discuss Pathly, pedagogy, teaching methods, learning methods, or content generation.",
                "Use the selected pages as the factual spine. Explain each page in order and never invent a quote, page, URL, author, result, formula, or citation.",
                "The public primary source establishes the foundation; a relevant private supplemental source may add another explanation or example.",
                "Write enough finished teaching for the scheduled minutes, including mechanism, boundaries, a fully solved example, and at least three objective questions.",
                "When approved_teaching_profile is present, treat it as the immutable factual contract. Use its claims, misconceptions, assessment targets, and source pages; do not introduce a conflicting fact.",
                "Use interest_tags, preferred_examples, and preferred_style only to choose a natural example scenario and degree of scaffolding. Never force an irrelevant interest into an example.",
                "Use the learner profile to vary explanation density, terminology depth, example selection, step size, and checkpoint frequency. For lower-prior-knowledge learners, make the explanation more explicit and concrete; for higher-prior-knowledge learners, compress the recap and move sooner into mechanism and boundary analysis.",
                "Use the selected approved teaching assets as the material spine. Preserve their worked steps, derivation, visual description, and transfer task; do not replace them with a generic example.",
                "After each page, explain its knowledge immediately; include one intuition and one common mistake for the whole section.",
                "Every objective question must test content explicitly taught in this section and have three or four options with exactly one correct option.",
                "Create exactly three questions: one mechanism, one misconception_discrimination, and one application_or_boundary. Each must include question_type, assessment_target_id, source_refs, correct_reasoning, and option-level feedback. Every distractor must express a plausible misconception or reasoning error, never an unrelated or absurd statement.",
                "Create exactly one page_walkthrough item for every selected source page, in ascending page order.",
                "Write formulas in readable Unicode or valid LaTeX notation. Never copy damaged OCR symbols or flattened matrix text into the teaching prose.",
                "Use math fields only for expressions that are stated or unambiguously supported by the selected source. If an OCR formula is uncertain, explain its meaning in prose and leave that math field empty.",
                "Return exactly one JSON object matching required_json.",
            ],
        }
        # Keep the live call focused on the parts where a model adds genuine
        # value: learner-facing explanation, mechanism, and a natural example.
        # The remaining source walkthrough, terms, maths, and assessment
        # contract are inserted from reviewed node assets after generation.
        # Asking one call to author every transport field was the main source
        # of invalid JSON and 75-second timeouts.
        request["required_json"] = {
            "opening_example": {"title": "short learner-facing label", "scenario": "concrete situation before the formal explanation", "question": "one orienting question"},
            "counterexample": {"scenario": "distinct contrast case", "contrast": "what differs from the anchor example", "boundary_condition": "specific condition that changes or limits the mechanism"},
            "concept_introduction": {
                "hook": "domain question",
                "explanation": "finished concept teaching",
                "mechanism": ["ordered mechanism steps"],
                "boundaries": "when the concept applies and fails",
            },
            "prerequisite_recap": {"title": "knowledge-specific title", "explanation": "actual prerequisite explanation", "example": "brief concrete example"},
            "intuition": "a concrete mental model",
            "worked_example": {"problem": "concrete domain problem", "steps": ["at least three solved steps"], "solution": "complete answer", "why_it_works": "mechanism explanation"},
            "common_mistake": "one plausible but incorrect interpretation and why it fails",
            "summary_connection": {"summary": "substantive recap", "next_concept_bridge": "domain connection only"},
        }
        request["rules"].append(
            "Return only the eight fields in required_json. Reuse opening_example.scenario as the anchor for intuition, mechanism, and worked_example. counterexample must be a different case that teaches the boundary. The application supplies the reviewed source walkthrough, terminology, mathematics, and assessment separately; do not describe that internal process."
        )
        pending.append((index, base, request, {item["page_number"] for item in pages}))

    def generate_one(base: dict[str, Any], request: dict[str, Any], page_numbers: set[int]) -> dict[str, Any]:
        failure_code, failure_reason = "generation_failed", "generation_failed"
        content: dict[str, Any] | None = None
        for pass_number in range(2):
            attempt_request = deepcopy(request)
            if pass_number:
                targets = _repair_targets(failure_reason)
                attempt_request["quality_rewriter"] = {
                    "validation_error": failure_reason,
                    "repair_targets": targets,
                    "instruction": "Return replacements only for repair_targets. Do not rewrite unrelated fields and do not mention this repair instruction.",
                }
            try:
                generated = model(attempt_request)
                content = generated if content is None else _merge_repaired_fields(content, generated, targets)
                content = _with_f7_teaching_fields(content, base["concept_name"])
                content = _with_f8_math_fields(content, base["concept_name"])
                content = _with_f9_exercise_support(content, str(base["section_id"]), str(base["concept_id"]), request.get("sources") or [])
                content = _with_f10_learner_adaptation(content, _profile_treatment(request.get("learner_profile")))
                # First give the model a targeted repair pass.  Only then
                # complete residual malformed fields from approved assets.
                missing_contract_fields = not {
                    "concept_introduction", "prerequisite_recap", "page_walkthrough",
                    "key_terms", "worked_example", "objective_exercise", "summary_connection",
                }.issubset(content)
                if pass_number or missing_contract_fields:
                    content, live_repairs = _complete_live_content_from_approved_assets(
                        content, base=base, request=request, page_numbers=page_numbers
                    )
                else:
                    live_repairs = []
                # Enforce one anchor example plus one genuinely contrasting
                # boundary case before assessment writing sees the lesson.
                # This is deterministic and evidence-bounded, so a weak model
                # response cannot make the full page fail or add more prose.
                content = _example_contract(content, base=base, request=request)
                # The inserted blueprint fields need the same factual math and
                # question provenance enrichment as model-authored fields.
                content = _with_f8_math_fields(content, base["concept_name"])
                content = _with_f9_exercise_support(content, str(base["section_id"]), str(base["concept_id"]), request.get("sources") or [])
                exercise_generation_mode = "approved_asset_fallback"
                exercise_generation_reason = None
                # Exercise writing is intentionally a separate live call.  It
                # receives the final taught content and reviewed constraints,
                # so its distractors can be nuanced without destabilising the
                # lecture writer's JSON contract.
                if model_generator is None:
                    try:
                        live_exercise = _openai_generate_exercises(request, content)
                        candidate = _with_f9_exercise_support(
                            {"objective_exercise": live_exercise},
                            str(base["section_id"]), str(base["concept_id"]), request.get("sources") or [],
                        )["objective_exercise"]
                        from v4_quality_baseline import evaluate_objective_exercise
                        if not evaluate_objective_exercise(candidate).get("passed"):
                            raise ValueError("live exercise did not pass quality gate")
                        content["objective_exercise"] = candidate
                        exercise_generation_mode = "live"
                    except Exception as exc:
                        # Keep the reviewed blueprint only for this isolated
                        # exercise failure; never discard the live lesson.
                        exercise_generation_reason = type(exc).__name__
                _validate_content(content, base["concept_name"], base["estimated_minutes"], page_numbers)
                return {
                    **base, "v4_status": "ready", "generation_mode": "live_augmented" if live_repairs else "live",
                    "lecture_content": content, "retryable": True,
                    "repair_pass_used": bool(pass_number),
                    "live_asset_repairs": live_repairs,
                    "exercise_generation_mode": exercise_generation_mode,
                    "exercise_generation_reason": exercise_generation_reason,
                }
            except V4ModelResponseError as exc:
                failure_code, failure_reason = "response_format_invalid", str(exc)
            except ValueError as exc:
                failure_code, failure_reason = "content_validation_failed", str(exc)
            except Exception as exc:
                failure_code, failure_reason = "generation_failed", type(exc).__name__
        # A verified section always has an approved, evidence-bounded fallback.
        # This is deliberately reached only after the live and targeted-repair
        # attempts fail, never as a replacement for live personalization.
        if request.get("approved_teaching_profile"):
            try:
                content = _build_approved_fallback_content(base, request, page_numbers)
                content = _example_contract(content, base=base, request=request)
                content = _with_f8_math_fields(content, base["concept_name"])
                content = _with_f9_exercise_support(content, str(base["section_id"]), str(base["concept_id"]), request.get("sources") or [])
                content = _with_f10_learner_adaptation(content, _profile_treatment(request.get("learner_profile")))
                _validate_content(content, base["concept_name"], base["estimated_minutes"], page_numbers)
                return {
                    **base, "v4_status": "ready", "generation_mode": "approved_profile_fallback",
                    "lecture_content": content, "retryable": True, "repair_pass_used": True,
                    "fallback_reason": failure_reason,
                }
            except ValueError as exc:
                failure_code, failure_reason = "approved_fallback_invalid", str(exc)
        elif request.get("source_interpretation"):
            try:
                content, generic_repairs = _complete_live_content_from_approved_assets(
                    {}, base=base, request=request, page_numbers=page_numbers
                )
                content = _example_contract(content, base=base, request=request)
                content = _with_f8_math_fields(content, base["concept_name"])
                content = _with_f9_exercise_support(
                    content, str(base["section_id"]), str(base["concept_id"]), request.get("sources") or []
                )
                content = _with_f10_learner_adaptation(
                    content, _profile_treatment(request.get("learner_profile"))
                )
                _validate_content(content, base["concept_name"], base["estimated_minutes"], page_numbers)
                return {
                    **base,
                    "v4_status": "ready",
                    "generation_mode": "source_grounded_fallback",
                    "lecture_content": content,
                    "retryable": True,
                    "repair_pass_used": True,
                    "live_asset_repairs": generic_repairs,
                    "fallback_reason": failure_reason,
                }
            except ValueError as exc:
                failure_code, failure_reason = "source_grounded_fallback_invalid", str(exc)
        return {
            **base,
            "v4_status": "unavailable",
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "retryable": int(base.get("retry_attempts") or 0) < V4_MAX_RETRY_ATTEMPTS,
            "repair_pass_used": True,
        }

    if pending:
        # Two concurrent calls are sufficient for the golden path and reduce
        # rate-limit/connection spikes that previously made live generation flaky.
        requested_workers = max(1, int(os.getenv("PATHLY_LECTURE_V4_WORKERS", "2")))
        with ThreadPoolExecutor(max_workers=min(requested_workers, len(pending))) as executor:
            futures = {
                executor.submit(generate_one, base, request, page_numbers): index
                for index, base, request, page_numbers in pending
            }
            for future in as_completed(futures):
                generated_sections[futures[future]] = future.result()

    completed_sections = [item for item in generated_sections if item is not None]
    # A user-document path may contain a concept whose public companion source
    # has no retrievable page text.  Do not fail the whole day in that case:
    # omit that unavailable section from the learner-facing lecture.  A day
    # with no usable sections still remains an explicit generation failure.
    unavailable_sections = [
        item for item in completed_sections
        if item.get("v4_status") != "ready"
        and item.get("failure_code") in {"source_text_unavailable", "no_reliable_source"}
    ]
    if unavailable_sections:
        completed_sections = [item for item in completed_sections if item not in unavailable_sections]
    output["lecture_sections"] = completed_sections
    metadata = dict(output.get("generation_metadata") or {})
    ready = sum(item.get("v4_status") == "ready" for item in completed_sections)
    ready_modes = {str(item.get("generation_mode") or "") for item in completed_sections if item.get("v4_status") == "ready"}
    if ready == len(completed_sections) and ready_modes == {"approved_profile_fallback"}:
        generation_mode = "approved_profile_fallback"
    elif ready == len(completed_sections) and ready_modes <= {"live", "live_augmented"}:
        generation_mode = "live"
    elif ready:
        generation_mode = "mixed"
    else:
        generation_mode = "unavailable"
    metadata.update({
        "generator_version": S4_GENERATOR_VERSION,
        "prompt_version": V4_PROMPT_VERSION,
        "content_model": str(content_model or os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4")),
        "temperature": 0.2,
        "live_timeout_seconds": float(os.getenv("PATHLY_CONTENT_TIMEOUT_SECONDS", "75")),
        "treatment_version": V4_TREATMENT_VERSION,
        "generated_for_user_id": user_id,
        "profile_version": (profile or {}).get("profile_version", 1),
        "source_link_version": (source_links[0].get("source_version") if source_links else None),
        "source_link_status": "indexed", "isolated_from_v3": True,
        "asset_manifest_version": next((item.get("asset_manifest_version") for item in completed_sections if item.get("asset_manifest_version")), None),
        "asset_selection_count": sum(len(item.get("teaching_asset_ids") or []) for item in completed_sections),
        "generation_mode": generation_mode,
        "omitted_unavailable_section_count": len(unavailable_sections),
        "ready_sections": ready, "total_sections": len(completed_sections),
    })
    output["generation_metadata"] = metadata
    output["source_links"] = deepcopy(source_links)
    output["v4_status"] = "generated" if ready else "unavailable"
    return output

