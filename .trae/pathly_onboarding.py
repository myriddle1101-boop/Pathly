"""Persistent first-time and repeat onboarding for Pathly Stage O3."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from agents.goal_parser import GoalParser
from pathly_backend import PathlyBackend, profile_from_payload
from pathly_goal_interpretation import GoalInterpretationStore
from verified_golden_sources import verified_goal_concepts_for_goal
from goal_chain_catalog import resolve_goal_chain


class OnboardingValidationError(ValueError):
    pass


class OnboardingDraftNotFoundError(KeyError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


STABLE_PROFILE_QUESTIONS = [
    {
        "id": "math_situation",
        "dimension": "mathematical_ability",
        "prompt": "Which statement best describes you when working with formulas and mathematical derivations?",
        "type": "single_choice",
        "options": [
            {"value": "avoid_formulas", "label": "I usually avoid formulas"},
            {"value": "basic_algebra", "label": "I understand basic algebra"},
            {"value": "follow_derivation", "label": "I can follow standard derivations"},
            {"value": "use_calculus", "label": "I can use calculus and linear algebra independently"},
            {"value": "advanced_math", "label": "I can work through complex mathematical proofs"},
        ],
    },
    {
        "id": "programming_situation",
        "dimension": "programming_ability",
        "prompt": "How far can you usually get with a programming exercise?",
        "type": "single_choice",
        "options": [
            {"value": "no_code", "label": "I have no programming experience yet"},
            {"value": "follow_code", "label": "I can run code by following an example"},
            {"value": "small_scripts", "label": "I can write small scripts independently"},
            {"value": "complete_projects", "label": "I can complete medium-sized projects"},
            {"value": "advanced_engineering", "label": "I can design and debug complex systems"},
        ],
    },
    {
        "id": "abstract_situation",
        "dimension": "abstract_thinking",
        "prompt": "Which statement best describes how you learn abstract concepts?",
        "type": "single_choice",
        "options": [
            {"value": "need_concrete", "label": "I need a concrete object or scenario first"},
            {"value": "need_examples", "label": "I understand after seeing several examples"},
            {"value": "mixed_representation", "label": "A mix of examples and models works best"},
            {"value": "model_first", "label": "I can start with the abstract model"},
            {"value": "enjoy_abstraction", "label": "I enjoy transferring ideas and building abstract models"},
        ],
    },
    {
        "id": "logic_situation",
        "dimension": "logical_reasoning",
        "prompt": "How do you usually break down a complex problem?",
        "type": "single_choice",
        "options": [
            {"value": "need_steps", "label": "I need someone to provide each step"},
            {"value": "follow_structure", "label": "I can analyze it using an existing structure"},
            {"value": "partial_decompose", "label": "I can decompose most of the problem"},
            {"value": "independent_decompose", "label": "I can build a reasoning chain independently"},
            {"value": "compare_strategies", "label": "I can compare multiple reasoning strategies"},
        ],
    },
    {
        "id": "learning_experience",
        "dimension": "general_learning_foundation",
        "prompt": "What experience do you have learning a similar new field?",
        "type": "single_choice",
        "options": [
            {"value": "new_to_learning", "label": "Almost no structured learning experience"},
            {"value": "first_structured", "label": "I have completed one introductory course"},
            {"value": "some_courses", "label": "I have taken several related courses"},
            {"value": "independent_projects", "label": "I have completed independent projects"},
            {"value": "advanced_experience", "label": "I have advanced study or research experience"},
        ],
    },
    {
        "id": "learning_style",
        "dimension": "learning_style",
        "prompt": "How do you prefer to understand a new concept?",
        "type": "single_choice",
        "options": [
            {"value": "visual", "label": "Diagrams and relationships"},
            {"value": "example", "label": "Examples and analogies"},
            {"value": "theory", "label": "Definitions and derivations"},
            {"value": "hands_on", "label": "Hands-on practice"},
            {"value": "mixed", "label": "A balanced mix"},
        ],
    },
    {
        "id": "preferred_examples",
        "dimension": "preferred_examples",
        "prompt": "How should concepts be explained to you?",
        "type": "multi_choice",
        "options": [
            {"value": "daily_life", "label": "Everyday situations"},
            {"value": "business", "label": "Business applications"},
            {"value": "research", "label": "Research problems"},
            {"value": "code", "label": "Code examples"},
            {"value": "mathematics", "label": "Mathematical examples"},
        ],
    },
    {
        "id": "interest_tags",
        "dimension": "interest_tags",
        "prompt": "Which domains should examples use when possible?",
        "type": "multi_choice",
        "options": [
            {"value": "healthcare", "label": "Healthcare"},
            {"value": "finance", "label": "Finance"},
            {"value": "education", "label": "Education"},
            {"value": "natural_language", "label": "Natural Language"},
            {"value": "computer_vision", "label": "Computer Vision"},
            {"value": "business", "label": "Business"},
            {"value": "no_preference", "label": "No preference"},
        ],
    },
    {
        "id": "pace_preference",
        "dimension": "pace_preference",
        "prompt": "What learning pace do you prefer?",
        "type": "single_choice",
        "options": [
            {"value": "intensive", "label": "Intensive progress"},
            {"value": "steady", "label": "Steady and consistent"},
            {"value": "flexible", "label": "Flexible based on my current capacity"},
        ],
    },


    {
        "id": "self_regulation",
        "dimension": "self_regulation",
        "prompt": "What is your recovery level after an interruption?",
        "type": "scale",
        "min": 1,
        "max": 5,
    },
]

PLAN_CONTEXT_QUESTIONS = [
    {
        "id": "target_familiarity",
        "dimension": "target_mastery",
        "prompt": "How familiar are you with the core concepts in this new goal?",
        "type": "single_choice",
        "options": [
            {"value": "never", "label": "I have never encountered them"},
            {"value": "heard", "label": "I have heard of them but cannot explain them"},
            {"value": "studied", "label": "I have studied them systematically"},
            {"value": "applied", "label": "I can apply them in practice"},
        ],
    },
    {
        "id": "current_confidence",
        "dimension": "current_confidence",
        "prompt": "How confident are you that you can complete this new path?",
        "type": "scale",
        "min": 1,
        "max": 5,
    },
    {
        "id": "current_anxiety",
        "dimension": "current_anxiety",
        "prompt": "How much pressure does this new goal create right now?",
        "type": "scale",
        "min": 1,
        "max": 5,
    },
]

FIRST_TIME_QUESTIONS = [*STABLE_PROFILE_QUESTIONS, *PLAN_CONTEXT_QUESTIONS]

REPEAT_QUESTIONS = [
    {
        "id": "profile_changed",
        "dimension": "profile_review",
        "prompt": "Have your foundations or long-term learning preferences changed since the last path?",
        "type": "single_choice",
        "options": [
            {"value": "no", "label": "No, keep using them"},
            {"value": "yes", "label": "Yes, I want to review and update them"},
        ],
    },
    *PLAN_CONTEXT_QUESTIONS,
]

# Kept only so drafts created by older builds can still be submitted.  The
# question is no longer exposed; absence means the learner's long-term
# preference is used (the same behavior as ``use_default``).
LEGACY_OPTIONAL_ANSWER_IDS = {"path_style_override"}


SITUATIONAL_SCORES = {
    "math_situation": {
        "avoid_formulas": 1,
        "basic_algebra": 2,
        "follow_derivation": 3,
        "use_calculus": 4,
        "advanced_math": 5,
    },
    "programming_situation": {
        "no_code": 1,
        "follow_code": 2,
        "small_scripts": 3,
        "complete_projects": 4,
        "advanced_engineering": 5,
    },
    "abstract_situation": {
        "need_concrete": 1,
        "need_examples": 2,
        "mixed_representation": 3,
        "model_first": 4,
        "enjoy_abstraction": 5,
    },
    "logic_situation": {
        "need_steps": 1,
        "follow_structure": 2,
        "partial_decompose": 3,
        "independent_decompose": 4,
        "compare_strategies": 5,
    },
    "learning_experience": {
        "new_to_learning": 1,
        "first_structured": 2,
        "some_courses": 3,
        "independent_projects": 4,
        "advanced_experience": 5,
    },
}


class OnboardingStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS onboarding_drafts (
                    draft_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    onboarding_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step INTEGER NOT NULL DEFAULT 0,
                    draft_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_onboarding_drafts_user
                    ON onboarding_drafts(user_id, updated_at DESC);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, draft: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO onboarding_drafts(
                    draft_id, user_id, onboarding_type, status, current_step,
                    draft_json, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(draft_id) DO UPDATE SET
                    status=excluded.status,
                    current_step=excluded.current_step,
                    draft_json=excluded.draft_json,
                    updated_at=excluded.updated_at
                """,
                (
                    draft["draft_id"],
                    draft["user_id"],
                    draft["onboarding_type"],
                    draft["status"],
                    int(draft.get("current_step") or 0),
                    json.dumps(draft, ensure_ascii=False),
                    draft.get("created_at") or now,
                    now,
                ),
            )
        return self.get(draft["user_id"], draft["draft_id"]) or {}

    def get(self, user_id: str, draft_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM onboarding_drafts
                WHERE draft_id = ? AND user_id = ? AND deleted_at IS NULL
                """,
                (draft_id, user_id),
            ).fetchone()
        if not row:
            return None
        draft = json.loads(row["draft_json"])
        draft["status"] = row["status"]
        draft["current_step"] = row["current_step"]
        draft["updated_at"] = row["updated_at"]
        return draft

    def list(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT draft_id FROM onboarding_drafts
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            draft
            for row in rows
            if (draft := self.get(user_id, row["draft_id"])) is not None
        ]

    def delete(self, user_id: str, draft_id: str) -> None:
        now = _now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE onboarding_drafts
                SET deleted_at = ?, updated_at = ?
                WHERE draft_id = ? AND user_id = ? AND deleted_at IS NULL
                """,
                (now, now, draft_id, user_id),
            )
            if cursor.rowcount == 0:
                raise OnboardingDraftNotFoundError(draft_id)


class OnboardingService:
    def __init__(
        self,
        store: OnboardingStore,
        backend: PathlyBackend,
        goal_interpretations: GoalInterpretationStore | None = None,
    ):
        self.store = store
        self.backend = backend
        self.goal_interpretations = goal_interpretations

    def create_draft(
        self,
        *,
        user_id: str,
        goal_text: str,
        name: str | None = None,
        academic_level: str | None = None,
        domain: str | None = None,
        goal_interpretation_id: str | None = None,
    ) -> dict[str, Any]:
        user_id = user_id.strip()
        goal_text = goal_text.strip()
        if not user_id or not goal_text:
            raise OnboardingValidationError("user_id and goal_text are required")
        existing = self.backend.get_profile_record(user_id)
        onboarding_type = "repeat" if existing else "first_time"
        interpretation = None
        if goal_interpretation_id:
            if not self.goal_interpretations:
                raise OnboardingValidationError("Goal interpretation service is unavailable")
            interpretation = self.goal_interpretations.get(user_id, goal_interpretation_id)
            if not interpretation:
                raise OnboardingValidationError("Goal interpretation not found for this user")
            if interpretation.get("status") != "confirmed":
                raise OnboardingValidationError(
                    "Goal interpretation must be confirmed before profile onboarding"
                )
        target_terms = self._target_terms(goal_text, interpretation)
        catalog_match = resolve_goal_chain(goal_text)
        questions = REPEAT_QUESTIONS if existing else FIRST_TIME_QUESTIONS
        now = _now_iso()
        draft = {
            "draft_id": str(uuid.uuid4()),
            "user_id": user_id,
            "onboarding_type": onboarding_type,
            "status": "draft",
            "current_step": 0,
            "goal_text": goal_text,
            "goal_interpretation_id": goal_interpretation_id,
            "target_terms": target_terms,
            "approved_goal_scope": (
                {
                    "goal_id": catalog_match[0],
                    "canonical_path": list(catalog_match[1]["canonical_path"]),
                    "display_names": list(catalog_match[1]["display_names"]),
                    "asset_scope": catalog_match[1]["asset_scope"],
                    "source_version": catalog_match[1]["source_version"],
                }
                if catalog_match else None
            ),
            "basic_info": {
                "name": name or (existing or {}).get("name") or "Pathly Learner",
                "academic_level": academic_level
                or (existing or {}).get("academic_level")
                or "unspecified",
                "domain": domain or (existing or {}).get("domain") or "user-defined",
            },
            # The old path-style answer is represented internally for
            # compatibility, but is not a visible or required question.
            "answers": {"path_style_override": "use_default"},
            "questions": questions,
            "required_answer_ids": [question["id"] for question in questions],
            "profile_review_questions": STABLE_PROFILE_QUESTIONS if existing else [],
            "profile_review_changes": [],
            "reused_fields": self._reused_fields(existing),
            "stable_profile_before": self._stable_profile(existing),
            "profile_preview": {},
            "path_context_preview": {},
            "profile_review_required": False,
            "legacy_constraint_placeholder": not bool(existing),
            "created_at": now,
            "updated_at": now,
        }
        return self._recompute_and_save(draft)

    def update_draft(
        self,
        *,
        user_id: str,
        draft_id: str,
        answers: dict[str, Any] | None = None,
        current_step: int | None = None,
        goal_text: str | None = None,
    ) -> dict[str, Any]:
        draft = self.store.get(user_id, draft_id)
        if not draft:
            raise OnboardingDraftNotFoundError(draft_id)
        if draft["status"] != "draft":
            raise OnboardingValidationError("A confirmed onboarding draft is read-only")
        self._normalize_repeat_draft(draft)
        review_ids = self._review_answer_ids(draft)
        allowed = (
            set(draft["required_answer_ids"])
            | review_ids
            | LEGACY_OPTIONAL_ANSWER_IDS
        )
        incoming = answers or {}
        profile_changed = incoming.get(
            "profile_changed",
            draft.get("answers", {}).get("profile_changed"),
        )
        for answer_id in incoming:
            if answer_id not in allowed:
                raise OnboardingValidationError(f"Unknown onboarding answer: {answer_id}")
            if answer_id in review_ids and profile_changed != "yes":
                raise OnboardingValidationError(
                    "Profile review answers require profile_changed=yes"
                )
        merged_answers = dict(draft.get("answers", {}))
        for answer_id, value in incoming.items():
            if value is None:
                if answer_id in draft["required_answer_ids"]:
                    raise OnboardingValidationError(
                        f"Required onboarding answer cannot be cleared: {answer_id}"
                    )
                merged_answers.pop(answer_id, None)
            else:
                merged_answers[answer_id] = value
        if merged_answers.get("profile_changed") != "yes":
            for answer_id in review_ids:
                merged_answers.pop(answer_id, None)
        draft["answers"] = merged_answers
        if current_step is not None:
            draft["current_step"] = max(0, min(int(current_step), len(draft["questions"])))
        if goal_text is not None and goal_text.strip():
            draft["goal_text"] = goal_text.strip()
            draft["target_terms"] = self._target_terms(draft["goal_text"], None)
            catalog_match = resolve_goal_chain(draft["goal_text"])
            draft["approved_goal_scope"] = ({"goal_id": catalog_match[0], "canonical_path": list(catalog_match[1]["canonical_path"]), "display_names": list(catalog_match[1]["display_names"]), "asset_scope": catalog_match[1]["asset_scope"], "source_version": catalog_match[1]["source_version"]} if catalog_match else None)
        draft["updated_at"] = _now_iso()
        return self._recompute_and_save(draft)

    def revise_goal(
        self,
        *,
        user_id: str,
        draft_id: str,
        goal_text: str,
        goal_interpretation_id: str | None = None,
    ) -> dict[str, Any]:
        draft = self.store.get(user_id, draft_id)
        if not draft:
            raise OnboardingDraftNotFoundError(draft_id)
        if draft.get("status") not in {"draft", "profile_confirmed"} or draft.get("plan_id"):
            raise OnboardingValidationError(
                "Only an unplanned onboarding path can revise its goal"
            )
        goal_text = goal_text.strip()
        if not goal_text:
            raise OnboardingValidationError("goal_text is required")
        interpretation = None
        if goal_interpretation_id:
            if not self.goal_interpretations:
                raise OnboardingValidationError(
                    "Goal interpretation service is unavailable"
                )
            interpretation = self.goal_interpretations.get(
                user_id,
                goal_interpretation_id,
            )
            if not interpretation:
                raise OnboardingValidationError(
                    "Goal interpretation not found for this user"
                )
            if interpretation.get("status") != "confirmed":
                raise OnboardingValidationError(
                    "Goal interpretation must be confirmed before revising the goal"
                )
        draft["goal_text"] = goal_text
        draft["goal_interpretation_id"] = goal_interpretation_id
        draft["target_terms"] = self._target_terms(goal_text, interpretation)
        catalog_match = resolve_goal_chain(goal_text)
        draft["approved_goal_scope"] = ({"goal_id": catalog_match[0], "canonical_path": list(catalog_match[1]["canonical_path"]), "display_names": list(catalog_match[1]["display_names"]), "asset_scope": catalog_match[1]["asset_scope"], "source_version": catalog_match[1]["source_version"]} if catalog_match else None)
        draft.pop("knowledge_map_review", None)
        if draft.get("status") == "profile_confirmed":
            for key in (
                "workload_estimate_id",
                "workload_estimate",
                "feasibility_decision_id",
            ):
                draft.pop(key, None)
        draft["updated_at"] = _now_iso()
        return self._recompute_and_save(draft)

    def confirm_knowledge_map(
        self,
        *,
        user_id: str,
        draft_id: str,
        reviewed_concepts: list[dict[str, Any]],
        excluded_concept_ids: list[str],
        edges: list[dict[str, Any]],
    ) -> dict[str, Any]:
        draft = self.store.get(user_id, draft_id)
        if not draft:
            raise OnboardingDraftNotFoundError(draft_id)
        if draft.get("status") != "draft":
            raise OnboardingValidationError(
                "The knowledge map is read-only after learner profile confirmation"
            )
        concepts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in reviewed_concepts:
            concept_id = str(raw.get("concept_id") or "").strip()
            if not concept_id or concept_id in seen:
                continue
            seen.add(concept_id)
            concepts.append(
                {
                    "concept_id": concept_id,
                    "display_name": str(
                        raw.get("display_name") or raw.get("title") or concept_id
                    ).strip(),
                    "is_target": bool(raw.get("is_target")),
                    "source_type": str(raw.get("source_type") or "public"),
                    "path_role": str(raw.get("path_role") or "supporting"),
                }
            )
        if not concepts:
            raise OnboardingValidationError("Review at least one knowledge-map concept")
        target_ids = {item["concept_id"] for item in concepts if item["is_target"]}
        if not target_ids:
            raise OnboardingValidationError("The reviewed map must retain its learning target")
        excluded = list(dict.fromkeys(str(item).strip() for item in excluded_concept_ids if str(item).strip()))
        unknown = set(excluded) - seen
        if unknown:
            raise OnboardingValidationError(
                "Excluded concepts are outside the reviewed map: " + ", ".join(sorted(unknown))
            )
        protected = set(excluded) & target_ids
        if protected:
            raise OnboardingValidationError(
                "Learning targets cannot be excluded: " + ", ".join(sorted(protected))
            )
        included = [item["concept_id"] for item in concepts if item["concept_id"] not in excluded]
        active = set(included)
        clean_edges: list[dict[str, str]] = []
        for raw in edges:
            source = str(raw.get("source") or "").strip()
            target = str(raw.get("target") or "").strip()
            if source in active and target in active and source != target:
                clean_edges.append(
                    {"source": source, "target": target, "type": str(raw.get("type") or "sequence_hint")}
                )
        draft["knowledge_map_review"] = {
            "status": "confirmed",
            "reviewed_concepts": concepts,
            "included_concept_ids": included,
            "excluded_concept_ids": excluded,
            "edges": clean_edges,
            "confirmed_at": _now_iso(),
        }
        draft["updated_at"] = _now_iso()
        return self.store.save(draft)
    def confirm_profile(
        self,
        *,
        user_id: str,
        draft_id: str,
        cognitive_overrides: dict[str, Any] | None = None,
        affective_overrides: dict[str, Any] | None = None,
        target_mastery_overrides: dict[str, Any] | None = None,
        preference_overrides: dict[str, Any] | None = None,
        current_affective_state_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        draft = self.store.get(user_id, draft_id)
        if not draft:
            raise OnboardingDraftNotFoundError(draft_id)
        if draft.get("status") != "draft":
            raise OnboardingValidationError("A confirmed onboarding draft is read-only")
        self._normalize_repeat_draft(draft)
        missing = [
            answer_id
            for answer_id in draft["required_answer_ids"]
            if answer_id not in draft.get("answers", {})
        ]
        if missing:
            raise OnboardingValidationError(
                "Required onboarding answers are missing: " + ", ".join(missing)
            )
        if (
            draft.get("onboarding_type") == "repeat"
            and draft.get("answers", {}).get("profile_changed") == "yes"
            and not (self._review_answer_ids(draft) & set(draft.get("answers", {})))
            and not (cognitive_overrides or affective_overrides)
        ):
            raise OnboardingValidationError(
                "Select at least one profile dimension to update, or choose to keep the existing profile"
            )
        preview = self._infer(draft)
        cognitive = {
            **preview["cognitive_traits"],
            **self._validated_scores(cognitive_overrides or {}, "cognitive"),
        }
        affective = {
            **preview["affective_defaults"],
            **self._validated_affective(affective_overrides or {}),
        }
        mastery_overrides = self._validated_mastery(target_mastery_overrides or {})
        unknown_mastery = set(mastery_overrides) - set(draft["target_terms"])
        if unknown_mastery:
            raise OnboardingValidationError(
                "Target mastery override is outside this goal: "
                + ", ".join(sorted(unknown_mastery))
            )
        target_mastery = {
            **preview["target_mastery"],
            **mastery_overrides,
        }
        target_mastery_evidence = dict(preview["target_mastery_evidence"])
        for target, value in mastery_overrides.items():
            target_mastery_evidence[target] = self._record(
                value=value,
                confidence=1.0,
                reason="Learner directly corrected target-specific mastery",
                source="user_override",
            )
            target_mastery_evidence[target]["confirmed"] = True
        path_preferences = {
            **preview["preference_overrides"],
            **(preference_overrides or {}),
        }
        current_affective = {
            **preview["current_affective_state"],
            **self._validated_scores(
                current_affective_state_overrides or {},
                "current affective",
            ),
        }
        inference_records = self._confirmed_inference_records(
            preview["inference_records"],
            cognitive_overrides or {},
            affective_overrides or {},
        )
        legacy = self.backend.profiles.get_profile(user_id)
        if not legacy:
            legacy = profile_from_payload(
                {
                    "user_id": user_id,
                    "name": draft["basic_info"]["name"],
                    "academic_level": draft["basic_info"]["academic_level"],
                    "domain": draft["basic_info"]["domain"],
                    "goal_text": draft["goal_text"],
                    # Compatibility placeholders only. O5 will collect and
                    # negotiate path-specific time constraints.
                    "target_days": 7,
                    "daily_minutes": 75,
                }
            )
        legacy.name = draft["basic_info"]["name"]
        legacy.academic_level = draft["basic_info"]["academic_level"]
        legacy.domain = draft["basic_info"]["domain"]
        legacy.goal_text = draft["goal_text"]
        legacy.math_foundation = int(cognitive["mathematical_ability"])
        legacy.programming_foundation = int(cognitive["programming_ability"])
        legacy.prior_knowledge_level = round(
            (
                float(cognitive["abstract_thinking"])
                + float(cognitive["logical_reasoning"])
                + float(cognitive["general_learning_foundation"])
            )
            / 3
        )
        legacy.preferred_style = str(affective["learning_style"])
        legacy.preferred_examples = list(affective["preferred_examples"])
        legacy.pace_preference = {
            "intensive": "fast",
            "steady": "medium",
            "flexible": "medium",
        }.get(str(affective["pace_preference"]), str(affective["pace_preference"]))
        legacy.interest_tags = list(affective.get("interest_tags") or [])
        legacy.motivation_level = int(affective["motivation_baseline"])
        # Legacy flat columns remain for compatibility only. Confidence and
        # pressure are now path context and must not become reusable defaults.
        legacy.confidence_level = 3
        legacy.anxiety_level = 3
        legacy.self_regulation = int(affective["self_regulation"])
        previous_record = self.backend.get_profile_record(user_id) or {}
        next_profile_version = max(2, int(previous_record.get("profile_version") or 1) + 1)
        profile_record = self.backend.save_profile(
            legacy,
            {
                "profile_version": next_profile_version,
                "cognitive_traits": cognitive,
                "affective_defaults": affective,
                "inference_records": inference_records,
            },
        )
        draft["status"] = "profile_confirmed"
        draft["current_step"] = len(draft["questions"])
        draft["profile_preview"] = {
            "cognitive_traits": cognitive,
            "affective_defaults": affective,
            "inference_records": inference_records,
        }
        draft["path_context_preview"] = {
            "goal_text": draft["goal_text"],
            "target_terms": draft["target_terms"],
            "target_mastery": target_mastery,
            "target_mastery_evidence": target_mastery_evidence,
            "preference_overrides": path_preferences,
            "current_affective_state": current_affective,
        }
        draft["profile_snapshot"] = profile_record
        draft["confirmed_at"] = _now_iso()
        draft["updated_at"] = _now_iso()
        return self.store.save(draft)

    def _recompute_and_save(self, draft: dict[str, Any]) -> dict[str, Any]:
        preview = self._infer(draft)
        draft["profile_preview"] = {
            "cognitive_traits": preview["cognitive_traits"],
            "affective_defaults": preview["affective_defaults"],
            "inference_records": preview["inference_records"],
        }
        draft["path_context_preview"] = {
            "goal_text": draft["goal_text"],
            "target_terms": draft["target_terms"],
            "target_mastery": preview["target_mastery"],
            "target_mastery_evidence": preview["target_mastery_evidence"],
            "preference_overrides": preview["preference_overrides"],
            "current_affective_state": preview["current_affective_state"],
        }
        draft["profile_review_required"] = (
            draft["onboarding_type"] == "repeat"
            and draft.get("answers", {}).get("profile_changed") == "yes"
        )
        draft["profile_review_changes"] = self._profile_review_changes(draft, preview)
        draft["answered_count"] = sum(
            answer_id in draft.get("answers", {})
            for answer_id in draft["required_answer_ids"]
        )
        draft["remaining_required"] = [
            answer_id
            for answer_id in draft["required_answer_ids"]
            if answer_id not in draft.get("answers", {})
        ]
        return self.store.save(draft)

    @staticmethod
    def _review_answer_ids(draft: dict[str, Any]) -> set[str]:
        return {
            question["id"]
            for question in draft.get("profile_review_questions") or []
        }

    def _normalize_repeat_draft(self, draft: dict[str, Any]) -> None:
        removed = {"confidence_level", "anxiety_level", "current_motivation"}
        hidden_legacy = {"path_style_override"}
        draft["questions"] = [
            question for question in draft.get("questions") or []
            if question.get("id") not in removed | hidden_legacy
        ]
        draft["required_answer_ids"] = [
            answer_id for answer_id in draft.get("required_answer_ids") or []
            if answer_id not in removed | hidden_legacy
        ]
        for answer_id in removed:
            draft.setdefault("answers", {}).pop(answer_id, None)
        # Do not delete a legacy path-style answer: it remains readable for
        # old drafts, while new and missing values resolve to use_default.
        draft.setdefault("answers", {}).setdefault("path_style_override", "use_default")
        if draft.get("onboarding_type") != "repeat":
            existing_ids = {question.get("id") for question in draft["questions"]}
            for question in PLAN_CONTEXT_QUESTIONS:
                if question["id"] not in existing_ids:
                    draft["questions"].append(question)
                    draft["required_answer_ids"].append(question["id"])
            return
        draft["questions"] = [
            question
            for question in draft.get("questions") or REPEAT_QUESTIONS
            if question.get("id") != "current_motivation"
        ]
        draft["required_answer_ids"] = [
            answer_id
            for answer_id in draft.get("required_answer_ids") or []
            if answer_id != "current_motivation"
        ]
        review_questions = list(draft.get("profile_review_questions") or STABLE_PROFILE_QUESTIONS)
        review_questions = [
            question for question in review_questions
            if question.get("id") not in {"confidence_level", "anxiety_level"}
        ]
        review_ids = {question.get("id") for question in review_questions}
        for question in STABLE_PROFILE_QUESTIONS:
            if question.get("id") not in review_ids:
                review_questions.append(question)
                review_ids.add(question.get("id"))
        draft["profile_review_questions"] = review_questions
        draft.setdefault("profile_review_changes", [])

    def _profile_review_changes(
        self,
        draft: dict[str, Any],
        preview: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if draft.get("answers", {}).get("profile_changed") != "yes":
            return []
        mapping = {
            "math_situation": ("cognitive_traits", "mathematical_ability"),
            "programming_situation": ("cognitive_traits", "programming_ability"),
            "abstract_situation": ("cognitive_traits", "abstract_thinking"),
            "logic_situation": ("cognitive_traits", "logical_reasoning"),
            "learning_experience": ("cognitive_traits", "general_learning_foundation"),
            "learning_style": ("affective_defaults", "learning_style"),
            "preferred_examples": ("affective_defaults", "preferred_examples"),
            "interest_tags": ("affective_defaults", "interest_tags"),
            "pace_preference": ("affective_defaults", "pace_preference"),
            "self_regulation": ("affective_defaults", "self_regulation"),
        }
        previous = draft.get("stable_profile_before") or {}
        changes = []
        for answer_id in self._review_answer_ids(draft) & set(draft.get("answers", {})):
            section, dimension = mapping[answer_id]
            before = (previous.get(section) or {}).get(dimension)
            after = (preview.get(section) or {}).get(dimension)
            if before != after:
                changes.append({
                    "answer_id": answer_id,
                    "dimension": dimension,
                    "before": before,
                    "after": after,
                })
        return sorted(changes, key=lambda item: item["dimension"])
    def _infer(self, draft: dict[str, Any]) -> dict[str, Any]:
        answers = draft.get("answers", {})
        previous = draft.get("stable_profile_before") or {}
        cognitive = dict(previous.get("cognitive_traits") or {})
        affective = dict(previous.get("affective_defaults") or {})
        affective.pop("confidence_baseline", None)
        affective.pop("anxiety_baseline", None)
        records: dict[str, Any] = {}
        cognitive_questions = {
            "math_situation": "mathematical_ability",
            "programming_situation": "programming_ability",
            "abstract_situation": "abstract_thinking",
            "logic_situation": "logical_reasoning",
            "learning_experience": "general_learning_foundation",
        }
        for answer_id, dimension in cognitive_questions.items():
            if answer_id not in answers:
                cognitive.setdefault(dimension, 3)
                continue
            value = self._situational_score(answer_id, answers[answer_id])
            cognitive[dimension] = value
            records[dimension] = self._record(
                value=value,
                confidence=0.78,
                reason=f"Inferred from situational response '{answers[answer_id]}'",
                source=f"onboarding_answer:{answer_id}",
            )
        if "learning_style" in answers:
            affective["learning_style"] = str(answers["learning_style"])
            records["learning_style"] = self._record(
                value=affective["learning_style"],
                confidence=0.9,
                reason="Learner selected a preferred explanation style",
                source="onboarding_answer:learning_style",
            )
        affective.setdefault("learning_style", "mixed")
        if "preferred_examples" in answers:
            examples = answers["preferred_examples"]
            if not isinstance(examples, list) or not examples:
                raise OnboardingValidationError("preferred_examples must be a non-empty list")
            affective["preferred_examples"] = [str(item) for item in examples]
            records["preferred_examples"] = self._record(
                value=affective["preferred_examples"],
                confidence=0.9,
                reason="Learner selected preferred example domains",
                source="onboarding_answer:preferred_examples",
            )
        affective.setdefault("preferred_examples", [])
        if "interest_tags" in answers:
            tags = answers["interest_tags"]
            if not isinstance(tags, list) or not tags:
                raise OnboardingValidationError("interest_tags must be a non-empty list")
            normalized_tags = [str(item) for item in tags]
            if "no_preference" in normalized_tags:
                normalized_tags = ["no_preference"]
            affective["interest_tags"] = normalized_tags
            records["interest_tags"] = self._record(
                value=affective["interest_tags"],
                confidence=0.9,
                reason="Learner selected application domains for examples and practice",
                source="onboarding_answer:interest_tags",
            )
        affective.setdefault("interest_tags", ["no_preference"])
        if "pace_preference" in answers:
            affective["pace_preference"] = str(answers["pace_preference"])
            records["pace_preference"] = self._record(
                value=affective["pace_preference"],
                confidence=0.9,
                reason="Learner selected a preferred long-term pace",
                source="onboarding_answer:pace_preference",
            )
        affective.setdefault("pace_preference", "steady")
        for answer_id, dimension in {
            "motivation_level": "motivation_baseline",
            "self_regulation": "self_regulation",
        }.items():
            if answer_id not in answers:
                affective.setdefault(dimension, 3 if dimension != "anxiety_baseline" else 2)
                continue
            value = self._score(answers[answer_id], answer_id)
            affective[dimension] = value
            records[dimension] = self._record(
                value=value,
                confidence=0.95,
                reason="Learner provided a current self-report",
                source=f"onboarding_answer:{answer_id}",
            )
        affective.pop("daily_minutes", None)
        affective.pop("daily_time_minutes", None)

        familiarity = str(answers.get("target_familiarity") or "never")
        mastery_score = {
            "never": 0.0,
            "heard": 0.25,
            "studied": 0.55,
            "applied": 0.8,
        }.get(familiarity, 0.0)
        target_mastery = {
            target: mastery_score
            for target in draft.get("target_terms") or []
        }
        mastery_source = (
            "onboarding_answer:target_familiarity"
            if "target_familiarity" in answers
            else "onboarding_default:no_target_familiarity"
        )
        mastery_confidence = 0.85 if "target_familiarity" in answers else 0.4
        target_mastery_evidence = {
            target: self._record(
                value=mastery_score,
                confidence=mastery_confidence,
                reason=(
                    f"Target familiarity was reported as '{familiarity}'"
                    if "target_familiarity" in answers
                    else "No target familiarity was reported; defaulted to no prior mastery"
                ),
                source=mastery_source,
            )
            for target in draft.get("target_terms") or []
        }
        preference = str(answers.get("path_style_override") or "use_default")
        preference_overrides = {} if preference == "use_default" else {"activity_style": preference}
        current_affective = {
            "motivation": self._score(
                answers.get("current_motivation", affective.get("motivation_baseline", 3)),
                "current_motivation",
            ),
            "confidence": self._score(
                answers.get("current_confidence", 3),
                "current_confidence",
            ),
            "anxiety": self._score(
                answers.get("current_anxiety", 3),
                "current_anxiety",
            ),
        }
        return {
            "cognitive_traits": cognitive,
            "affective_defaults": affective,
            "inference_records": {
                **(previous.get("inference_records") or {}),
                **records,
            },
            "target_mastery": target_mastery,
            "target_mastery_evidence": target_mastery_evidence,
            "preference_overrides": preference_overrides,
            "current_affective_state": current_affective,
        }

    @staticmethod
    def _target_terms(
        goal_text: str,
        interpretation: dict[str, Any] | None,
    ) -> list[str]:
        verified_terms = verified_goal_concepts_for_goal(goal_text)
        catalog = resolve_goal_chain(goal_text)
        if not verified_terms and catalog:
            verified_terms = list(catalog[1]["canonical_path"])
        private_terms: list[str] = []
        if interpretation:
            terms = [
                item["concept_id"]
                for item in interpretation.get("canonical_concepts") or []
            ]
            private_terms = [
                item["private_concept_id"]
                for item in interpretation.get("private_concepts") or []
            ]
            if verified_terms:
                return list(dict.fromkeys([*verified_terms, *private_terms]))
            terms.extend(private_terms)
            if terms:
                return list(dict.fromkeys(terms))
        if verified_terms:
            return list(verified_terms)
        parser = GoalParser()
        explicit = parser._extract_known_concept(goal_text)
        return [explicit] if explicit else parser._clean_target_concepts([], goal_text)[:1]

    @staticmethod
    def _stable_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
        if not profile:
            return {}
        affective = dict(profile.get("affective_defaults") or {})
        affective.pop("confidence_baseline", None)
        affective.pop("anxiety_baseline", None)
        return {
            "cognitive_traits": profile.get("cognitive_traits") or {},
            "affective_defaults": affective,
            "inference_records": profile.get("inference_records") or {},
        }

    @staticmethod
    def _reused_fields(profile: dict[str, Any] | None) -> list[str]:
        if not profile:
            return []
        return [
            "basic_info",
            "cognitive_traits",
            "affective_defaults",
            "known_topics",
            "mastery_vector",
        ]

    @staticmethod
    def _situational_score(answer_id: str, answer: Any) -> int:
        if isinstance(answer, (int, float)):
            return OnboardingService._score(answer, answer_id)
        mapping = SITUATIONAL_SCORES[answer_id]
        if answer not in mapping:
            raise OnboardingValidationError(f"Unsupported answer for {answer_id}: {answer}")
        return mapping[answer]

    @staticmethod
    def _score(value: Any, field: str) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError) as exc:
            raise OnboardingValidationError(f"{field} must be between 1 and 5") from exc
        if not 1 <= score <= 5:
            raise OnboardingValidationError(f"{field} must be between 1 and 5")
        return score

    @staticmethod
    def _validated_scores(values: dict[str, Any], label: str) -> dict[str, int]:
        allowed = (
            {
                "mathematical_ability",
                "programming_ability",
                "abstract_thinking",
                "logical_reasoning",
                "general_learning_foundation",
            }
            if label == "cognitive"
            else {"motivation", "confidence", "anxiety"}
        )
        unknown = set(values) - allowed
        if unknown:
            raise OnboardingValidationError(
                f"Unsupported {label} override: " + ", ".join(sorted(unknown))
            )
        return {
            key: OnboardingService._score(value, f"{label}.{key}")
            for key, value in values.items()
        }

    @staticmethod
    def _validated_mastery(values: dict[str, Any]) -> dict[str, float]:
        result = {}
        for key, value in values.items():
            try:
                score = float(value)
            except (TypeError, ValueError) as exc:
                raise OnboardingValidationError(
                    f"target mastery for {key} must be between 0 and 1"
                ) from exc
            if not 0 <= score <= 1:
                raise OnboardingValidationError(
                    f"target mastery for {key} must be between 0 and 1"
                )
            result[str(key)] = round(score, 4)
        return result

    @staticmethod
    def _validated_affective(values: dict[str, Any]) -> dict[str, Any]:
        result = dict(values)
        for field in {
            "motivation_baseline",
            "confidence_baseline",
            "anxiety_baseline",
            "self_regulation",
        } & result.keys():
            result[field] = OnboardingService._score(result[field], field)
        if "preferred_examples" in result:
            if not isinstance(result["preferred_examples"], list):
                raise OnboardingValidationError("preferred_examples must be a list")
            result["preferred_examples"] = [str(item) for item in result["preferred_examples"]]
        result.pop("daily_minutes", None)
        result.pop("daily_time_minutes", None)
        return result

    @staticmethod
    def _record(
        *,
        value: Any,
        confidence: float,
        reason: str,
        source: str,
    ) -> dict[str, Any]:
        return {
            "value": value,
            "confidence": confidence,
            "reason": reason,
            "evidence_source": source,
            "confirmed": False,
            "updated_at": _now_iso(),
        }

    @staticmethod
    def _confirmed_inference_records(
        records: dict[str, Any],
        cognitive_overrides: dict[str, Any],
        affective_overrides: dict[str, Any],
    ) -> dict[str, Any]:
        confirmed = {}
        overrides = {**cognitive_overrides, **affective_overrides}
        for key, item in records.items():
            record = dict(item)
            if key in overrides:
                record.update(
                    {
                        "value": overrides[key],
                        "confidence": 1.0,
                        "reason": "Learner directly corrected the inferred value",
                        "evidence_source": "user_override",
                    }
                )
            record["confirmed"] = True
            record["updated_at"] = _now_iso()
            confirmed[key] = record
        for key, value in overrides.items():
            if key not in confirmed:
                confirmed[key] = {
                    "value": value,
                    "confidence": 1.0,
                    "reason": "Learner directly supplied this value",
                    "evidence_source": "user_override",
                    "confirmed": True,
                    "updated_at": _now_iso(),
                }
        return confirmed



