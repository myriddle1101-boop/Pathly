"""KQ0 quality baseline for source-grounded V4 exercises.

This module is deliberately read-only: it records the learner-visible quality
bar before KQ1-KQ4 change the knowledge or generation pipeline.
"""
from __future__ import annotations

from typing import Any

from verified_golden_sources import GOLDEN_PATH


V4_QUALITY_BASELINE_VERSION = "dp0-dual-user-quality-baseline-v1"
REQUIRED_QUESTION_TYPES = {
    "mechanism", "misconception_discrimination", "application_or_boundary",
}

# These phrases describe the exact failure mode seen in the original verified
# deterministic questions. They are prohibited in learner-visible questions.
GENERIC_PROMPT_MARKERS = (
    "which statement best describes",
    "what is the first useful question to ask",
    "which statement is a real limitation",
)
NONSENSE_DISTRACTOR_MARKERS = (
    "unrelated model names",
    "unrelated topic has the longest name",
    "label or file name",
    "ignores the input representation",
    "skip its input",
    "always solves every task",
    "removes the need to define inputs and outputs",
)


NORMAL_PROFILE_FIXTURES = {
    "foundation_learner": {
        "user_id": "demo-foundation-learner",
        "display_name": "Foundation Learner",
        "profile_version": 2,
        "cognitive_traits": {
            "mathematical_ability": 2,
            "programming_ability": 2,
            "abstract_thinking": 2,
            "logical_reasoning": 2,
            "general_learning_foundation": 2,
        },
        "affective_defaults": {
            "learning_style": "example",
            "preferred_examples": ["daily_life"],
            "interest_tags": ["no_preference"],
            "pace_preference": "steady",
            "self_regulation": 2,
        },
        "path_context": {
            "target_familiarity": "never",
            "current_confidence": 2,
            "current_anxiety": 4,
            "path_style_override": "use_default",
        },
    },
    "advanced_learner": {
        "user_id": "demo-advanced-learner",
        "display_name": "Advanced Learner",
        "profile_version": 1,
        "cognitive_traits": {
            "mathematical_ability": 5,
            "programming_ability": 5,
            "abstract_thinking": 5,
            "logical_reasoning": 5,
            "general_learning_foundation": 4,
        },
        "affective_defaults": {
            "learning_style": "theory",
            "preferred_examples": ["research", "code"],
            "interest_tags": ["computer_vision"],
            "pace_preference": "intensive",
            "self_regulation": 4,
        },
        "path_context": {
            "target_familiarity": "applied",
            "current_confidence": 5,
            "current_anxiety": 2,
            "path_style_override": "use_default",
        },
    },
}

CONTROLLED_DUAL_USER_SCENARIO = {
    "goal_text": "Learn how neural networks solve XOR using activation functions and gradient descent",
    "golden_concepts": list(GOLDEN_PATH),
    "requested_days": 60,
    "daily_minutes": 60,
    "same_deadline": True,
    "same_source_version": True,
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def evaluate_objective_exercise(exercise: dict[str, Any]) -> dict[str, Any]:
    """Return learner-facing quality failures without changing generated content."""
    questions = list((exercise or {}).get("questions") or [])
    failures: list[dict[str, str]] = []
    seen_prompts: set[str] = set()
    correct_positions: list[int] = []
    question_types: list[str] = []
    for index, question in enumerate(questions, 1):
        prompt = _text(question.get("prompt"))
        options = list(question.get("options") or [])
        explanation = _text(question.get("explanation"))
        question_type = str(question.get("question_type") or "")
        question_types.append(question_type)
        if not prompt:
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "missing_prompt"})
        if prompt in seen_prompts:
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "duplicate_prompt"})
        seen_prompts.add(prompt)
        if any(marker in prompt for marker in GENERIC_PROMPT_MARKERS):
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "generic_prompt_template"})
        if question_type not in REQUIRED_QUESTION_TYPES:
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "invalid_question_type"})
        if not question.get("assessment_target_id"):
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "missing_assessment_target"})
        if not _text(question.get("correct_reasoning")):
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "missing_correct_reasoning"})
        if not question.get("source_refs") and not question.get("page_references"):
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "missing_source_reference"})
        if not explanation or len(explanation.split()) < 8:
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "thin_feedback"})
        correct = [option_index for option_index, option in enumerate(options) if option.get("correct")]
        if len(options) < 3 or len(correct) != 1:
            failures.append({"question_id": str(question.get("question_id") or index), "reason": "invalid_options"})
            continue
        correct_positions.append(correct[0])
        for option in options:
            text = _text(option.get("text"))
            feedback = _text(option.get("feedback"))
            if not feedback or len(feedback.split()) < 5:
                failures.append({"question_id": str(question.get("question_id") or index), "reason": "missing_option_feedback"})
            if not option.get("correct") and any(marker in text for marker in NONSENSE_DISTRACTOR_MARKERS):
                failures.append({"question_id": str(question.get("question_id") or index), "reason": "nonsense_distractor"})
    if len(questions) < 3:
        failures.append({"question_id": "exercise", "reason": "fewer_than_three_questions"})
    if len(correct_positions) >= 3 and len(set(correct_positions)) == 1:
        failures.append({"question_id": "exercise", "reason": "unbalanced_correct_answer_position"})
    if len(questions) >= 3 and set(question_types) != REQUIRED_QUESTION_TYPES:
        failures.append({"question_id": "exercise", "reason": "missing_required_question_categories"})
    return {
        "baseline_version": V4_QUALITY_BASELINE_VERSION,
        "question_count": len(questions),
        "passed": not failures,
        "failures": failures,
    }


def golden_baseline_manifest() -> dict[str, Any]:
    """Static KQ0 acceptance manifest; no learner data or model calls are stored."""
    return {
        "baseline_version": V4_QUALITY_BASELINE_VERSION,
        "golden_concepts": list(GOLDEN_PATH),
        "normal_profiles": NORMAL_PROFILE_FIXTURES,
        "controlled_scenario": CONTROLLED_DUAL_USER_SCENARIO,
        "known_failures": [
            "two prior plan ids resolved to the same learner profile",
            "regeneration did not expose learner adaptation fields",
            "the visible difference was mainly estimated time",
            "fallback content and stale cache could conceal prompt changes",
            "generic definition-style prompts",
            "nonsense or unrelated distractors",
            "all correct answers in the same position",
            "feedback that does not explain the mechanism",
            "questions disconnected from the taught section",
        ],
        "acceptance_rules": [
            "three or more questions",
            "exactly one correct answer per question",
            "no generic prompt template",
            "no nonsense distractor",
            "specific feedback of at least eight words",
            "three distinct question categories and an approved assessment target",
            "source reference plus option-level feedback for every question",
            "correct answer positions are not all identical",
            "both users share the same goal, source version, time budget, and canonical concepts",
            "content differs in at least six teaching dimensions while canonical facts stay identical",
        ],
    }
