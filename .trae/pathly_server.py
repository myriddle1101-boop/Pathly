"""Pathly learner-facing web service.

Milestone 1 intentionally exposes only system endpoints and static assets. It
does not import or modify the Streamlit developer console on port 8501.
"""

from __future__ import annotations

import os
import copy
import hashlib
import json
import logging
import re
import subprocess
import time
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from pathly_backend import (
    PLAN_DB, PathlyBackend, PlanningClarificationRequiredError,
    PlanningUnavailableError, profile_from_payload,
)
from pathly_documents import (
    DocumentConflictError, DocumentNotFoundError, DocumentValidationError,
    PrivateDocumentService, PrivateDocumentStore,
)
from pathly_goal_interpretation import (
    GoalInterpretationNotFoundError, GoalInterpretationService,
    GoalInterpretationStore, GoalInterpretationValidationError,
)
from pathly_onboarding import (
    OnboardingDraftNotFoundError, OnboardingService, OnboardingStore,
    OnboardingValidationError,
)
from pathly_workload import WorkloadService, WorkloadStore, WorkloadValidationError
from pathly_feasibility import (
    FeasibilityDecisionNotFoundError, FeasibilityService, FeasibilityStore,
    FeasibilityValidationError,
)
from pathly_scheduler import ScheduleNotFoundError, ScheduleService, ScheduleValidationError
from pathly_daily import (
    DailyLearningNotFoundError,
    DailyLearningService,
    DailyLearningStore,
    DailyLearningValidationError,
)
from pathly_annotated_content import (
    AnnotatedContentService,
    AnnotatedContentStore,
    AnnotatedSessionNotFoundError,
    AnnotatedSessionValidationError,
)
from full_lecture_generator import generate_full_lecture, generate_full_lecture_from_daily, regenerate_full_lecture_section
from full_lecture_store import FullLectureProgressStore
from source_grounded_v4_store import SourceGroundedLectureV4Store, create_v4_baseline
from source_grounded_v4_generator import (
    S4_GENERATOR_VERSION, V4_PROMPT_VERSION, V4_TREATMENT_VERSION,
    generate_source_grounded_lecture_v4 as build_source_grounded_lecture_v4,
)
from source_grounded_v4_generator import V4_MAX_RETRY_ATTEMPTS
from source_linking_index import SOURCE_LINK_VERSION, ConceptSourceLinkIndex, links_from_lecture
from private_source_linking import PrivateSourceLinkResolver
from source_provenance_backfill import SourceProvenanceBackfill
from verified_golden_sources import GOLDEN_PATH, GOLDEN_PATH_VERSION, VerifiedGoldenSourceRegistry, verified_goal_concepts_for_goal
from goal_chain_catalog import resolve_goal_chain
from experience_goal_source_resolver import ExperienceGoalSourceResolver, FullExperienceSourceResolver
from public_source_registry import (
    PUBLIC_SOURCE_VERSION,
    PublicConceptSourceRegistry,
    PublicThenReviewedResolver,
)
from pathly_learning_loop import (
    LearningLoopNotFoundError,
    LearningLoopService,
    LearningLoopStore,
    LearningLoopValidationError,
)
from pathly_security import AnonymousSessionStore, COOKIE_NAME
from experience_run_store import ExperienceRunStore, build_experience_run
from experience_source_store import ExperienceSourceStore
from ablation_config import ABLATION_VERSION, capability_matrix, get_system_config
from v4_quality_baseline import NORMAL_PROFILE_FIXTURES
from pathly_neo4j import query_status as neo4j_query_status
from fresh_experience_baseline import TARGET_GOALS


PATHLY_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
DATA_DIR = Path(os.getenv("PATHLY_DATA_DIR", str(KG_DIR / "data"))).resolve()
PROFILE_DB = Path(os.getenv("PATHLY_PROFILE_DB", str(DATA_DIR / "learner_profiles.db"))).resolve()
CHROMA_DIR = Path(os.getenv("PATHLY_CHROMA_DIR", str(DATA_DIR / "chroma"))).resolve()
PRIVATE_DOCUMENT_DIR = Path(
    os.getenv("PATHLY_PRIVATE_DOCUMENT_DIR", str(DATA_DIR / "pathly_private_documents"))
).resolve()
PRIVATE_CHROMA_DIR = Path(
    os.getenv("PATHLY_PRIVATE_CHROMA_DIR", str(DATA_DIR / "pathly_private_chroma"))
).resolve()
KG_JSON = Path(
    os.getenv(
        "PATHLY_KG_JSON",
        str(KG_DIR / "web_data" / "global" / "global_knowledge_graph_calibrated.json"),
    )
).resolve()
backend = PathlyBackend()
document_store = PrivateDocumentStore(PLAN_DB)
document_service = PrivateDocumentService(
    document_store,
    PRIVATE_DOCUMENT_DIR,
    PRIVATE_CHROMA_DIR,
)
goal_interpretation_store = GoalInterpretationStore(PLAN_DB)
goal_interpretation_service = GoalInterpretationService(
    goal_interpretation_store,
    document_store,
)
onboarding_store = OnboardingStore(PLAN_DB)
onboarding_service = OnboardingService(
    onboarding_store,
    backend,
    goal_interpretation_store,
)
workload_store = WorkloadStore(PLAN_DB)
workload_service = WorkloadService(
    store=workload_store,
    onboarding_store=onboarding_store,
    backend=backend,
    goal_interpretations=goal_interpretation_store,
    documents=document_store,
)
feasibility_store = FeasibilityStore(PLAN_DB)
feasibility_service = FeasibilityService(
    store=feasibility_store,
    workload_store=workload_store,
    onboarding_store=onboarding_store,
    backend=backend,
    goal_interpretations=goal_interpretation_store,
    documents=document_store,
)
schedule_service = ScheduleService(backend)
daily_learning_store = DailyLearningStore(PLAN_DB)
daily_learning_service = DailyLearningService(
    backend,
    daily_learning_store,
    document_store,
    document_service,
)
annotated_content_store = AnnotatedContentStore(PLAN_DB)
full_lecture_progress_store = FullLectureProgressStore(PLAN_DB)
source_grounded_v4_store = SourceGroundedLectureV4Store(PLAN_DB)
experience_run_store = ExperienceRunStore(PLAN_DB)
experience_source_store = ExperienceSourceStore(PATHLY_DIR / "pathly_experience_sources.db")
concept_source_link_index = ConceptSourceLinkIndex(PLAN_DB)
private_source_link_resolver = PrivateSourceLinkResolver(goal_interpretation_store, document_store)
source_provenance_backfill = SourceProvenanceBackfill(KG_DIR, KG_JSON)
verified_golden_sources = VerifiedGoldenSourceRegistry(KG_DIR)
experience_goal_sources = ExperienceGoalSourceResolver(PATHLY_DIR)
full_experience_sources = FullExperienceSourceResolver(verified_golden_sources, experience_goal_sources)
public_source_registry = PublicConceptSourceRegistry(PLAN_DB, KG_DIR)
public_source_resolver = PublicThenReviewedResolver(public_source_registry, full_experience_sources)
annotated_content_service = AnnotatedContentService(
    backend,
    annotated_content_store,
    daily_learning_service,
)
learning_loop_store = LearningLoopStore(PLAN_DB)
learning_loop_service = LearningLoopService(
    backend, daily_learning_service, daily_learning_store, learning_loop_store
)
session_store = AnonymousSessionStore(PLAN_DB)
TEST_COMPAT_MODE = os.getenv("PATHLY_TEST_COMPAT", "false").lower() in {
    "1", "true", "yes", "on",
}
REQUIRE_SESSION_AUTH = (
    False
    if TEST_COMPAT_MODE
    else os.getenv("PATHLY_REQUIRE_SESSION_AUTH", "true").lower()
    in {"1", "true", "yes", "on"}
)
SESSION_COOKIE_SECURE = os.getenv("PATHLY_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
LECTURE_V4_ENABLED = os.getenv("PATHLY_LECTURE_V4_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
# Explicit local-only presentation switch. Production keeps per-session ownership.
LOCAL_DEMO_SHARED_MODE = os.getenv("PATHLY_LOCAL_DEMO_SHARED_MODE", "false").lower() in {"1", "true", "yes", "on"}
LOCAL_DEMO_USER_ID = os.getenv("PATHLY_LOCAL_DEMO_USER_ID", "local-demo-learner")
DEMO_USERS_ENABLED = os.getenv("PATHLY_DEMO_USERS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
security_logger = logging.getLogger("uvicorn.error")
_v4_jobs_lock = threading.Lock()
_v4_active_jobs: set[tuple[str, str, int]] = set()
V4_MAX_CONCURRENT_JOBS = max(1, int(os.getenv("PATHLY_V4_MAX_CONCURRENT_JOBS", "1")))
_v4_generation_slots = threading.BoundedSemaphore(V4_MAX_CONCURRENT_JOBS)
# A complete Day 1 can contain several independent sections.  Each section may
# make one lecture call plus one assessment call, and the worker deliberately
# limits concurrency to avoid rate-limit spikes.  180 seconds was therefore
# shorter than a healthy live Day 1 on GPT-5.4 and caused polling requests to
# mark an *active* job as interrupted.  This is only a stale-job safety net;
# active in-memory jobs must never be invalidated by elapsed wall time.
V4_JOB_TIMEOUT_SECONDS = int(os.getenv("PATHLY_V4_JOB_TIMEOUT_SECONDS", "720"))


class ProfilePayload(BaseModel):
    user_id: str | None = None
    name: str = "Pathly Learner"
    academic_level: str = "undergraduate"
    domain: str = "computer science"
    goal_text: str = "Learn neural network basics"
    target_days: int = Field(default=7, ge=1, le=90)
    daily_minutes: int = Field(default=75, ge=15, le=480)
    prior_knowledge_level: int = Field(default=3, ge=1, le=5)
    math_foundation: int = Field(default=3, ge=1, le=5)
    programming_foundation: int = Field(default=4, ge=1, le=5)
    self_regulation: int = Field(default=3, ge=1, le=5)
    interest_tags: list[str] = Field(default_factory=lambda: ["neural networks"])
    preferred_style: str = "intuitive_with_code"
    motivation_level: int = Field(default=4, ge=1, le=5)
    confidence_level: int = Field(default=3, ge=1, le=5)
    anxiety_level: int = Field(default=2, ge=1, le=5)
    known_topics: list[str] = Field(default_factory=list)
    preferred_examples: list[str] = Field(default_factory=lambda: ["code", "visual analogy"])
    pace_preference: str = "medium"
    cognitive_traits: dict[str, Any] = Field(default_factory=dict)
    affective_defaults: dict[str, Any] = Field(default_factory=dict)
    inference_records: dict[str, Any] = Field(default_factory=dict)
    profile_version: int = Field(default=2, ge=2)


class ProfilePatch(BaseModel):
    name: str | None = None
    goal_text: str | None = None
    target_days: int | None = Field(default=None, ge=1, le=90)
    daily_minutes: int | None = Field(default=None, ge=15, le=480)
    math_foundation: int | None = Field(default=None, ge=1, le=5)
    programming_foundation: int | None = Field(default=None, ge=1, le=5)
    preferred_style: str | None = None
    confidence_level: int | None = Field(default=None, ge=1, le=5)
    known_topics: list[str] | None = None
    preferred_examples: list[str] | None = None
    cognitive_traits: dict[str, Any] | None = None
    affective_defaults: dict[str, Any] | None = None
    inference_records: dict[str, Any] | None = None
    profile_version: int | None = Field(default=None, ge=2)


class PlanPayload(BaseModel):
    user_id: str
    goal_text: str | None = None
    path_id: str | None = None
    confirmed_mappings: dict[str, str] = Field(default_factory=dict)


class DeletePathPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)


class DocumentOwnerPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)


class DocumentSelectionPayload(BaseModel):
    document_id: str
    role: str = "supplementary"
    required: bool | None = None
    included_pages: list[int] = Field(default_factory=list)
    excluded_pages: list[int] = Field(default_factory=list)
    included_sections: list[str] = Field(default_factory=list)
    excluded_sections: list[str] = Field(default_factory=list)


class DocumentScopePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    role: str = "supplementary"
    required: bool | None = None
    included_pages: list[int] = Field(default_factory=list)
    excluded_pages: list[int] = Field(default_factory=list)
    included_sections: list[str] = Field(default_factory=list)
    excluded_sections: list[str] = Field(default_factory=list)


class GoalInterpretationPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    goal_text: str = Field(min_length=1, max_length=2000)
    source_mode: str = "private_plus_kg"
    documents: list[DocumentSelectionPayload] = Field(default_factory=list)


class GoalInterpretationConfirmPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    confirmed_mappings: dict[str, str] = Field(default_factory=dict)
    accepted_private_concepts: list[str] = Field(default_factory=list)
    rejected_private_concepts: list[str] = Field(default_factory=list)
    rejected_terms: list[str] = Field(default_factory=list)


class ControlledEvaluationRunPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    goal_text: str = Field(min_length=1, max_length=2000)
    system_version: str = Field(min_length=2, max_length=20)
    # Kept as an optional legacy input for reproducibility of old artifacts.
    # New controlled comparisons deliberately let each Planning Agent recommend
    # its own daily workload.
    daily_minutes: int | None = Field(default=None, ge=15, le=480)
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    force_regenerate: bool = True
    allow_cache: bool = False
    deadline_days: int | None = Field(default=None, ge=1, le=3650)
    allow_fallback_preview: bool = False


class ControlledEvaluationComparisonPayload(BaseModel):
    """One fixed input used to run the four end-to-end ablation systems."""
    user_id: str = Field(min_length=1, max_length=200)
    goal_text: str = Field(min_length=1, max_length=2000)
    daily_minutes: int | None = Field(default=None, ge=15, le=480)
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    force_regenerate: bool = True
    allow_cache: bool = False
    deadline_days: int | None = Field(default=None, ge=1, le=3650)
    include_matched_diagnostic: bool = True
    allow_fallback_preview: bool = False


class OnboardingDraftCreatePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    goal_text: str = Field(min_length=1, max_length=2000)
    name: str | None = Field(default=None, max_length=200)
    academic_level: str | None = Field(default=None, max_length=200)
    domain: str | None = Field(default=None, max_length=200)
    goal_interpretation_id: str | None = None


class OnboardingDraftPatchPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    answers: dict[str, Any] = Field(default_factory=dict)
    current_step: int | None = Field(default=None, ge=0)
    goal_text: str | None = Field(default=None, min_length=1, max_length=2000)


class KnowledgeMapReviewPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    reviewed_concepts: list[dict[str, Any]] = Field(default_factory=list)
    excluded_concept_ids: list[str] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class OnboardingGoalRevisionPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    goal_text: str = Field(min_length=1, max_length=2000)
    goal_interpretation_id: str | None = None

class OnboardingProfileConfirmPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    cognitive_overrides: dict[str, Any] = Field(default_factory=dict)
    affective_overrides: dict[str, Any] = Field(default_factory=dict)
    target_mastery_overrides: dict[str, Any] = Field(default_factory=dict)
    preference_overrides: dict[str, Any] = Field(default_factory=dict)
    current_affective_state_overrides: dict[str, Any] = Field(default_factory=dict)


class WorkloadEstimatePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)


class FeasibilityDecisionCreatePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    estimate_id: str = Field(min_length=1, max_length=200)
    requested_days: int | None = Field(default=None, ge=1, le=60)
    deadline: str | None = None
    max_available_daily_minutes: int | None = Field(default=None, ge=1, le=1440)


class FeasibilityDecisionPatchPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    requested_days: int | None = Field(default=None, ge=1, le=60)
    deadline: str | None = None
    max_available_daily_minutes: int | None = Field(default=None, ge=1, le=1440)
    selected_strategy: str | None = None
    scope_remove_concept_ids: list[str] | None = None
    scope_change_decision: str | None = None

class PlanActivationPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    start_date: str | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)


class DayReschedulePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    new_date: str
    confirm_deadline_impact: bool = False


class DailyContentGeneratePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    force: bool = False

class AnnotatedSessionGeneratePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    force: bool = False

class AnnotatedReadingCompletePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    status: str = "completed"
    response: dict[str, Any] | str | None = None

class AnnotatedExerciseSubmitPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    answer: dict[str, Any] | str = Field(default_factory=dict)

class FullLectureSectionProgressPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    completed: bool

class FullLectureSectionRegeneratePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    topic_override: str | None = Field(default=None, max_length=200)
class SourceGroundedLectureV4GeneratePayload(BaseModel):
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    force: bool = False

class SourceGroundedLectureV4SectionPayload(BaseModel):
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    completed: bool = True

class SourceGroundedLectureV4ExerciseAnswerPayload(BaseModel):
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    answer_id: str = Field(min_length=1, max_length=200)

class SourceGroundedLectureV4OpenAnswerPayload(BaseModel):
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=5000)


class StudyBlockProgressPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    status: str = "in_progress"
    progress: float | None = Field(default=None, ge=0, le=1)
    actual_seconds: int = Field(default=0, ge=0)
    answer: dict[str, Any] | str | None = None
    feedback: dict[str, Any] | None = None

class StudyBlockCompletePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    actual_seconds: int = Field(default=0, ge=0)
    answer: dict[str, Any] | str | None = None

class StudyBlockFeedbackPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    feedback_type: str
    note: str | None = Field(default=None, max_length=2000)

class StudyBlockRegeneratePayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)

class DailyFeedbackPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    feedback_type: str
    concept_ids: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=2000)
    content_progress: float | None = Field(default=None, ge=0, le=1)


class ChatPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    plan_id: str = Field(min_length=1, max_length=200)
    day: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=8000)
    intent: str | None = None
    content_id: str | None = None
    current_block_id: str | None = None
    completed_block_ids: list[str] = Field(default_factory=list)
    current_resource_id: str | None = None


class QuizAnswerPayload(BaseModel):
    question_id: str
    answer: str
    confidence: int = Field(default=3, ge=1, le=5)
    time_seconds: int = Field(default=0, ge=0)


class QuizAttemptPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    answers: list[QuizAnswerPayload]
    duration_seconds: int = Field(default=0, ge=0)


class AdaptationProposalPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)


class AdaptationDecisionPayload(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    decision: str
    modifications: dict[str, Any] = Field(default_factory=dict)

app = FastAPI(
    title="Pathly API",
    version="0.1.0",
    description="Learner-facing service for Pathly. The 8501 Streamlit app remains a separate developer console.",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def envelope(*, data: Any, request_id: str, mode: str = "live") -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "meta": {
            "request_id": request_id,
            "mode": mode,
            "generated_at": utc_now(),
        },
    }


def error_envelope(*, code: str, message: str, request_id: str, details: Any = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "details": details},
        "meta": {"request_id": request_id, "generated_at": utc_now()},
    }


def request_id_for(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


@app.middleware("http")
async def request_context(request: Request, call_next):
    started = time.perf_counter()
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.user_id = None
    path = request.url.path
    public_api = path in {
        "/api/health",
        "/api/capabilities",
        "/api/sessions/anonymous",
        "/api/sessions/fresh-walkthrough",
    }
    if REQUIRE_SESSION_AUTH and path.startswith("/api/") and not public_api:
        session = session_store.resolve(request.cookies.get(COOKIE_NAME))
        if LOCAL_DEMO_SHARED_MODE:
            session = {"session_id": "local-demo", "user_id": LOCAL_DEMO_USER_ID}
        if not session:
            return JSONResponse(
                status_code=401,
                content=error_envelope(
                    code="session_required",
                    message="An anonymous Pathly session is required.",
                    request_id=request.state.request_id,
                ),
            )
        request.state.user_id = session["user_id"]
        claimed = request.query_params.get("user_id")
        parts = path.split("/")
        if len(parts) > 3 and parts[2] == "users":
            claimed = parts[3]
        elif len(parts) > 3 and parts[2] == "profiles":
            claimed = parts[3]
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.body()
            async def replay_body():
                return {"type": "http.request", "body": body, "more_body": False}
            request._receive = replay_body
            try:
                claimed = (json.loads(body or b"{}") or {}).get("user_id") or claimed
            except (ValueError, TypeError):
                pass
        controlled_eval_request = path.startswith("/api/controlled-evaluation/")
        controlled_eval_demo_owner = (
            controlled_eval_request
            and _controlled_evaluation_enabled()
            and claimed in {fixture["user_id"] for fixture in NORMAL_PROFILE_FIXTURES.values()}
        )
        if claimed and claimed != session["user_id"] and not controlled_eval_demo_owner:
            return JSONResponse(
                status_code=403,
                content=error_envelope(
                    code="owner_mismatch",
                    message="This resource belongs to another anonymous session.",
                    request_id=request.state.request_id,
                ),
            )
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and request.url.netloc not in origin:
                return JSONResponse(
                    status_code=403,
                    content=error_envelope(
                        code="origin_mismatch",
                        message="Cross-origin state changes are not allowed.",
                        request_id=request.state.request_id,
                    ),
                )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if path == "/" or path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-store"
    user_hash = (
        hashlib.sha256(request.state.user_id.encode()).hexdigest()[:12]
        if request.state.user_id else None
    )
    security_logger.info(json.dumps({
        "event": "http_request", "request_id": request.state.request_id,
        "method": request.method, "path": path, "status": response.status_code,
        "duration_ms": round((time.perf_counter()-started)*1000, 2),
        "user_hash": user_hash,
    }))
    return response


@app.post("/api/sessions/anonymous", status_code=201)
async def create_anonymous_session(request: Request):
    existing = session_store.resolve(request.cookies.get(COOKIE_NAME))
    if existing:
        token = None
        record = existing
    else:
        token, record = await run_in_threadpool(session_store.create)
    if LOCAL_DEMO_SHARED_MODE:
        # Cookies remain per-browser; the local presentation uses one stable learner.
        record = {**record, "user_id": LOCAL_DEMO_USER_ID, "local_demo_shared": True}
    response = JSONResponse(
        status_code=200 if existing else 201,
        content=envelope(data=record, request_id=request_id_for(request)),
    )
    if token:
        response.set_cookie(
            COOKIE_NAME, token, httponly=True, samesite="lax",
            secure=SESSION_COOKIE_SECURE, max_age=30*24*60*60, path="/",
        )
    return response


def _fresh_workspace_audit(user_id: str) -> dict[str, Any]:
    """Prove that a newly issued walkthrough identity has no inherited state."""
    profile_exists = backend.get_profile_record(user_id) is not None
    plans = backend.plans.list_plans(user_id)
    drafts = onboarding_store.list(user_id)
    cache_tables = (
        "source_grounded_lecture_v4",
        "source_grounded_lecture_v4_progress",
        "source_grounded_lecture_v4_exercise_answers",
    )
    cache_entries = 0
    with sqlite3.connect(PLAN_DB) as conn:
        existing_tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for table in cache_tables:
            if table in existing_tables:
                cache_entries += int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)
                    ).fetchone()[0]
                )
    audit = {
        "profile_exists": profile_exists,
        "plan_count": len(plans),
        "onboarding_draft_count": len(drafts),
        "content_cache_count": cache_entries,
    }
    audit["empty_workspace_verified"] = not profile_exists and all(
        audit[key] == 0
        for key in ("plan_count", "onboarding_draft_count", "content_cache_count")
    )
    return audit


@app.post("/api/sessions/fresh-walkthrough", status_code=201)
async def create_fresh_walkthrough_session(request: Request):
    """Always issue a new owner for the real onboarding walkthrough.

    This deliberately bypasses demo fixtures and never reuses the current cookie.
    """
    token, record = await run_in_threadpool(session_store.create)
    audit = await run_in_threadpool(_fresh_workspace_audit, record["user_id"])
    if not audit["empty_workspace_verified"]:
        raise HTTPException(status_code=409, detail="Fresh workspace isolation check failed.")
    data = {
        **record,
        **audit,
        "walkthrough_type": "fresh_user",
        "display_name": "New Learner",
        "fixture_injected": False,
    }
    response = JSONResponse(
        status_code=201,
        content=envelope(data=data, request_id=request_id_for(request)),
    )
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax",
        secure=SESSION_COOKIE_SECURE, max_age=30*24*60*60, path="/",
    )
    return response


def _demo_user_summary(key: str, fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "user_id": fixture["user_id"],
        "display_name": fixture["display_name"],
        "level": "foundation" if key == "foundation_learner" else "advanced",
    }


def _ensure_demo_profile(fixture: dict[str, Any]) -> dict[str, Any]:
    user_id = str(fixture["user_id"])
    existing = backend.profiles.get_profile(user_id)
    cognitive = fixture["cognitive_traits"]
    affective = fixture["affective_defaults"]
    values = {
        "user_id": user_id,
        "name": fixture["display_name"],
        "goal_text": "Learn the foundations of neural networks",
        "target_days": 5,
        "daily_minutes": 60,
        "prior_knowledge_level": cognitive["general_learning_foundation"],
        "math_foundation": cognitive["mathematical_ability"],
        "programming_foundation": cognitive["programming_ability"],
        "self_regulation": affective["self_regulation"],
        "interest_tags": affective["interest_tags"],
        "preferred_style": affective["learning_style"],
        "preferred_examples": affective["preferred_examples"],
        "pace_preference": affective["pace_preference"],
        "cognitive_traits": cognitive,
        "affective_defaults": affective,
        "profile_version": fixture.get("profile_version", 1),
    }
    profile = profile_from_payload(values, existing)
    return backend.save_profile(profile, values)


def _controlled_evaluation_enabled() -> bool:
    return DEMO_USERS_ENABLED and not LOCAL_DEMO_SHARED_MODE


def _controlled_evaluation_goals() -> list[dict[str, Any]]:
    return [
        {
            "goal_id": item["id"],
            "goal_text": item["goal"],
            "short_label": item["id"],
            "eligible_for_full_experience": True,
        }
        for item in TARGET_GOALS
    ]


def _controlled_goal_spec(goal_text: str) -> dict[str, Any]:
    normalized = " ".join(str(goal_text or "").strip().split()).lower()
    for item in TARGET_GOALS:
        if normalized == item["goal"].strip().lower():
            return item
    match = resolve_goal_chain(goal_text)
    if match:
        goal_id, _ = match
        for item in TARGET_GOALS:
            if item["id"] == goal_id:
                return item
    if verified_goal_concepts_for_goal(goal_text):
        return next(item for item in TARGET_GOALS if item["id"] == "xor")
    raise HTTPException(status_code=400, detail="Goal is not approved for controlled evaluation")


def _learner_source_tier(profile: dict[str, Any] | None) -> str:
    """Map a learner treatment to the curated source tier without changing facts."""
    profile = profile or {}
    name = str(profile.get("display_name") or profile.get("user_type") or "").lower()
    traits = profile.get("cognitive_traits") or {}
    values = [int(value) for value in traits.values() if str(value).isdigit()]
    return "advanced" if "advanced" in name or (values and sum(values) / len(values) >= 4) else "foundation"


def _controlled_source_input(goal_spec: dict[str, Any], learner_tier: str = "shared") -> tuple[str, dict[str, Any]]:
    goal_text = goal_spec["goal"]
    verified = verified_goal_concepts_for_goal(goal_text)
    if verified:
        concept_name = verified[-1]
        link = full_experience_sources.resolve(concept_id=concept_name, concept_name=concept_name, learner_tier=learner_tier)
        if link:
            link = {**link, "concept_id": link.get("concept_id") or concept_name, "concept_name": link.get("concept_name") or concept_name}
            return concept_name, link
        raise ValueError("verified source link unavailable")
    match = resolve_goal_chain(goal_text)
    if not match:
        raise ValueError("approved goal chain unavailable")
    _, spec = match
    concept_id = spec["canonical_path"][-1]
    concept_name = spec["display_names"][-1]
    link = full_experience_sources.resolve(concept_id=concept_id, concept_name=concept_name, learner_tier=learner_tier)
    if link:
        link = {**link, "concept_id": link.get("concept_id") or concept_id, "concept_name": link.get("concept_name") or concept_name}
        return concept_name, link
    raise ValueError("approved scoped source link unavailable")


def _controlled_profile_snapshot(user_id: str, goal_text: str, daily_minutes: int | None = None) -> dict[str, Any]:
    fixture = next((value for value in NORMAL_PROFILE_FIXTURES.values() if value["user_id"] == user_id), None)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Controlled evaluation profile not found")
    profile = copy.deepcopy(_ensure_demo_profile(fixture))
    profile["goal_text"] = goal_text
    if daily_minutes is not None:
        profile["daily_minutes"] = int(daily_minutes)
    else:
        profile.pop("daily_minutes", None)
    return profile


def _controlled_openai_json(request: dict[str, Any], *, max_output_tokens: int, temperature: float = 0.2, attempts: int = 3) -> dict[str, Any]:
    """Call the live evaluator/generator with bounded retries and JSON validation."""
    from openai import OpenAI
    last_error: Exception | None = None
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=float(os.getenv("PATHLY_CONTENT_TIMEOUT_SECONDS", "75")),
        max_retries=0,
    )
    for attempt in range(max(1, attempts)):
        try:
            response = client.responses.create(
                model=os.getenv("PATHLY_CONTROLLED_EVAL_MODEL", "gpt-5.4"),
                input=json.dumps(request, ensure_ascii=False),
                text={"format": {"type": "json_object"}},
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            parsed = json.loads(str(response.output_text or "{}"))
            if not isinstance(parsed, dict):
                raise ValueError("live_generation_invalid_json_object")
            return parsed
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max(1, attempts):
                time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"live_generation_failed_after_{max(1, attempts)}_attempts:{type(last_error).__name__}") from last_error


def _controlled_openai_text(prompt: str, *, max_output_tokens: int, temperature: float = 0.2, attempts: int = 3) -> str:
    """Call the live model for the natural-language V0-V2 contracts."""
    from openai import OpenAI
    last_error: Exception | None = None
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=float(os.getenv("PATHLY_CONTENT_TIMEOUT_SECONDS", "75")),
        max_retries=0,
    )
    for attempt in range(max(1, attempts)):
        try:
            response = client.responses.create(
                model=os.getenv("PATHLY_CONTROLLED_EVAL_MODEL", "gpt-5.4"),
                input=prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            text = str(response.output_text or "").strip()
            if len(text) < 80:
                raise ValueError("live_generation_empty_or_too_short")
            return text
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max(1, attempts):
                time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"live_generation_failed_after_{max(1, attempts)}_attempts:{type(last_error).__name__}") from last_error


def _controlled_profile_summary(profile: dict[str, Any]) -> str:
    cognitive = profile.get("cognitive_traits") or {}
    affective = profile.get("affective_defaults") or {}
    return (
        f"Mathematical foundation: {cognitive.get('mathematical_ability', 3)}/5; "
        f"programming foundation: {cognitive.get('programming_ability', 3)}/5; "
        f"general learning foundation: {cognitive.get('general_learning_foundation', 3)}/5; "
        f"learning style: {affective.get('learning_style', 'balanced')}; "
        f"preferred examples: {', '.join(affective.get('preferred_examples') or ['general'])}; "
        f"pace preference: {affective.get('pace_preference', 'steady')}."
    )


def _controlled_heading_body(markdown: str, heading: str) -> str:
    pattern = rf"(?ims)^##\s+{re.escape(heading)}\s*$\s*(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown or "")
    return match.group(1).strip() if match else ""


def _controlled_int_from_markdown(markdown: str, heading: str, default: int) -> int:
    text = _controlled_heading_body(markdown, heading)
    match = re.search(r"\b(\d{1,5})\s*(?:minutes?|mins?)\b", text, flags=re.I)
    if not match and heading.lower().endswith("days"):
        match = re.search(r"\b(\d{1,4})\s*days?\b", text, flags=re.I)
    if not match:
        match = re.search(r"\b(\d{1,5})\b", text)
    return int(match.group(1)) if match else int(default)


def _normalise_controlled_plan_timing(plan: dict[str, Any], deadline_days: int | None = None) -> dict[str, Any]:
    """Keep the timing cards internally consistent across every ablation.

    The model is allowed to estimate workload, but the derived day count and
    the Day 1 display must use one deterministic calculation.  This prevents
    a natural-language estimate (for example, 120 minutes over 3 days) from
    being displayed alongside an unrelated legacy Day 1 cap (20 minutes).
    """
    daily = max(1, int(plan.get("recommended_daily_minutes") or 50))
    total = max(1, int(plan.get("estimated_total_minutes") or daily))
    days = max(1, (total + daily - 1) // daily)
    day_one = max(10, min(daily, (total + days - 1) // days))
    plan["recommended_daily_minutes"] = daily
    plan["estimated_total_minutes"] = total
    plan["estimated_days"] = days
    plan["session_minutes"] = day_one
    plan["day_1_minutes"] = day_one
    plan["feasibility"] = {
        "status": "feasible" if not deadline_days or days <= int(deadline_days) else "infeasible",
        "deadline_days": deadline_days,
    }
    return plan


def _normalise_controlled_concept_path(raw_path: Any, fallback: list[str]) -> list[str]:
    """Convert V3 planner path items into the string contract used by V4."""
    values: list[str] = []
    for item in raw_path or []:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("concept") or item.get("concept_name") or item.get("name") or item.get("title")
            if name:
                values.append(str(name).strip())
    return values or list(fallback)


def _controlled_natural_plan_prompt(*, goal: str, deadline_days: int | None, profile_summary: str | None, kg_path: list[str] | None) -> str:
    deadline = f"{deadline_days} days" if deadline_days else "not specified"
    profile_block = f"\nAnonymous learner profile:\n{profile_summary}\n" if profile_summary else ""
    if kg_path is None:
        sequence_heading = "## Recommended learning sequence"
        kg_block = ""
        rules = "Do not assume or claim access to a knowledge graph, curriculum, teaching assets, documents, sources, PDFs, or page numbers."
    else:
        sequence_heading = "## Approved concept path\n## Prerequisite rationale"
        kg_block = "\nApproved concepts in prerequisite order:\n" + " → ".join(kg_path) + "\n"
        rules = "Use only the supplied approved concepts and preserve their prerequisite order. Do not claim access to teaching assets, source documents, PDFs, page numbers, citations, or retrieved evidence."
    profile_heading = "\n## Profile-informed decisions\n" if profile_summary else ""
    profile_requirements = (
        "Under Profile-informed decisions, explain concrete choices for prerequisite recap, explanation order, terminology, formula support, examples, code scaffolding, checkpoints, exercise difficulty, and workload."
        if profile_summary else ""
    )
    return f"""You are a {'personalised ' if profile_summary else ''}learning-planning assistant.

A learner wants to achieve this learning goal:

{goal}

Preferred completion window: {deadline}.
{profile_block}{kg_block}
Create a practical learning plan using {'the approved concept order and ' if kg_path is not None else ''}your general tutoring judgement.

Write in natural language using exactly these headings:

## Goal interpretation
{sequence_heading}
## Estimated total study time
## Estimated number of study days
## Recommended daily study time
## Day 1 plan
## Suggested remaining-day progression
{profile_heading}## Feasibility note

Requirements:
- State one estimated total study time in minutes, one estimated number of study days, and one recommended daily study time in minutes. Decide these from the learning goal and the information you are allowed to use.
- Give a concrete Day 1 focus, approximate Day 1 duration consistent with your recommended daily study time, and activities.
- If the preferred completion window is unrealistic, explain why and suggest alternatives.
- {rules}
- {profile_requirements}
- Do not cite sources or mention prompts, system versions, evaluation, experiments, or internal processes.
"""


def _controlled_planning_unit(goal_spec: dict[str, Any], profile: dict[str, Any], system: dict[str, Any], daily_minutes: int | None = None, deadline_days: int | None = None, force_fallback: bool = False) -> dict[str, Any]:
    """Version-scoped planning contract used by the ablation runner.

    The important property is input isolation: each ablation receives only the
    components enabled by its contract. This plan object is passed unchanged to
    the content stage and retained in the run artifact.
    """
    catalog = resolve_goal_chain(goal_spec["goal"])
    kg_path = list((catalog or (None, {}))[1].get("display_names") or verified_goal_concepts_for_goal(goal_spec["goal"]) or [])
    style = (profile.get("affective_defaults") or {}).get("learning_style", "balanced") if system["profile"] else None
    pace = (profile.get("affective_defaults") or {}).get("pace_preference", "steady") if system["profile"] else None
    path = kg_path if system["kg"] else []
    core = path[-1] if path else goal_spec["goal"]
    concept_count = max(1, len(path) if path else 3)
    ability = int((profile.get("cognitive_traits") or {}).get("general_learning_foundation") or 3) if system["profile"] else 3
    pace_factor = 0.82 if system["profile"] and ability >= 4 else (1.18 if system["profile"] and ability <= 2 else 1.0)
    estimated_total = max(30, int(round(concept_count * 25 * pace_factor)))
    recommended_daily = int(daily_minutes) if daily_minutes is not None else (70 if system["profile"] and ability >= 4 else (40 if system["profile"] and ability <= 2 else 50))
    estimated_days = max(1, (estimated_total + recommended_daily - 1) // recommended_daily)
    plan = {
        "planning_agent": f"controlled_eval_{system['version'].lower()}_planning_v2",
        "goal_text": goal_spec["goal"],
        "core_concept": core,
        "prerequisite_path": path,
        "recommended_daily_minutes": recommended_daily,
        "session_minutes": max(10, min(recommended_daily, (estimated_total + estimated_days - 1) // estimated_days)),
        "estimated_total_minutes": estimated_total,
        "estimated_days": estimated_days,
        "concept_count": concept_count,
        "feasibility": {"status": "feasible" if not deadline_days or estimated_days <= deadline_days else "infeasible", "deadline_days": deadline_days},
        "learner_treatment": {"style": style, "pace": pace} if system["profile"] else {},
        "planning_constraints": {
            "profile": bool(system["profile"]), "kg": bool(system["kg"]),
            "teaching_assets": bool(system["teaching_assets"]), "source_grounding": bool(system["source_grounding"]),
        },
        "planning_rationale": (
            "Use only the goal and a generic learning sequence."
            if system["version"] == "V0" else
            "Adapt sequence and pacing to the learner profile without adding KG facts."
            if system["version"] == "V1" else
            "Follow the approved KG prerequisite path before teaching the target mechanism."
            if system["version"] == "V2" else
            "Follow the approved KG path and allocate source-grounded teaching assets to the core unit."
        ),
        "output_format": "lecture_v4_json" if system["version"] == "V3" else "natural_markdown",
        "prompt_version": f"controlled-eval-{system['version'].lower()}-planning-prompt-v2",
    }
    if system["version"] != "V3":
        prompt = _controlled_natural_plan_prompt(
            goal=goal_spec["goal"], deadline_days=deadline_days,
            profile_summary=_controlled_profile_summary(profile) if system["profile"] else None,
            kg_path=kg_path if system["kg"] else None,
        )
        plan["planning_prompt"] = prompt
        if not force_fallback and os.getenv("OPENAI_API_KEY") and os.getenv("PATHLY_CONTROLLED_EVAL_LIVE", "true").lower() == "true":
            markdown = _controlled_openai_text(prompt, max_output_tokens=2200, attempts=3)
            plan["planning_agent"] = f"controlled_eval_{system['version'].lower()}_planning_live"
            plan["plan_markdown"] = markdown
            plan["estimated_total_minutes"] = _controlled_int_from_markdown(markdown, "Estimated total study time", estimated_total)
            plan["estimated_days"] = _controlled_int_from_markdown(markdown, "Estimated number of study days", estimated_days)
            plan["recommended_daily_minutes"] = _controlled_int_from_markdown(markdown, "Recommended daily study time", recommended_daily)
            _normalise_controlled_plan_timing(plan, deadline_days)
            plan["day_1_plan_markdown"] = _controlled_heading_body(markdown, "Day 1 plan") or markdown
            plan["day_1_focus"] = (plan["day_1_plan_markdown"].splitlines() or [goal_spec["goal"]])[0].lstrip("- ").strip()
            plan["profile_informed_decisions"] = _controlled_heading_body(markdown, "Profile-informed decisions") if system["profile"] else ""
        elif force_fallback:
            plan["plan_markdown"] = f"## Goal interpretation\n{goal_spec['goal']}\n\n## Estimated total study time\n{estimated_total} minutes\n\n## Estimated number of study days\n{estimated_days}\n\n## Recommended daily study time\n{recommended_daily} minutes\n\n## Day 1 plan\nReview the goal and begin with the first core idea.\n\n## Feasibility note\nFallback preview only."
            plan["day_1_plan_markdown"] = _controlled_heading_body(plan["plan_markdown"], "Day 1 plan")
            plan["day_1_focus"] = goal_spec["goal"]
        return _normalise_controlled_plan_timing(plan, deadline_days)
    plan["v3_prompt_contract"] = """You are Pathly's source-grounded personalised learning-planning agent. Respect direct prerequisites, adapt workload to the anonymous learner profile, use only approved KG concepts, teaching assets and source coverage, calculate estimated total study minutes and estimated study days, and never fabricate evidence."""
    if not force_fallback and os.getenv("OPENAI_API_KEY") and os.getenv("PATHLY_CONTROLLED_EVAL_LIVE", "true").lower() == "true":
        allowed = {"profile": bool(system["profile"]), "kg": bool(system["kg"]), "teaching_assets": bool(system["teaching_assets"]), "source_grounding": bool(system["source_grounding"])}
        prompt = {
            "role": "Pathly source-grounded personalised learning-planning agent",
            "task": "Create one auditable source-grounded learning plan as JSON.",
            "goal": goal_spec["goal"], "deadline_days": deadline_days,
            "allowed_components": allowed,
            "profile": profile if system["profile"] else None,
            "approved_kg_path": kg_path if system["kg"] else [],
            "required_keys": ["core_concept", "prerequisite_path", "session_minutes", "recommended_daily_minutes", "estimated_total_minutes", "estimated_days", "rationale"],
            "rules": ["Respect direct prerequisites", "Use only approved KG concepts, teaching assets and source coverage", "Never fabricate evidence or citations", "Return JSON only"],
        }
        generated = _controlled_openai_json(prompt, max_output_tokens=1800, attempts=3)
        plan["planning_agent"] = f"controlled_eval_{system['version'].lower()}_planning_live"
        plan["core_concept"] = generated.get("core_concept") or plan["core_concept"]
        plan["prerequisite_path"] = _normalise_controlled_concept_path(
            generated.get("prerequisite_path"), plan["prerequisite_path"]
        )
        plan["session_minutes"] = int(generated.get("session_minutes") or plan["session_minutes"])
        plan["recommended_daily_minutes"] = int(generated.get("recommended_daily_minutes") or plan["recommended_daily_minutes"])
        plan["estimated_total_minutes"] = int(generated.get("estimated_total_minutes") or plan["estimated_total_minutes"])
        plan["estimated_days"] = int(generated.get("estimated_days") or max(1, (plan["estimated_total_minutes"] + plan["recommended_daily_minutes"] - 1) // plan["recommended_daily_minutes"]))
        plan["concept_count"] = int(generated.get("concept_count") or plan["concept_count"])
        plan["planning_rationale"] = generated.get("rationale") or plan["planning_rationale"]
    return _normalise_controlled_plan_timing(plan, deadline_days)


def _controlled_eval_text_unit(goal_spec: dict[str, Any], profile: dict[str, Any], system: dict[str, Any], plan: dict[str, Any], force_fallback: bool = False, diagnostic_concept: str | None = None) -> dict[str, Any]:
    goal_text = goal_spec["goal"]
    catalog = resolve_goal_chain(goal_text)
    path_names = list((catalog or (None, {}))[1].get("display_names") or verified_goal_concepts_for_goal(goal_text) or [])
    concept_name = diagnostic_concept or (path_names[-1] if path_names else goal_text)
    treatment = {
        "learning_style": ((profile.get("affective_defaults") or {}).get("learning_style") or profile.get("preferred_style") or "balanced"),
        "preferred_examples": list((profile.get("affective_defaults") or {}).get("preferred_examples") or profile.get("preferred_examples") or []),
        "pace_preference": ((profile.get("affective_defaults") or {}).get("pace_preference") or profile.get("pace_preference") or "steady"),
    }
    prerequisites = list(plan.get("prerequisite_path") or [])
    profile_summary = _controlled_profile_summary(profile) if system["profile"] else None
    kg_block = (
        f"\nApproved concept path:\n{' → '.join(prerequisites)}\n\n"
        f"Today's concepts in required order:\n{' → '.join(prerequisites[:max(1, min(3, len(prerequisites)))])}\n"
        if system["kg"] else ""
    )
    profile_block = (
        f"\nAnonymous learner profile:\n{profile_summary}\n\n"
        f"Profile-informed planning decisions:\n{plan.get('profile_informed_decisions') or 'Adapt depth, examples, scaffolding, and checkpoints to the profile.'}\n"
        if profile_summary else ""
    )
    headings = "## Core idea\n## Prerequisite recap\n## Intuition\n## Worked example\n## Check yourself\n## Connection to the next concept" if system["kg"] else ("## Core idea\n## Prerequisite recap\n## Intuition\n## Worked example\n## Check yourself\n## Takeaway" if system["profile"] else "## Core idea\n## Intuition\n## Worked example\n## Check yourself\n## Takeaway")
    prompt = f"""You are a {'personalised ' if system['profile'] else ''}machine-learning tutor.

Teach the learner the first day of this learning plan.

Learning goal:
{goal_text}

Day 1 focus:
{plan.get('day_1_focus') or concept_name}

Day 1 plan:
{plan.get('day_1_plan_markdown') or plan.get('plan_markdown') or goal_text}
{profile_block}{kg_block}
Write a complete natural teaching response in Markdown using exactly these headings:

{headings}

Requirements:
- Explain the topic clearly with an intuitive example and one worked example.
- Under “Check yourself”, ask one short question and provide its answer after a line reading “Answer:”.
- {'Teach supplied concepts in order and explain why each is needed before the next.' if system['kg'] else 'Write as a normal high-quality tutoring response.'}
- {'Make profile adaptation visible through teaching choices, not through profile labels.' if system['profile'] else ''}
- Do not mention learner profiles, knowledge graphs, sources, documents, PDFs, citations, prompts, system versions, evaluation, experiments, or internal processes.
- Do not invent citations.
- Do not output JSON, lecture sections, source cards, PDF readers, or V4 objective-exercise schema.
"""
    if not force_fallback and os.getenv("OPENAI_API_KEY") and os.getenv("PATHLY_CONTROLLED_EVAL_LIVE", "true").lower() == "true":
        markdown = _controlled_openai_text(prompt, max_output_tokens=3000, attempts=3)
        if "[object Object]" in markdown or "Build the prerequisite idea" in markdown:
            raise ValueError("controlled_natural_content_placeholder_detected")
        return {
            "contract_version": "controlled-evaluation-natural-content-v2",
            "title": plan.get("day_1_focus") or concept_name,
            "goal": goal_text,
            "content_markdown": markdown,
            "content_agent": f"controlled_eval_{system['version'].lower()}_content_live",
            "content_inputs": {"profile": bool(system["profile"]), "kg": bool(system["kg"]), "teaching_assets": False, "source_grounding": False, "planning_agent": plan["planning_agent"]},
            "source_evidence": [],
            "generation_mode": f"controlled_eval_{system['version'].lower()}_live",
            "planning_agent": plan["planning_agent"],
            "day_1": {"title": f"Day 1 · {goal_text}", "estimated_minutes": int(plan.get("session_minutes") or plan.get("recommended_daily_minutes") or 50), "content_markdown": markdown, "lecture_sections": []},
            "lecture_sections": [],
            "prompt_version": f"controlled-eval-{system['version'].lower()}-content-prompt-v2",
            "output_format": "natural_markdown",
        }
    if force_fallback:
        markdown = f"## Core idea\n{concept_name}\n\n## Intuition\nFallback preview only.\n\n## Worked example\nFallback preview only.\n\n## Check yourself\nWhat is the key idea?\n\nAnswer: See the core idea.\n\n## Takeaway\nFallback preview only."
        return {
            "contract_version": "controlled-evaluation-natural-content-v2", "title": concept_name,
            "goal": goal_text, "content_markdown": markdown,
            "content_agent": f"controlled_eval_{system['version'].lower()}_content_fallback_preview",
            "content_inputs": {"profile": bool(system["profile"]), "kg": bool(system["kg"]), "teaching_assets": False, "source_grounding": False, "planning_agent": plan["planning_agent"]},
            "source_evidence": [], "generation_mode": f"controlled_eval_{system['version'].lower()}_fallback_preview",
            "planning_agent": plan["planning_agent"],
            "day_1": {"title": f"Day 1 · {goal_text}", "estimated_minutes": int(plan.get("session_minutes") or 60), "content_markdown": markdown, "lecture_sections": []}, "lecture_sections": [],
            "prompt_version": f"controlled-eval-{system['version'].lower()}-content-prompt-v2", "output_format": "natural_markdown",
        }
    raise RuntimeError("controlled_natural_content_live_unavailable")


def _controlled_day_from_unit(unit: dict[str, Any], plan: dict[str, Any], goal_text: str) -> dict[str, Any]:
    """Normalize non-V3 output to the same complete-Day contract as V3."""
    path = list(plan.get("prerequisite_path") or []) or [unit.get("title") or goal_text, "Mechanism", "Application"]
    per = max(8, int(plan.get("recommended_daily_minutes") or 50) // max(1, len(path)))
    sections = []
    seeds = list(unit.get("day_sections_seed") or [])
    for index, name in enumerate(path):
        seed = seeds[index] if index < len(seeds) and isinstance(seeds[index], dict) else {}
        sections.append({
            "section_id": f"controlled:{uuid.uuid4().hex[:12]}:{index}",
            "concept_name": name,
            "title": name,
            "estimated_minutes": per,
            "lecture_content": {
                "concept_introduction": seed.get("concept_introduction") or {"hook": name, "explanation": unit.get("summary") if index == len(path)-1 else f"Build the prerequisite idea of {name} before connecting it to the goal.", "mechanism": [unit.get("body") or "Trace the representation, operation, and resulting behavior."], "boundaries": "Use this idea only within the assumptions stated in the lesson."},
                "intuition": seed.get("intuition") or unit.get("body") or "Connect the concept to a concrete example.",
                "worked_example": seed.get("worked_example") or {"problem": f"Apply {name} to the stated learning goal.", "steps": ["Identify the input representation.", "Apply the mechanism.", "Interpret the result."], "solution": unit.get("worked_example") or unit.get("body") or "The mechanism explains the observed result.", "why_it_works": unit.get("check") or "Each step follows from the concept definition."},
                "objective_exercise": seed.get("objective_exercise") or {"questions": [{"question_id": f"q-{uuid.uuid4().hex[:8]}", "prompt": f"Which statement best applies {name} to this goal?", "options": [{"text": unit.get("check") or f"Use {name} to explain the mechanism.", "is_correct": True}, {"text": "The concept changes only the label.", "is_correct": False}, {"text": "The concept works without inputs or assumptions.", "is_correct": False}]}]},
                "summary_connection": seed.get("summary_connection") or {"summary": unit.get("summary") or f"{name} is one step in the path to the goal."},
            },
            "v4_status": "ready",
            "generation_mode": unit.get("generation_mode"),
        })
    unit["day_1"] = {"title": f"Day 1 · {goal_text}", "estimated_minutes": sum(x["estimated_minutes"] for x in sections), "lecture_sections": sections}
    unit["lecture_sections"] = sections
    return unit


def _controlled_eval_v3_unit(goal_spec: dict[str, Any], profile: dict[str, Any], plan: dict[str, Any] | None = None) -> dict[str, Any]:
    learner_tier = _learner_source_tier(profile)
    concept_name, link = _controlled_source_input(goal_spec, learner_tier)
    path = list((plan or {}).get("prerequisite_path") or [concept_name])
    links = []
    for name in path:
        candidate = full_experience_sources.resolve(concept_id=name, concept_name=name, learner_tier=learner_tier)
        if candidate:
            links.append({**candidate, "concept_id": candidate.get("concept_id") or name, "concept_name": candidate.get("concept_name") or name})
    if not links:
        links = [link]
    v3_seed = {
        "contract_version": "full-lecture-v3",
        "plan_id": f"controlled-{uuid.uuid4()}",
        "path_id": f"controlled-{uuid.uuid4()}",
        "day": 1,
        "lecture_sections": [{"section_id": f"controlled:{uuid.uuid4().hex[:12]}:{i}", "concept_id": item["concept_id"], "concept_name": item["concept_name"], "title": item["concept_name"], "estimated_minutes": max(8, int((plan or {}).get("recommended_daily_minutes") or 50) // max(1, len(links)))} for i, item in enumerate(links)],
        "generation_metadata": {"generator_version": "controlled-evaluation-v3-seed", "generation_mode": "controlled_evaluation_seed", "planning_agent": (plan or {}).get("planning_agent")},
        "controlled_planning": plan or {},
    }
    lecture = build_source_grounded_lecture_v4(
        v3_lecture=v3_seed,
        source_links=links,
        daily={"prepared_evidence": []},
        user_id=f"controlled-{uuid.uuid4()}",
        profile=profile,
        verified_registry=full_experience_sources,
        content_model=os.getenv("PATHLY_V4_DAY1_MODEL", os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4")),
    )
    sections = lecture.get("lecture_sections") or []
    refs = [{
        "resource_id": page.get("resource_id"),
        "document_id": page.get("document_id"),
        "page_number": page.get("page_number"),
        "link_id": page.get("link_id"),
    } for section in sections for page in section.get("source_pages") or []]
    return {
        "contract_version": "controlled-evaluation-core-unit-v1",
        "title": concept_name,
        "goal": goal_spec["goal"],
        "lecture": lecture,
        "section": sections[0] if sections else {},
        "day_1": {"title": f"Day 1 · {goal_spec['goal']}", "estimated_minutes": sum(int(s.get("estimated_minutes") or 0) for s in sections), "lecture_sections": sections},
        "lecture_sections": sections,
        "source_evidence": refs,
        "generation_mode": (sections[0].get("generation_mode") if sections else None) or (lecture.get("generation_metadata") or {}).get("generation_mode"),
    }


def _run_controlled_evaluation(payload: ControlledEvaluationRunPayload) -> dict[str, Any]:
    system = get_system_config(payload.system_version)
    goal_spec = _controlled_goal_spec(payload.goal_text)
    # Controlled comparisons intentionally do not feed a daily-time limit to
    # any version. Recommended cadence is a Planning Agent output.
    profile = _controlled_profile_snapshot(payload.user_id, goal_spec["goal"])
    planning_failure: str | None = None
    try:
        planning = _controlled_planning_unit(goal_spec, profile, system, None, payload.deadline_days)
    except Exception as exc:
        planning_failure = f"planning_live_failed:{str(exc)[:220]}"
        if payload.allow_fallback_preview:
            planning = _controlled_planning_unit(goal_spec, profile, system, None, payload.deadline_days, force_fallback=True)
            planning["generation_mode"] = "controlled_evaluation_planning_fallback_preview"
        else:
            planning = _controlled_planning_unit(goal_spec, profile, system, None, payload.deadline_days, force_fallback=True)
            planning["generation_mode"] = "controlled_evaluation_planning_live_failed"
    run_id = f"controlled-{uuid.uuid4()}"
    if system["version"] == "V3":
        unit = _controlled_eval_v3_unit(goal_spec, profile, planning)
        core_output = unit.get("section") or {}
        source_refs = unit.get("source_evidence") or []
        generation_mode = unit.get("generation_mode")
        success = core_output.get("v4_status") == "ready" and generation_mode not in {"fallback", "source_grounded_fallback"}
        failure_reason = core_output.get("failure_reason") or ("controlled_evaluation_generation_failed" if not success else None)
    else:
        try:
            unit = _controlled_eval_text_unit(goal_spec, profile, system, planning)
        except Exception as exc:
            if payload.allow_fallback_preview:
                unit = _controlled_eval_text_unit(goal_spec, profile, system, planning, force_fallback=True)
                unit["generation_mode"] = f"controlled_eval_{system['version'].lower()}_fallback_preview"
            else:
                unit = {"contract_version": "controlled-evaluation-core-unit-v1", "title": goal_spec["goal"], "goal": goal_spec["goal"], "lecture_sections": [], "day_1": {"lecture_sections": []}, "generation_mode": f"controlled_eval_{system['version'].lower()}_live_failed"}
            planning_failure = planning_failure or f"content_live_failed:{str(exc)[:220]}"
        core_output = unit
        source_refs = []
        generation_mode = unit.get("generation_mode")
        live_ok = generation_mode.endswith("_live")
        fallback_preview = generation_mode.endswith("_fallback_preview")
        success = bool(unit.get("content_markdown")) and (live_ok or fallback_preview)
        failure_reason = None if success and not planning_failure else planning_failure or "controlled_evaluation_generation_failed"
    fingerprint_payload = {
        "goal": goal_spec["goal"], "profile": profile, "system": system["version"],
        "model": payload.model or "default",
        "deadline_days": payload.deadline_days, "temperature": float(payload.temperature), "ablation": system["ablation_version"],
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]
    expected_components = {
        "profile": bool(system["profile"]), "kg": bool(system["kg"]),
        "teaching_assets": bool(system["teaching_assets"]), "source_grounding": bool(system["source_grounding"]),
    }
    canonical_components = {
        "V0": {"profile": False, "kg": False, "teaching_assets": False, "source_grounding": False},
        "V1": {"profile": True, "kg": False, "teaching_assets": False, "source_grounding": False},
        "V2": {"profile": True, "kg": True, "teaching_assets": False, "source_grounding": False},
        "V3": {"profile": True, "kg": True, "teaching_assets": True, "source_grounding": True},
    }[system["version"]]
    catalog = resolve_goal_chain(goal_spec["goal"])
    path_names = list((catalog or (None, {}))[1].get("display_names") or verified_goal_concepts_for_goal(goal_spec["goal"]) or [])
    natural_output = system["version"] != "V3"
    day_sections = list(unit.get("lecture_sections") or (unit.get("day_1") or {}).get("lecture_sections") or [])
    estimated_minutes = int((unit.get("day_1") or {}).get("estimated_minutes") or sum(int(item.get("estimated_minutes") or 0) for item in day_sections) or core_output.get("estimated_minutes") or 0)
    foundation = _controlled_profile_snapshot("demo-foundation-learner", goal_spec["goal"])
    advanced = _controlled_profile_snapshot("demo-advanced-learner", goal_spec["goal"])
    profile_dimensions = (
        ("learning_style", lambda p: (p.get("affective_defaults") or {}).get("learning_style")),
        ("preferred_examples", lambda p: tuple((p.get("affective_defaults") or {}).get("preferred_examples") or [])),
        ("pace_preference", lambda p: (p.get("affective_defaults") or {}).get("pace_preference")),
        ("mathematical_ability", lambda p: (p.get("cognitive_traits") or {}).get("mathematical_ability")),
        ("programming_ability", lambda p: (p.get("cognitive_traits") or {}).get("programming_ability")),
    )
    profile_difference = sum(1 for _, getter in profile_dimensions if getter(foundation) != getter(advanced))
    source_integrity = all(bool(ref.get("resource_id") and ref.get("page_number")) for ref in source_refs) if source_refs else not system["source_grounding"]
    checks = {
        "goal_coverage": {"passed": bool(goal_spec.get("id") and core_output), "goal_id": goal_spec.get("id")},
        "schema": {"passed": isinstance(core_output, dict) and (bool(core_output.get("content_markdown")) if natural_output else bool(day_sections)) and (bool(core_output.get("contract_version")) or bool(core_output.get("v4_status"))), "contract_version": core_output.get("contract_version") if isinstance(core_output, dict) else None, "day_sections": len(day_sections), "output_format": core_output.get("output_format") if isinstance(core_output, dict) else None, "v4_fields_present": bool(isinstance(core_output, dict) and core_output.get("v4_status"))},
        "component_contract": {"passed": expected_components == canonical_components, "enabled": expected_components, "expected": canonical_components},
        "source_grounding": {"passed": source_integrity, "source_refs": len(source_refs), "requires_grounding": system["source_grounding"]},
        "live_generation": {"passed": generation_mode.endswith("_live") if system["version"] != "V3" else generation_mode not in {"fallback", "source_grounded_fallback", "controlled_evaluation_seed"}, "generation_mode": generation_mode, "live": generation_mode.endswith("_live"), "fallback_preview": generation_mode.endswith("_fallback_preview")},
        "planning_live_generation": {"passed": planning_failure is None or payload.allow_fallback_preview, "failure": planning_failure, "fallback_preview": planning.get("generation_mode", "").endswith("fallback_preview")},
        "cache_identity": {"passed": bool(fingerprint), "fingerprint": fingerprint, "cache_status": "bypassed" if not payload.allow_cache else "miss"},
        "plan_coverage": {"passed": bool(goal_spec.get("id") and (bool(planning.get("plan_markdown")) if natural_output else bool(path_names))), "path_length": len(planning.get("prerequisite_path") or []), "path": planning.get("prerequisite_path") or [], "not_applicable": False},
        "prerequisite_order": {"passed": len(path_names) == len(set(path_names)) if system["kg"] else True, "path": path_names if system["kg"] else [], "not_applicable": not system["kg"]},
        "time_budget": {"passed": estimated_minutes <= int(planning.get("recommended_daily_minutes") or 0), "estimated_minutes": estimated_minutes, "recommended_daily_minutes": planning.get("recommended_daily_minutes")},
        "planning_workload": {"passed": bool(planning.get("estimated_total_minutes") and planning.get("estimated_days")), "estimated_total_minutes": planning.get("estimated_total_minutes"), "estimated_days": planning.get("estimated_days"), "concept_count": planning.get("concept_count")},
        "day_completeness": {"passed": bool(unit.get("day_1", {}).get("content_markdown")) if natural_output else len(day_sections) >= max(1, len(planning.get("prerequisite_path") or []), 1), "section_count": len(day_sections), "planned_concepts": len(planning.get("prerequisite_path") or []) or 1, "output_format": "natural_markdown" if natural_output else "lecture_v4"},
        "profile_structural_difference": {"passed": profile_difference >= 2, "different_dimensions": profile_difference},
        "version_distinguishability": {"passed": expected_components == canonical_components, "signature": expected_components},
        "source_evidence_integrity": {"passed": source_integrity, "complete_refs": sum(bool(ref.get("resource_id") and ref.get("page_number")) for ref in source_refs), "total_refs": len(source_refs)},
        "reproducibility": {"passed": bool(fingerprint and system["ablation_version"] and payload.model is not None or fingerprint), "fingerprint": fingerprint},
    }
    if not all(item["passed"] for item in checks.values()):
        success = False
        failure_reason = failure_reason or next((f"{name}_failed" for name, item in checks.items() if not item["passed"]), "controlled_evaluation_checks_failed")
    planning_check_names = ("goal_coverage", "plan_coverage", "prerequisite_order", "time_budget", "planning_workload")
    content_check_names = ("schema", "live_generation", "source_evidence_integrity", "day_completeness")
    evaluation_metrics = {
        "planning": {
            "passed": all(checks[name]["passed"] for name in planning_check_names),
            "checks_passed": sum(bool(checks[name]["passed"]) for name in planning_check_names),
            "checks_total": len(planning_check_names),
            "path_length": len(planning.get("prerequisite_path") or []),
            "session_minutes": planning.get("session_minutes"),
        },
        "content": {
            "passed": all(checks[name]["passed"] for name in content_check_names),
            "checks_passed": sum(bool(checks[name]["passed"]) for name in content_check_names),
            "checks_total": len(content_check_names),
            "generation_mode": generation_mode,
            "has_core_output": bool(core_output),
        },
        "grounding": {
            "required": bool(system["source_grounding"]),
            "passed": bool(checks["source_evidence_integrity"]["passed"]),
            "source_refs": len(source_refs),
        },
        "personalization": {"passed": bool(checks["profile_structural_difference"]["passed"]) if system["profile"] else None},
        "overall": {"passed": bool(success), "status": "success" if success else "failed"},
    }
    fallback_preview = generation_mode.endswith("fallback_preview") or planning.get("generation_mode", "").endswith("fallback_preview")
    record = {
        "run_id": run_id,
        "run_type": "controlled_evaluation",
        "user_id": payload.user_id,
        "profile_snapshot": profile,
        "goal": goal_spec["goal"],
        "goal_admission": {"goal_id": goal_spec["id"], "status": "eligible_for_full_experience"},
        "system_version": system["version"],
        "enabled_components": {
            "profile": system["profile"],
            "kg": system["kg"],
            "teaching_assets": system["teaching_assets"],
            "source_grounding": system["source_grounding"],
            "fallback_allowed": system["fallback_allowed"],
            "product_surface": system.get("product_surface"),
            "current_final_system": system.get("current_final_system", False),
        },
        "time_budget": {"user_daily_minutes": payload.daily_minutes, "recommended_daily_minutes": planning.get("recommended_daily_minutes"), "deadline_days": payload.deadline_days},
        "versions": {
            "ablation": system["ablation_version"],
            "kg": "goal_chain_catalog" if system["kg"] else None,
            "source_registry": SOURCE_LINK_VERSION if system["source_grounding"] else None,
            "asset_manifest": "scoped_assets_enabled" if system["teaching_assets"] else None,
            "prompt": V4_PROMPT_VERSION if system["version"] == "V3" else f"controlled-eval-{system['version'].lower()}-prompt-v2",
            "planning_prompt_version": planning.get("prompt_version") or ("controlled-eval-v3-planning-prompt-v2" if system["version"] == "V3" else f"controlled-eval-{system['version'].lower()}-planning-prompt-v2"),
            "content_prompt_version": core_output.get("prompt_version") or (V4_PROMPT_VERSION if system["version"] == "V3" else f"controlled-eval-{system['version'].lower()}-content-prompt-v2"),
            "generator": S4_GENERATOR_VERSION if system["version"] == "V3" else f"controlled-eval-{system['version'].lower()}-generator-v1",
            "planning_agent": planning["planning_agent"],
            "content_agent": core_output.get("content_agent") or f"controlled_eval_{system['version'].lower()}_content_v1",
            "model": payload.model or os.getenv("PATHLY_CONTROLLED_EVAL_MODEL", "gpt-5.4"),
            "temperature": float(payload.temperature),
        },
        "plan": {
            **planning,
            "selected_system_version": system["version"],
            "core_concept": core_output.get("concept_name") or core_output.get("title") or planning["core_concept"],
        },
        "day_1": unit.get("day_1") or {"lecture_sections": day_sections, "estimated_minutes": estimated_minutes},
        "content_contract": {
            "content_agent": core_output.get("content_agent") or f"controlled_eval_{system['version'].lower()}_content_v1",
            "output_format": core_output.get("output_format") or ("lecture_v4" if system["version"] == "V3" else "natural_markdown"),
            "inputs": {
                "planning_agent": planning["planning_agent"],
                "profile": system["profile"], "kg": system["kg"],
                "teaching_assets": system["teaching_assets"], "source_grounding": system["source_grounding"],
            },
        },
        "evaluation_metrics": evaluation_metrics,
        "core_learning_unit": core_output,
        "source_evidence": source_refs,
        "cache": {"status": "bypassed" if not payload.allow_cache else "miss", "fingerprint": fingerprint},
        "checks": {"system_contract": "isolated_controlled_evaluation", "ordinary_learning_paths_untouched": True, **checks},
        "status": "fallback_preview" if fallback_preview else ("success" if success else "failed"),
        "failure_reason": failure_reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generation_mode": generation_mode,
    }
    experience_run_store.save(
        user_id=payload.user_id,
        plan_id=f"controlled-eval:{system['version']}:{goal_spec['id']}",
        day=1,
        status=record["status"],
        payload=record,
    )
    return record


@app.get("/api/demo-users")
async def list_demo_users(request: Request):
    if not DEMO_USERS_ENABLED or LOCAL_DEMO_SHARED_MODE:
        raise HTTPException(status_code=404, detail="Demo users are not enabled")
    users = []
    for key, fixture in NORMAL_PROFILE_FIXTURES.items():
        await run_in_threadpool(_ensure_demo_profile, fixture)
        users.append(_demo_user_summary(key, fixture))
    return envelope(data=users, request_id=request_id_for(request), mode="local_demo")


@app.get("/api/controlled-evaluation/capabilities")
async def controlled_evaluation_capabilities(request: Request):
    """Expose the auditable A0 matrix for local research/benchmark tooling."""
    if not _controlled_evaluation_enabled():
        raise HTTPException(status_code=404, detail="Controlled evaluation is not enabled")
    return envelope(
        data={"ablation_version": ABLATION_VERSION, "systems": capability_matrix()},
        request_id=request_id_for(request),
        mode="controlled_evaluation",
    )


@app.get("/api/controlled-evaluation/options")
async def controlled_evaluation_options(request: Request):
    if not _controlled_evaluation_enabled():
        raise HTTPException(status_code=404, detail="Controlled evaluation is not enabled")
    users = []
    for key, fixture in NORMAL_PROFILE_FIXTURES.items():
        await run_in_threadpool(_ensure_demo_profile, fixture)
        users.append(_demo_user_summary(key, fixture))
    return envelope(
        data={
            "ablation_version": ABLATION_VERSION,
            "systems": capability_matrix(),
            "profiles": users,
            "goals": _controlled_evaluation_goals(),
        },
        request_id=request_id_for(request),
        mode="controlled_evaluation",
    )


@app.post("/api/controlled-evaluation/runs", status_code=201)
async def create_controlled_evaluation_run(payload: ControlledEvaluationRunPayload, request: Request):
    if not _controlled_evaluation_enabled():
        raise HTTPException(status_code=404, detail="Controlled evaluation is not enabled")
    try:
        record = await run_in_threadpool(_run_controlled_evaluation, payload)
    except Exception as exc:
        logging.getLogger("pathly").exception("controlled evaluation run failed")
        record = {
            "run_id": f"controlled-failed-{uuid.uuid4()}",
            "run_type": "controlled_evaluation",
            "user_id": payload.user_id,
            "goal": payload.goal_text,
            "system_version": payload.system_version.upper(),
            "status": "failed",
            "failure_reason": f"generation_exception:{type(exc).__name__}",
            "checks": {"ordinary_learning_paths_untouched": True, "exception": str(exc)[:240]},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    return envelope(data=record, request_id=request_id_for(request), mode="controlled_evaluation")


def _run_matched_diagnostic(payload: ControlledEvaluationComparisonPayload, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Run four new content calls for one fixed concept; never project a Day-1 section."""
    goal_spec = _controlled_goal_spec(payload.goal_text)
    catalog = resolve_goal_chain(goal_spec["goal"])
    path = list((catalog or (None, {}))[1].get("display_names") or verified_goal_concepts_for_goal(goal_spec["goal"]) or [])
    diagnostic_concept = path[-1] if path else goal_spec["goal"]
    systems = []
    for parent in results:
        version = parent.get("system_version")
        system = get_system_config(version)
        profile = _controlled_profile_snapshot(payload.user_id, goal_spec["goal"])
        plan = copy.deepcopy(parent.get("plan") or {})
        plan["day_1_focus"] = diagnostic_concept
        if system["kg"]:
            plan["prerequisite_path"] = [name for name in path if name != diagnostic_concept] + [diagnostic_concept]
        try:
            if version == "V3":
                unit = _controlled_eval_v3_unit(goal_spec, profile, plan)
            else:
                unit = _controlled_eval_text_unit(goal_spec, profile, system, plan, diagnostic_concept=diagnostic_concept)
            status = "success" if (unit.get("content_markdown") or unit.get("lecture_sections")) else "failed"
            failure_reason = None if status == "success" else "matched_diagnostic_empty"
        except Exception as exc:
            unit = {"generation_mode": f"controlled_eval_{str(version).lower()}_live_failed"}
            status = "failed"
            failure_reason = f"matched_diagnostic_exception:{type(exc).__name__}"
        systems.append({
            "run_id": f"matched-{version.lower()}-{uuid.uuid4()}",
            "system_version": version,
            "diagnostic_concept_id": diagnostic_concept,
            "diagnostic_concept": diagnostic_concept,
            "plan": plan,
            "core_learning_unit": unit,
            "source_evidence": unit.get("source_evidence") or [],
            "generation_mode": unit.get("generation_mode"),
            "status": status,
            "failure_reason": failure_reason,
        })
    return {
        "mode": "matched_core_unit_diagnostic",
        "diagnostic_concept_id": diagnostic_concept,
        "concept": diagnostic_concept,
        "systems": systems,
        "note": "Each system independently generated this exact concept with only its own enabled components.",
    }


def _run_controlled_comparison(payload: ControlledEvaluationComparisonPayload) -> dict[str, Any]:
    """Run all four systems with one fixed input and independent artifacts."""
    results = []
    for version in ("V0", "V1", "V2", "V3"):
        run_payload = ControlledEvaluationRunPayload(
            user_id=payload.user_id,
            goal_text=payload.goal_text,
            system_version=version,
            daily_minutes=None,
            model=payload.model,
            temperature=payload.temperature,
            force_regenerate=payload.force_regenerate,
            allow_cache=payload.allow_cache,
            deadline_days=payload.deadline_days,
            allow_fallback_preview=payload.allow_fallback_preview,
        )
        try:
            results.append(_run_controlled_evaluation(run_payload))
        except Exception as exc:
            results.append({
                "run_id": f"controlled-failed-{version.lower()}-{uuid.uuid4()}",
                "run_type": "controlled_evaluation",
                "user_id": payload.user_id,
                "goal": payload.goal_text,
                "system_version": version,
                "status": "failed",
                "failure_reason": f"generation_exception:{type(exc).__name__}",
                "checks": {"ordinary_learning_paths_untouched": True, "exception": str(exc)[:240]},
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    planning_signatures = {
        item.get("system_version"): json.dumps({
            "path": (item.get("plan") or {}).get("prerequisite_path", []),
            "treatment": (item.get("plan") or {}).get("learner_treatment", {}),
            "components": (item.get("plan") or {}).get("planning_components", {}),
        }, sort_keys=True, ensure_ascii=False) for item in results
    }
    content_signatures = {
        item.get("system_version"): json.dumps({
            "title": (item.get("core_learning_unit") or {}).get("title"),
            "mode": item.get("generation_mode"),
            "refs": len(item.get("source_evidence") or []),
            "agent": (item.get("content_contract") or {}).get("content_agent"),
        }, sort_keys=True, ensure_ascii=False) for item in results
    }
    comparison_metrics = {
        "all_versions_completed": all(item.get("status") == "success" for item in results),
        "planning": {item.get("system_version"): item.get("evaluation_metrics", {}).get("planning", {}) for item in results},
        "content": {item.get("system_version"): item.get("evaluation_metrics", {}).get("content", {}) for item in results},
        "grounding": {item.get("system_version"): item.get("evaluation_metrics", {}).get("grounding", {}) for item in results},
        "version_signatures": {item.get("system_version"): item.get("enabled_components", {}) for item in results},
        "distinguishability": {
            "planning_unique_signatures": len(set(planning_signatures.values())),
            "content_unique_signatures": len(set(content_signatures.values())),
            "component_signatures_unique": len({json.dumps(item.get("enabled_components", {}), sort_keys=True) for item in results}),
            "passed": len(set(planning_signatures.values())) >= 3 and len(set(content_signatures.values())) >= 3,
        },
    }
    quality_evaluation = _controlled_quality_evaluation(results, payload)
    matched = _run_matched_diagnostic(payload, results) if payload.include_matched_diagnostic else None
    return {
        "comparison_id": f"comparison-{uuid.uuid4()}",
        "run_type": "controlled_evaluation_comparison",
        "user_id": payload.user_id,
        "goal": payload.goal_text,
        "fixed_input": {"deadline_days": payload.deadline_days, "model": payload.model, "temperature": payload.temperature},
        "systems": results,
        "comparison_metrics": comparison_metrics,
        "quality_evaluation": quality_evaluation,
        "matched_diagnostic": matched,
        "status": "success" if all(item.get("status") == "success" for item in results) and comparison_metrics["distinguishability"]["passed"] else "partial_or_failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _controlled_quality_evaluation(results: list[dict[str, Any]], payload: ControlledEvaluationComparisonPayload) -> dict[str, Any]:
    """Run independent, anonymous, repeated quality judging when configured."""
    evaluator_model = os.getenv("PATHLY_EVALUATOR_MODEL", "")
    if not evaluator_model or not os.getenv("OPENAI_API_KEY"):
        return {"status": "unavailable", "reason": "independent_evaluator_not_configured", "repetitions": 3, "dimensions": []}
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=float(os.getenv("PATHLY_EVALUATOR_TIMEOUT_SECONDS", "60")), max_retries=1)
    dimensions = [
        ("plan_prerequisite_correctness", "Evaluate prerequisite ordering from 1 to 5. Return JSON with score, reasoning, violations_found.", lambda r: {"goal": r.get("goal"), "plan_concept_sequence": (r.get("plan") or {}).get("prerequisite_path", []), "known_prerequisite_pairs": (r.get("checks") or {}).get("plan_coverage", {}).get("path", [])}),
        ("content_pedagogical_completeness", "Evaluate whether the complete Day 1 teaches the goal with coherent explanations, examples, exercises, and takeaway. Score 1 to 5. Return JSON with score, reasoning, missing_elements.", lambda r: {"goal": r.get("goal"), "day_1": r.get("day_1") or {}}),
        ("content_source_grounding", "Evaluate whether claims are traceable to identifiable sources. Score 1 to 5. Return JSON with score, reasoning, grounded_claims, ungrounded_claims.", lambda r: {"concept": (r.get("plan") or {}).get("core_concept"), "content": r.get("day_1") or {}, "source_evidence": r.get("source_evidence") or []}),
        ("personalisation_depth", "Evaluate structural personalization. Score 1 to 5. Return JSON with score, reasoning, adaptation_evidence.", lambda r: {"concept": (r.get("plan") or {}).get("core_concept"), "profile_summary": {"abilities": (r.get("profile_snapshot") or {}).get("cognitive_traits", {}), "style": (r.get("profile_snapshot") or {}).get("preferred_style"), "examples": (r.get("profile_snapshot") or {}).get("preferred_examples", [])}, "content": r.get("day_1") or {}}),
    ]
    judged = []
    for result in results:
        candidate = {"candidate_id": uuid.uuid4().hex, "system_version": result.get("system_version"), "payload": result}
        for name, instruction, package_builder in dimensions:
            scores = []
            attempts = []
            for _ in range(3):
                package = package_builder(result)
                # Blind package excludes version; the UI receives the mapping only after judging.
                request = {"role": "independent expert evaluator", "instruction": instruction, "evaluation_input": package, "rules": ["Do not infer system version", "Return JSON only"]}
                try:
                    response = client.responses.create(model=evaluator_model, input=json.dumps(request, ensure_ascii=False), text={"format": {"type": "json_object"}}, temperature=0, max_output_tokens=700)
                    item = json.loads(str(response.output_text or "{}"))
                    score = int(item.get("score"))
                    if 1 <= score <= 5:
                        scores.append(score); attempts.append(item)
                except Exception as exc:
                    attempts.append({"error": type(exc).__name__})
            judged.append({"candidate_id": candidate["candidate_id"], "system_version": result.get("system_version"), "dimension": name, "scores": scores, "mean": (sum(scores) / len(scores) if scores else None), "low_confidence": bool(scores and max(scores) - min(scores) >= 2), "attempts": attempts})
    return {"status": "complete", "evaluator_model": evaluator_model, "temperature": 0, "repetitions": 3, "blind": True, "results": judged}


@app.post("/api/controlled-evaluation/comparisons", status_code=201)
async def create_controlled_evaluation_comparison(payload: ControlledEvaluationComparisonPayload, request: Request):
    if not _controlled_evaluation_enabled():
        raise HTTPException(status_code=404, detail="Controlled evaluation is not enabled")
    comparison = await run_in_threadpool(_run_controlled_comparison, payload)
    return envelope(data=comparison, request_id=request_id_for(request), mode="controlled_evaluation")


@app.get("/api/controlled-evaluation/runs")
async def list_controlled_evaluation_runs(request: Request, limit: int = 100):
    """List only the current demo user's isolated research artifacts."""
    if not _controlled_evaluation_enabled():
        raise HTTPException(status_code=404, detail="Controlled evaluation is not enabled")
    user_id = str(getattr(request.state, "user_id", None) or "")
    if not user_id or user_id not in {fixture["user_id"] for fixture in NORMAL_PROFILE_FIXTURES.values()}:
        raise HTTPException(status_code=403, detail="Controlled evaluation artifacts require a demo profile session")
    records = await run_in_threadpool(
        experience_run_store.list_runs,
        user_id=user_id,
        run_type="controlled_evaluation",
        limit=limit,
    )
    return envelope(data={"runs": records, "count": len(records)}, request_id=request_id_for(request), mode="controlled_evaluation")


@app.post("/api/demo-users/{user_id}/switch")
async def switch_demo_user(user_id: str, request: Request):
    if not DEMO_USERS_ENABLED or LOCAL_DEMO_SHARED_MODE:
        raise HTTPException(status_code=404, detail="Demo users are not enabled")
    fixture_entry = next(
        ((key, value) for key, value in NORMAL_PROFILE_FIXTURES.items() if value["user_id"] == user_id),
        None,
    )
    if fixture_entry is None:
        raise HTTPException(status_code=404, detail="Demo user not found")
    key, fixture = fixture_entry
    await run_in_threadpool(_ensure_demo_profile, fixture)
    token, record = await run_in_threadpool(session_store.create_for_user, user_id)
    data = {**record, **_demo_user_summary(key, fixture)}
    response = JSONResponse(content=envelope(data=data, request_id=request_id_for(request), mode="local_demo"))
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax",
        secure=SESSION_COOKIE_SECURE, max_age=30*24*60*60, path="/",
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    request_id = request_id_for(request)
    return JSONResponse(
        status_code=422,
        content=error_envelope(
            code="validation_error",
            message="The request data is invalid.",
            details=exc.errors(),
            request_id=request_id,
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    request_id = request_id_for(request)
    message = "The requested Pathly resource was not found." if exc.status_code == 404 else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(
            code="not_found" if exc.status_code == 404 else "http_error",
            message=message,
            request_id=request_id,
        ),
    )

@app.exception_handler(DailyLearningValidationError)
async def daily_learning_validation_error(request: Request, exc: DailyLearningValidationError):
    return JSONResponse(status_code=409, content=error_envelope(code="daily_session_incomplete_or_invalid", message=str(exc), request_id=request_id_for(request)))

@app.exception_handler(LearningLoopValidationError)
async def learning_loop_validation_error(request: Request, exc: LearningLoopValidationError):
    return JSONResponse(
        status_code=409,
        content=error_envelope(
            code="learning_day_locked_or_invalid",
            message=str(exc),
            request_id=request_id_for(request),
        ),
    )


@app.exception_handler(LearningLoopNotFoundError)
async def learning_loop_not_found(request: Request, exc: LearningLoopNotFoundError):
    return JSONResponse(
        status_code=404,
        content=error_envelope(
            code="not_found",
            message="The learning-loop resource was not found.",
            request_id=request_id_for(request),
        ),
    )

@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    request_id = request_id_for(request)
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            code="internal_error",
            message="Pathly could not complete the request.",
            request_id=request_id,
        ),
    )


def sqlite_status() -> dict[str, Any]:
    status = {"available": False, "path_exists": PROFILE_DB.exists(), "writable": False}
    if not PROFILE_DB.exists():
        status["reason"] = "profile database not found"
        return status
    try:
        with sqlite3.connect(f"file:{PROFILE_DB.as_posix()}?mode=ro", uri=True, timeout=2) as conn:
            conn.execute("SELECT 1").fetchone()
        status["available"] = True
        status["writable"] = os.access(PROFILE_DB, os.W_OK)
    except Exception as exc:
        status["reason"] = type(exc).__name__
    return status


def file_capability(path: Path, *, kind: str) -> dict[str, Any]:
    exists = path.exists()
    return {
        "available": exists,
        "kind": kind,
        "reason": None if exists else f"{kind} not found",
    }


def neo4j_status() -> dict[str, Any]:
    status = neo4j_query_status()
    return {
        "available": status["query_verified"],
        "configured": status["configured"],
        "configured_backend": status["configured_backend"],
        "bolt_reachable": status["bolt_reachable"],
        "query_verified": status["query_verified"],
        "actual_backend": status["actual_backend"],
        "database": status["database"],
        "concept_count": status["concept_count"],
        "reason": status["reason"],
    }


def capabilities() -> dict[str, Any]:
    return {
        "service": {"available": True, "name": "pathly", "version": app.version},
        "source_grounded_lecture_v4": {
            "available": LECTURE_V4_ENABLED,
            "stage": "s4_source_grounded_lecture",
            "golden_path_version": GOLDEN_PATH_VERSION,
            "golden_path": GOLDEN_PATH,
            "isolated_progress": True,
            "changes_v1_v2_v3": False,
        },
        "anonymous_sessions": {
            "available": True,
            "required": REQUIRE_SESSION_AUTH,
            "cookie_http_only": True,
            "same_site": "lax",
        },
        "controlled_evaluation": {
            "available": _controlled_evaluation_enabled(),
            "ablation_version": ABLATION_VERSION,
            "current_final_system": "V3",
            "current_final_product_surface": "lecture-v4",
        },
        "sqlite": sqlite_status(),
        "kg_json": file_capability(KG_JSON, kind="calibrated knowledge graph"),
        "chromadb": file_capability(CHROMA_DIR / "chroma.sqlite3", kind="ChromaDB persistence"),
        "private_documents": {
            "available": PRIVATE_DOCUMENT_DIR.exists() and PRIVATE_CHROMA_DIR.exists(),
            "supported_types": ["pdf"],
            "max_bytes": int(os.getenv("PATHLY_MAX_PDF_BYTES", str(25 * 1024 * 1024))),
            "ingestion_mode": "private_chroma_local_hash",
        },
        "workload_estimation": {
            "available": True,
            "scope": "complete_activity_workload",
            "duration_independent": True,
            "document_deduplication": True,
            "generation_mode": "deterministic_template",
        },
        "capacity_negotiation": {
            "available": True,
            "arbitrary_days": True,
            "deadline_supported": True,
            "statuses": ["comfortable", "feasible", "tight", "insufficient"],
            "scope_change_requires_confirmation": True,
            "plan_created_only_after_confirmation": True,
        },
        "activity_scheduling": {
            "available": True,
            "deterministic": True,
            "review_offsets": [1, 3, 7, 14],
            "preserves_unscheduled": True,
            "creates_new_plan_version": True,
        },
        "daily_learning": {
            "available": True,
            "hybrid_calendar": True,
            "whole_remaining_schedule_shift": True,
            "deadline_confirmation": True,
            "content_generation": "two_stage_block_generation_with_deterministic_fallback",
            "content_contract": "daily-content-v2",
            "activity_to_block_mapping": True,
            "scheduled_minute_conservation": True,
            "evidence_preparation": True,
            "required_resources_in_session": True,
            "block_progress_persistence": True,
            "content_cache": True,
            "public_rag": True,
            "private_rag": True,
            "resource_recommendation": True,
        },
        "learning_loop": {
            "contextual_chat": True,
            "content_feedback": True,
            "stable_daily_quiz": True,
            "quiz_uses_completed_study_blocks": True,
            "required_blocks_before_quiz": True,
            "sequential_day_unlock": True,
            "timeline_entry_per_unlocked_day": True,
            "adaptation_signal_storage": True,
            "learner_confirmed_adaptation": False,
            "plan_versions": "v2_active_until_r4",
        },
        "neo4j": neo4j_status(),
    }


@app.post("/api/profiles", status_code=201)
async def create_profile(payload: ProfilePayload, request: Request):
    values = payload.model_dump(exclude_none=True)
    profile = profile_from_payload(values)
    record = await run_in_threadpool(backend.save_profile, profile, values)
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/profiles/{user_id}")
async def get_profile(user_id: str, request: Request):
    record = await run_in_threadpool(backend.get_profile_record, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Profile not found")
    return envelope(data=record, request_id=request_id_for(request))


@app.patch("/api/profiles/{user_id}")
async def patch_profile(user_id: str, payload: ProfilePatch, request: Request):
    current = await run_in_threadpool(backend.profiles.get_profile, user_id)
    if not current:
        raise HTTPException(status_code=404, detail="Profile not found")
    changes = payload.model_dump(exclude_none=True)
    changes["user_id"] = user_id
    profile = profile_from_payload(changes, current)
    record = await run_in_threadpool(backend.save_profile, profile, changes)
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/plans", status_code=201)
async def create_plan(payload: PlanPayload, request: Request):
    try:
        record = await run_in_threadpool(
            backend.create_plan,
            payload.user_id,
            payload.goal_text,
            payload.path_id,
            payload.confirmed_mappings,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Profile not found")
    except PlanningClarificationRequiredError as exc:
        return JSONResponse(
            status_code=409,
            content=error_envelope(
                code="planning_clarification_required",
                message="Some learning goals could not be mapped reliably. Please revise or confirm them.",
                request_id=request_id_for(request),
                details={"mappings": exc.mappings},
            ),
        )
    except PlanningUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                code="planning_unavailable",
                message="Planning is temporarily unavailable. Please retry.",
                request_id=request_id_for(request),
                details={"attempts": exc.attempts},
            ),
        )
    return envelope(data=record, request_id=request_id_for(request), mode=record["mode"])


@app.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str, request: Request):
    record = await run_in_threadpool(backend.plans.get_plan, plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    if REQUIRE_SESSION_AUTH and record["user_id"] != request.state.user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    return envelope(data=record, request_id=request_id_for(request), mode=record["mode"])


@app.get("/api/users/{user_id}/plans")
async def list_plans(user_id: str, request: Request):
    records = await run_in_threadpool(backend.plans.list_plans, user_id)
    return envelope(data=records, request_id=request_id_for(request))


@app.delete("/api/plans/{path_id}")
async def delete_plan_path(path_id: str, payload: DeletePathPayload, request: Request):
    if REQUIRE_SESSION_AUTH and request.state.user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="Plan owner mismatch")
    records = await run_in_threadpool(backend.plans.list_plans, payload.user_id)
    targets = [record for record in records if record["path_id"] == path_id]
    if not targets:
        raise HTTPException(status_code=404, detail="Plan not found")
    deleted = await run_in_threadpool(backend.plans.delete_path, payload.user_id, path_id)
    await run_in_threadpool(backend.contracts.delete_path_context, path_id)
    deleted_v4 = await run_in_threadpool(
        source_grounded_v4_store.delete_by_path,
        payload.user_id,
        path_id,
        [record["plan_id"] for record in targets],
    )
    return envelope(
        data={"path_id": path_id, "deleted_plans": deleted, "deleted_v4_snapshots": deleted_v4},
        request_id=request_id_for(request),
    )

@app.post("/api/documents", status_code=202)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    if REQUIRE_SESSION_AUTH and request.state.user_id != user_id:
        raise HTTPException(status_code=403, detail="Document owner mismatch")
    try:
        record, duplicate = await run_in_threadpool(
            document_service.create_document,
            user_id,
            file.filename,
            file.file,
            file.content_type,
        )
    except DocumentValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_document",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    finally:
        await file.close()
    if not duplicate:
        background_tasks.add_task(document_service.process_document, record["document_id"])
    return envelope(
        data={**record, "duplicate": duplicate},
        request_id=request_id_for(request),
        mode="deduplicated" if duplicate else "queued",
    )


@app.get("/api/users/{user_id}/documents")
async def list_documents(user_id: str, request: Request):
    records = await run_in_threadpool(document_store.list_documents, user_id)
    return envelope(data=records, request_id=request_id_for(request))


@app.get("/api/documents/{document_id}/pages/{page}/render")
async def render_document_page(document_id: str, page: int, user_id: str, request: Request):
    try:
        image_path = await run_in_threadpool(document_service.render_pdf_page, user_id, document_id, page)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except DocumentValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="pdf_page_unavailable", message=str(exc), request_id=request_id_for(request)))
    return FileResponse(image_path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/public-resources/{resource_id}/pages/{page}/render")
async def render_verified_public_resource_page(resource_id: str, page: int, request: Request):
    """Render only PDFs that passed the verified public-source registry."""
    pdf_path = verified_golden_sources.pdf_path_for_resource(resource_id)
    if pdf_path is None:
        # New full-experience goals use the additive, approved source store.
        # They are intentionally not copied into the legacy golden registry,
        # but their page previews still need the same rendering endpoint.
        source = await run_in_threadpool(
            lambda: next(
                (
                    item for item in (
                        experience_source_store.get(source_id)
                        for source_id in ("source:rag:cs224n-2026-rag-agents", "source:word-embeddings:cs224n-2026-wordvecs", "source:self-attention:cs224n-2026-transformers")
                    )
                    if item and str(item.get("resource_id")) == str(resource_id)
                ),
                None,
            )
        )
        if source:
            title_key = re.sub(r"[^a-z0-9]+", "-", str(source.get("document_title") or "").lower()).strip("-")
            source_key = re.sub(r"[^a-z0-9]+", "-", str(source.get("source_id") or "").split(":")[-1].lower()).strip("-")
            candidates = list((KG_DIR / "web_data" / "runs").rglob("*.pdf")) if (KG_DIR / "web_data" / "runs").exists() else []
            pdf_path = next((item for item in candidates if any(
                key and key in re.sub(r"[^a-z0-9]+", "-", item.stem.lower()).strip("-")
                for key in (title_key, source_key)
            )), None)
            if pdf_path is None:
                resource_prefix = str(resource_id).lower()[:12]
                pdf_path = next(
                    (item for item in candidates if resource_prefix and resource_prefix in str(item.parent).lower()),
                    None,
                )
    if pdf_path is None:
        raise HTTPException(status_code=404, detail="Verified public source not found")
    try:
        if page < 1:
            raise HTTPException(status_code=404, detail="PDF page not found")
        target_dir = DATA_DIR / "public_page_cache" / resource_id
        target_dir.mkdir(parents=True, exist_ok=True)
        image_path = target_dir / f"page-{page}.png"
        if not image_path.exists() or image_path.stat().st_size == 0:
            prefix = image_path.with_suffix("")
            subprocess.run(
                [
                    "pdftoppm", "-f", str(page), "-l", str(page), "-r", "144",
                    "-png", "-singlefile", str(pdf_path), str(prefix),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30,
            )
        if not image_path.exists() or image_path.stat().st_size == 0:
            raise RuntimeError("The verified PDF page could not be rendered")
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="pdf_page_unavailable", message=str(exc), request_id=request_id_for(request)))
    return FileResponse(image_path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str, user_id: str, request: Request):
    record = await run_in_threadpool(document_store.get_document, user_id, document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/documents/{document_id}/status")
async def get_document_status(document_id: str, user_id: str, request: Request):
    try:
        status = await run_in_threadpool(document_service.status, user_id, document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    return envelope(data=status, request_id=request_id_for(request))


@app.post("/api/documents/{document_id}/retry", status_code=202)
async def retry_document(
    document_id: str,
    payload: DocumentOwnerPayload,
    request: Request,
    background_tasks: BackgroundTasks,
):
    try:
        job = await run_in_threadpool(
            document_service.retry_document,
            payload.user_id,
            document_id,
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except DocumentConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=error_envelope(
                code="document_ingestion_running",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    background_tasks.add_task(document_service.process_document, document_id)
    return envelope(data=job, request_id=request_id_for(request), mode="queued")


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, user_id: str, request: Request):
    try:
        await run_in_threadpool(document_service.delete_document, user_id, document_id)
        await run_in_threadpool(concept_source_link_index.delete_document, user_id, document_id)
        await run_in_threadpool(source_grounded_v4_store.delete_by_document, user_id, document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    return envelope(
        data={"document_id": document_id, "deleted": True},
        request_id=request_id_for(request),
    )


@app.patch("/api/documents/{document_id}/scope")
async def update_document_scope(
    document_id: str,
    payload: DocumentScopePayload,
    request: Request,
):
    try:
        record = await run_in_threadpool(
            goal_interpretation_service.update_document_scope,
            user_id=payload.user_id,
            document_id=document_id,
            scope=payload.model_dump(exclude={"user_id"}),
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except GoalInterpretationValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_document_scope",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/goal-interpretations", status_code=201)
async def create_goal_interpretation(payload: GoalInterpretationPayload, request: Request):
    try:
        record = await run_in_threadpool(
            goal_interpretation_service.create,
            user_id=payload.user_id,
            goal_text=payload.goal_text,
            source_mode=payload.source_mode,
            document_selections=[item.model_dump() for item in payload.documents],
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except GoalInterpretationValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_goal_interpretation",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=record, request_id=request_id_for(request), mode=record["kg_source"])


@app.get("/api/goal-interpretations/{interpretation_id}")
async def get_goal_interpretation(
    interpretation_id: str,
    user_id: str,
    request: Request,
):
    record = await run_in_threadpool(
        goal_interpretation_store.get,
        user_id,
        interpretation_id,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Goal interpretation not found")
    return envelope(data=record, request_id=request_id_for(request), mode=record["kg_source"])


@app.post("/api/goal-interpretations/{interpretation_id}/confirm")
async def confirm_goal_interpretation(
    interpretation_id: str,
    payload: GoalInterpretationConfirmPayload,
    request: Request,
):
    try:
        record = await run_in_threadpool(
            goal_interpretation_service.confirm,
            user_id=payload.user_id,
            interpretation_id=interpretation_id,
            confirmed_mappings=payload.confirmed_mappings,
            accepted_private_concepts=payload.accepted_private_concepts,
            rejected_private_concepts=payload.rejected_private_concepts,
            rejected_terms=payload.rejected_terms,
        )
    except GoalInterpretationNotFoundError:
        raise HTTPException(status_code=404, detail="Goal interpretation not found")
    except GoalInterpretationValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="goal_interpretation_confirmation_required",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=record, request_id=request_id_for(request), mode=record["kg_source"])


@app.post("/api/onboarding-drafts", status_code=201)
async def create_onboarding_draft(
    payload: OnboardingDraftCreatePayload,
    request: Request,
):
    try:
        draft = await run_in_threadpool(
            onboarding_service.create_draft,
            user_id=payload.user_id,
            goal_text=payload.goal_text,
            name=payload.name,
            academic_level=payload.academic_level,
            domain=payload.domain,
            goal_interpretation_id=payload.goal_interpretation_id,
        )
    except OnboardingValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_onboarding_draft",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=draft, request_id=request_id_for(request))


@app.get("/api/onboarding-drafts/{draft_id}")
async def get_onboarding_draft(draft_id: str, user_id: str, request: Request):
    draft = await run_in_threadpool(onboarding_store.get, user_id, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    return envelope(data=draft, request_id=request_id_for(request))


@app.get("/api/users/{user_id}/onboarding-drafts")
async def list_onboarding_drafts(user_id: str, request: Request):
    drafts = await run_in_threadpool(onboarding_store.list, user_id)
    return envelope(data=drafts, request_id=request_id_for(request))


@app.patch("/api/onboarding-drafts/{draft_id}")
async def patch_onboarding_draft(
    draft_id: str,
    payload: OnboardingDraftPatchPayload,
    request: Request,
):
    try:
        draft = await run_in_threadpool(
            onboarding_service.update_draft,
            user_id=payload.user_id,
            draft_id=draft_id,
            answers=payload.answers,
            current_step=payload.current_step,
            goal_text=payload.goal_text,
        )
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    except OnboardingValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_onboarding_answers",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=draft, request_id=request_id_for(request))


@app.put("/api/onboarding-drafts/{draft_id}/knowledge-map-review")
async def confirm_onboarding_knowledge_map(
    draft_id: str,
    payload: KnowledgeMapReviewPayload,
    request: Request,
):
    try:
        draft = await run_in_threadpool(
            onboarding_service.confirm_knowledge_map,
            user_id=payload.user_id,
            draft_id=draft_id,
            reviewed_concepts=payload.reviewed_concepts,
            excluded_concept_ids=payload.excluded_concept_ids,
            edges=payload.edges,
        )
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    except OnboardingValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_knowledge_map_review",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=draft, request_id=request_id_for(request))


@app.post("/api/onboarding-drafts/{draft_id}/revise-goal")
async def revise_onboarding_goal(
    draft_id: str,
    payload: OnboardingGoalRevisionPayload,
    request: Request,
):
    try:
        draft = await run_in_threadpool(
            onboarding_service.revise_goal,
            user_id=payload.user_id,
            draft_id=draft_id,
            goal_text=payload.goal_text,
            goal_interpretation_id=payload.goal_interpretation_id,
        )
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    except OnboardingValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_goal_revision",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=draft, request_id=request_id_for(request))

@app.post("/api/onboarding-drafts/{draft_id}/confirm-profile")
async def confirm_onboarding_profile(
    draft_id: str,
    payload: OnboardingProfileConfirmPayload,
    request: Request,
):
    try:
        draft = await run_in_threadpool(
            onboarding_service.confirm_profile,
            user_id=payload.user_id,
            draft_id=draft_id,
            cognitive_overrides=payload.cognitive_overrides,
            affective_overrides=payload.affective_overrides,
            target_mastery_overrides=payload.target_mastery_overrides,
            preference_overrides=payload.preference_overrides,
            current_affective_state_overrides=payload.current_affective_state_overrides,
        )
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    except OnboardingValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="onboarding_confirmation_required",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=draft, request_id=request_id_for(request))


@app.delete("/api/onboarding-drafts/{draft_id}")
async def delete_onboarding_draft(draft_id: str, user_id: str, request: Request):
    try:
        await run_in_threadpool(onboarding_store.delete, user_id, draft_id)
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    return envelope(
        data={"draft_id": draft_id, "deleted": True},
        request_id=request_id_for(request),
    )


@app.post("/api/onboarding-drafts/{draft_id}/workload-estimates", status_code=201)
async def create_workload_estimate(
    draft_id: str,
    payload: WorkloadEstimatePayload,
    request: Request,
):
    try:
        estimate = await run_in_threadpool(
            workload_service.generate,
            user_id=payload.user_id,
            draft_id=draft_id,
        )
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    except WorkloadValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="workload_estimate_unavailable",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(
        data=estimate,
        request_id=request_id_for(request),
        mode=estimate["mode"],
    )


@app.get("/api/workload-estimates/{estimate_id}")
async def get_workload_estimate(
    estimate_id: str,
    user_id: str,
    request: Request,
):
    estimate = await run_in_threadpool(workload_store.get, user_id, estimate_id)
    if not estimate:
        raise HTTPException(status_code=404, detail="Workload estimate not found")
    return envelope(
        data=estimate,
        request_id=request_id_for(request),
        mode=estimate["mode"],
    )


@app.get("/api/onboarding-drafts/{draft_id}/workload-estimate")
async def get_latest_draft_workload_estimate(
    draft_id: str,
    user_id: str,
    request: Request,
):
    draft = await run_in_threadpool(onboarding_store.get, user_id, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    estimate = await run_in_threadpool(
        workload_store.latest_for_draft,
        user_id,
        draft_id,
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Workload estimate not found")
    return envelope(
        data=estimate,
        request_id=request_id_for(request),
        mode=estimate["mode"],
    )


@app.post("/api/feasibility-decisions", status_code=201)
async def create_feasibility_decision(
    payload: FeasibilityDecisionCreatePayload,
    request: Request,
):
    try:
        decision = await run_in_threadpool(
            feasibility_service.create,
            user_id=payload.user_id,
            estimate_id=payload.estimate_id,
            requested_days=payload.requested_days,
            deadline=payload.deadline,
            max_available_daily_minutes=payload.max_available_daily_minutes,
        )
    except FeasibilityValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_feasibility_decision",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=decision, request_id=request_id_for(request))


@app.get("/api/workload-estimates/{estimate_id}/feasibility-decision")
async def get_latest_feasibility_decision(
    estimate_id: str,
    user_id: str,
    request: Request,
):
    decision = await run_in_threadpool(
        feasibility_store.latest_for_estimate,
        user_id,
        estimate_id,
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Feasibility decision not found")
    return envelope(data=decision, request_id=request_id_for(request))

@app.get("/api/feasibility-decisions/{decision_id}")
async def get_feasibility_decision(
    decision_id: str,
    user_id: str,
    request: Request,
):
    decision = await run_in_threadpool(feasibility_store.get, user_id, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Feasibility decision not found")
    return envelope(data=decision, request_id=request_id_for(request))


@app.patch("/api/feasibility-decisions/{decision_id}")
async def patch_feasibility_decision(
    decision_id: str,
    payload: FeasibilityDecisionPatchPayload,
    request: Request,
):
    try:
        decision = await run_in_threadpool(
            feasibility_service.update,
            user_id=payload.user_id,
            decision_id=decision_id,
            requested_days=payload.requested_days,
            deadline=payload.deadline,
            max_available_daily_minutes=payload.max_available_daily_minutes,
            selected_strategy=payload.selected_strategy,
            scope_remove_concept_ids=payload.scope_remove_concept_ids,
            scope_change_decision=payload.scope_change_decision,
        )
    except FeasibilityDecisionNotFoundError:
        raise HTTPException(status_code=404, detail="Feasibility decision not found")
    except FeasibilityValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="invalid_feasibility_decision",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(data=decision, request_id=request_id_for(request))


@app.post("/api/feasibility-decisions/{decision_id}/confirm")
async def confirm_feasibility_decision(
    decision_id: str,
    payload: DocumentOwnerPayload,
    request: Request,
):
    try:
        result = await run_in_threadpool(
            feasibility_service.confirm,
            user_id=payload.user_id,
            decision_id=decision_id,
        )
    except FeasibilityDecisionNotFoundError:
        raise HTTPException(status_code=404, detail="Feasibility decision not found")
    except OnboardingDraftNotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding draft not found")
    except FeasibilityValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="feasibility_confirmation_required",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(
        data=result,
        request_id=request_id_for(request),
        mode=result["plan"]["mode"],
    )


@app.post("/api/plans/{plan_id}/schedule", status_code=201)
async def create_plan_schedule(
    plan_id: str,
    payload: DocumentOwnerPayload,
    request: Request,
):
    try:
        record = await run_in_threadpool(
            schedule_service.create,
            user_id=payload.user_id,
            plan_id=plan_id,
        )
    except ScheduleNotFoundError:
        raise HTTPException(status_code=404, detail="Plan not found")
    except ScheduleValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code="schedule_unavailable",
                message=str(exc),
                request_id=request_id_for(request),
            ),
        )
    return envelope(
        data=record,
        request_id=request_id_for(request),
        mode=record["mode"],
    )


@app.get("/api/plans/{plan_id}/schedule")
async def get_plan_schedule(plan_id: str, user_id: str, request: Request):
    try:
        record = await run_in_threadpool(
            schedule_service.get,
            user_id=user_id,
            plan_id=plan_id,
        )
    except ScheduleNotFoundError:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return envelope(
        data=record,
        request_id=request_id_for(request),
        mode=record["mode"],
    )


@app.post("/api/plans/{plan_id}/activate", status_code=201)
async def activate_plan(plan_id: str, payload: PlanActivationPayload, request: Request):
    try:
        record = await run_in_threadpool(
            daily_learning_service.activate,
            user_id=payload.user_id,
            plan_id=plan_id,
            start_date=payload.start_date,
            timezone_name=payload.timezone,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan not found")
    except DailyLearningValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="activation_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/paths/{path_id}/today")
async def get_path_today(path_id: str, user_id: str, request: Request):
    try:
        record = await run_in_threadpool(
            daily_learning_service.today, user_id=user_id, path_id=path_id)
        try:
            progress = await run_in_threadpool(
                learning_loop_service.progress, user_id=user_id, path_id=path_id)
        except LearningLoopNotFoundError:
            progress = None
        if progress:
            next_day = progress.get("next_day")
            if next_day:
                selected = next(
                    (item for item in record["day_dates"] if int(item["day"]) == int(next_day["day"])),
                    None,
                )
                if selected:
                    record["current"] = selected
                    record["is_overdue"] = selected["scheduled_date"] < record["today"]
            record["progress"] = progress
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Active path not found")
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/paths/{path_id}/days/{day}/reschedule")
async def reschedule_path_day(
    path_id: str, day: int, payload: DayReschedulePayload, request: Request
):
    try:
        record = await run_in_threadpool(
            daily_learning_service.reschedule,
            user_id=payload.user_id,
            path_id=path_id,
            day=day,
            new_date=payload.new_date,
            confirm_deadline_impact=payload.confirm_deadline_impact,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Path or learning day not found")
    except DailyLearningValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="reschedule_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/plans/{plan_id}/days/{day}/content")
async def get_daily_content(plan_id: str, day: int, user_id: str, request: Request):
    try:
        await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=user_id, plan_id=plan_id, day=day)
        record = await run_in_threadpool(
            daily_learning_service.get_content,
            user_id=user_id,
            plan_id=plan_id,
            day=day,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Daily content not found")
    return envelope(
        data=record,
        request_id=request_id_for(request),
        mode=record.get("generation_mode", "fallback"),
    )


@app.post("/api/plans/{plan_id}/days/{day}/content", status_code=201)
async def generate_daily_content(
    plan_id: str, day: int, payload: DailyContentGeneratePayload, request: Request
):
    try:
        try:
            await run_in_threadpool(
                learning_loop_service.start_day,
                user_id=payload.user_id,
                plan_id=plan_id,
                day=day,
            )
        except LearningLoopNotFoundError:
            # Compatibility path for isolated DailyContent service tests and
            # legacy activated plans that do not yet have loop runtime rows.
            pass
        record = await run_in_threadpool(
            daily_learning_service.generate_content,
            user_id=payload.user_id,
            plan_id=plan_id,
            day=day,
            force=payload.force,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except DailyLearningValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="daily_content_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(
        data=record,
        request_id=request_id_for(request),
        mode=record.get("generation_mode", "fallback"),
    )


@app.get("/api/plans/{plan_id}/days/{day}/session")
async def get_daily_session(plan_id: str, day: int, user_id: str, request: Request):
    await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=user_id, plan_id=plan_id, day=day)
    record = await run_in_threadpool(daily_learning_service.get_session, user_id=user_id, plan_id=plan_id, day=day)
    return envelope(data=record, request_id=request_id_for(request), mode=record.get("generation_mode", "fallback"))


@app.get("/api/plans/{plan_id}/days/{day}/annotated-session")
async def get_annotated_session(plan_id: str, day: int, user_id: str, request: Request):
    try:
        try:
            await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=user_id, plan_id=plan_id, day=day)
        except LearningLoopNotFoundError:
            pass
        record = await run_in_threadpool(
            annotated_content_service.get_session,
            user_id=user_id,
            plan_id=plan_id,
            day=day,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except AnnotatedSessionValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="annotated_session_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=record, request_id=request_id_for(request), mode=record.get("source_mode", "generated_fallback"))


@app.post("/api/plans/{plan_id}/days/{day}/annotated-session", status_code=201)
async def generate_annotated_session(plan_id: str, day: int, payload: AnnotatedSessionGeneratePayload, request: Request):
    try:
        try:
            await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=payload.user_id, plan_id=plan_id, day=day)
        except LearningLoopNotFoundError:
            pass
        record = await run_in_threadpool(
            annotated_content_service.generate_session,
            user_id=payload.user_id,
            plan_id=plan_id,
            day=day,
            force=payload.force,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except AnnotatedSessionValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="annotated_session_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=record, request_id=request_id_for(request), mode=record.get("source_mode", "generated_fallback"))


@app.get("/api/plans/{plan_id}/days/{day}/full-lecture")
async def get_full_lecture(plan_id: str, day: int, user_id: str, request: Request):
    """Parallel Full Lecture v3 endpoint; existing pages remain unchanged."""
    try:
        try:
            await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=user_id, plan_id=plan_id, day=day)
        except LearningLoopNotFoundError:
            pass
        try:
            annotated = await run_in_threadpool(
                annotated_content_service.get_session,
                user_id=user_id,
                plan_id=plan_id,
                day=day,
            )
            lecture = await run_in_threadpool(generate_full_lecture, annotated)
        except (DailyLearningNotFoundError, AnnotatedSessionValidationError):
            daily = await run_in_threadpool(
                daily_learning_service.get_session,
                user_id=user_id,
                plan_id=plan_id,
                day=day,
            )
            lecture = await run_in_threadpool(generate_full_lecture_from_daily, daily)
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    return envelope(data=lecture, request_id=request_id_for(request), mode=lecture["generation_metadata"].get("generation_mode", "fallback"))


@app.get("/api/plans/{plan_id}/days/{day}/full-lecture/progress")
async def get_full_lecture_progress(plan_id: str, day: int, user_id: str, request: Request):
    try:
        await run_in_threadpool(annotated_content_service.get_session, user_id=user_id, plan_id=plan_id, day=day)
        progress = await run_in_threadpool(full_lecture_progress_store.get, user_id, plan_id, day)
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    return envelope(data={"sections": progress}, request_id=request_id_for(request), mode="stored")


@app.post("/api/plans/{plan_id}/days/{day}/full-lecture/sections/{section_id}/progress", status_code=201)
async def set_full_lecture_section_progress(plan_id: str, day: int, section_id: str, payload: FullLectureSectionProgressPayload, request: Request):
    try:
        lecture = await run_in_threadpool(
            annotated_content_service.get_session, user_id=payload.user_id, plan_id=plan_id, day=day
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    reading_count = len(lecture.get("reading_sequence") or [])
    valid_ids = {f"lecture-section-{index}" for index in range(1, reading_count + 1)}
    if section_id not in valid_ids:
        raise HTTPException(status_code=404, detail="Lecture section not found")
    saved = await run_in_threadpool(
        full_lecture_progress_store.set, payload.user_id, plan_id, day, section_id, payload.completed
    )
    return envelope(data=saved, request_id=request_id_for(request), mode="stored")



@app.post("/api/plans/{plan_id}/days/{day}/full-lecture/sections/{section_id}/regenerate")
async def regenerate_full_lecture_section_endpoint(plan_id: str, day: int, section_id: str, payload: FullLectureSectionRegeneratePayload, request: Request):
    try:
        annotated = await run_in_threadpool(
            annotated_content_service.get_session, user_id=payload.user_id, plan_id=plan_id, day=day
        )
        try:
            section = await run_in_threadpool(regenerate_full_lecture_section, annotated, section_id)
        except ValueError:
            # The browser may hold a section ID from an older annotated-session version.
            # Refresh the source mapping from the unchanged plan and retry the same scheduled position.
            annotated = await run_in_threadpool(
                annotated_content_service.generate_session,
                user_id=payload.user_id,
                plan_id=plan_id,
                day=day,
                force=True,
            )
            section = await run_in_threadpool(regenerate_full_lecture_section, annotated, section_id)
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except (AnnotatedSessionNotFoundError, AnnotatedSessionValidationError, ValueError) as exc:
        return JSONResponse(status_code=409, content=error_envelope(
            code="lecture_section_context_changed",
            message="This lecture section changed while Pathly refreshed its source mapping. Reload the lecture and retry the scheduled concept.",
            request_id=request_id_for(request),
            details={"reason": type(exc).__name__},
        ))
    quality = section.get("content_quality") or {}
    return envelope(data=section, request_id=request_id_for(request), mode=quality.get("generation_mode", "fallback"))

def _v4_enabled_or_404() -> None:
    if not LECTURE_V4_ENABLED:
        raise HTTPException(status_code=404, detail="Source-Grounded Lecture View v4 is disabled")

def _with_v4_progress(payload: dict[str, Any], user_id: str, plan_id: str, day: int) -> dict[str, Any]:
    result = dict(payload)
    result["v4_progress"] = source_grounded_v4_store.progress(user_id, plan_id, day)
    result["v4_exercise_answers"] = source_grounded_v4_store.exercise_answers(user_id, plan_id, day)
    return result

def _v4_request_user(request: Request, claimed_user_id: str | None, plan_id: str) -> tuple[str, dict[str, Any]]:
    """Resolve v4 ownership from the secure session and distinguish missing from foreign plans."""
    user_id = str(getattr(request.state, "user_id", None) or claimed_user_id or "")
    record = backend.plans.get_plan(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="The selected learning plan no longer exists")
    if str(record.get("user_id") or "") != user_id:
        raise HTTPException(status_code=403, detail="This learning plan belongs to another anonymous session")
    return user_id, record

def _v4_scenario_fingerprint(record: dict[str, Any]) -> str:
    """Cache v4 by the inputs expected to change its teaching treatment."""
    plan = record.get("plan") or {}
    profile = (
        backend.get_profile_record(str(record.get("user_id") or ""))
        if record.get("user_id") else None
    ) or record.get("profile_snapshot") or {}
    path_context = record.get("path_context") or {}
    concepts = [str(item.get("concept_id") or item.get("display_name") or item.get("name") or "") for item in (plan.get("concept_path") or [])]
    cognitive = profile.get("cognitive_traits") or {}
    affective = profile.get("affective_defaults") or {}
    relevant_profile = {
        "profile_version": profile.get("profile_version"),
        "mathematical_ability": cognitive.get("mathematical_ability", profile.get("mathematical_ability")),
        "programming_ability": cognitive.get("programming_ability", profile.get("programming_ability")),
        "abstract_thinking": cognitive.get("abstract_thinking", profile.get("abstract_thinking")),
        "logical_reasoning": cognitive.get("logical_reasoning", profile.get("logical_reasoning")),
        "current_affective_state": path_context.get("current_affective_state") or {},
        "target_mastery": path_context.get("target_mastery") or {},
        "learning_style": affective.get("learning_style", profile.get("learning_style")),
        "preferred_examples": affective.get("preferred_examples", profile.get("preferred_examples")),
        "interest_tags": affective.get("interest_tags", profile.get("interest_tags")),
        "pace_preference": affective.get("pace_preference", profile.get("pace_preference")),
        "path_style": path_context.get("preference_overrides") or profile.get("path_style"),
    }
    source = {
        "goal_text": record.get("goal_text") or plan.get("goal_text") or "",
        "concepts": concepts,
        "profile": relevant_profile,
        "public_source_version": PUBLIC_SOURCE_VERSION,
        "source_link_version": SOURCE_LINK_VERSION,
        "golden_path_version": GOLDEN_PATH_VERSION,
        "generator_version": S4_GENERATOR_VERSION,
        "prompt_version": V4_PROMPT_VERSION,
        "treatment_version": V4_TREATMENT_VERSION,
        "verified_source_policy": "golden-goal-canonical-v2",
    }
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

def _v4_cache_is_current(lecture: dict[str, Any] | None, scenario_fingerprint: str) -> bool:
    if lecture is None:
        return False
    meta = lecture.get("generation_metadata") or {}
    # A queued/failed snapshot is still current for this request identity.  Returning
    # it lets the client show its real state instead of repeatedly treating it as a
    # missing resource and starting a second generation job.
    if meta.get("scenario_fingerprint") == scenario_fingerprint and meta.get("generation_state") in {"queued", "generating", "failed"}:
        return True
    asset_manifest_version = str(meta.get("asset_manifest_version") or "")
    approved_asset_manifest = (
        asset_manifest_version == "ta-golden-v2"
        or bool(re.match(r"^[a-z0-9_-]+-(?:assets|gold)-v[0-9]+$", asset_manifest_version))
    )
    current_contract = (
        meta.get("generator_version") == S4_GENERATOR_VERSION
        and meta.get("source_link_version") == SOURCE_LINK_VERSION
        and meta.get("source_link_status") == "indexed"
        and approved_asset_manifest
    )
    if not current_contract:
        return False
    # Saved learner content remains stable until explicit regeneration.  A
    # profile revision or another non-contract fingerprint change must not hide
    # a ready sequential section and replace it with an empty legacy surface.
    ready_sections = [
        section for section in lecture.get("lecture_sections") or []
        if section.get("v4_status") == "ready"
    ]
    if ready_sections and meta.get("generation_state") in {"complete", "waiting_for_completion"}:
        return True
    return meta.get("scenario_fingerprint") == scenario_fingerprint

def _v4_recover_interrupted(lecture: dict[str, Any] | None, active: bool = True) -> dict[str, Any] | None:
    """Turn an abandoned persisted job into a retryable failure after restart/timeout."""
    if lecture is None:
        return None
    metadata = lecture.get("generation_metadata") or {}
    if metadata.get("generation_state") not in {"queued", "generating", "validating"}:
        return lecture
    stamp = metadata.get("started_at") or metadata.get("queued_at")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(stamp))).total_seconds()
    except (TypeError, ValueError):
        age = V4_JOB_TIMEOUT_SECONDS + 1
    # The local worker registry is authoritative while this server process is
    # alive.  A slow but active generation is not interrupted, irrespective of
    # elapsed time; otherwise a browser poll can race the worker and present a
    # false production failure before the worker saves its completed lecture.
    if active:
        return lecture
    metadata.update({
        "generation_state": "failed", "cache_status": "failed",
        "failure_code": "generation_interrupted", "failed_at": datetime.now(timezone.utc).isoformat(),
    })
    lecture["generation_metadata"] = metadata
    lecture["v4_status"] = "failed"
    lecture["can_generate"] = int(metadata.get("attempt_count") or 0) < V4_MAX_RETRY_ATTEMPTS
    return lecture

def _v4_pending_payload(plan_id: str, day: int, scenario_fingerprint: str, reason_code: str) -> dict[str, Any]:
    """Return a non-error v4 runtime state when the isolated lecture can be generated."""
    return {
        "contract_version": "source-grounded-lecture-v4",
        "plan_id": plan_id,
        "day": int(day),
        "v4_status": "not_generated" if reason_code == "cache_missing" else "stale",
        "can_generate": True,
        "reason_code": reason_code,
        "lecture_sections": [],
        "generation_metadata": {
            "generator_version": S4_GENERATOR_VERSION,
            "source_link_version": SOURCE_LINK_VERSION,
            "public_source_version": PUBLIC_SOURCE_VERSION,
            "golden_path_version": GOLDEN_PATH_VERSION,
            "verified_source_policy": "golden-goal-canonical-v2",
            "scenario_fingerprint": scenario_fingerprint,
            "cache_status": reason_code,
            "generation_state": "not_generated",
        },
    }

def _v4_daily_runtime_from_plan(plan_record: dict[str, Any], day: int) -> dict[str, Any]:
    """Build the minimal v4 runtime from a scheduled plan day only.

    The source-grounded experiment must not first create the legacy daily/v3
    lesson.  That old dependency was the cause of v4 404s and long restores for
    otherwise valid newly-created plans.
    """
    plan = plan_record.get("plan") or {}
    plan_day = next((item for item in (plan.get("days") or []) if int(item.get("day") or 0) == int(day)), None)
    if plan_day is None:
        raise HTTPException(status_code=409, detail="This plan has not been scheduled for the selected learning day")
    activities = list(plan_day.get("activities") or [])
    topic_ids: list[str] = []
    for activity in activities:
        ids = activity.get("concept_ids") or ([activity.get("concept_id")] if activity.get("concept_id") else [])
        for concept_id in ids:
            if concept_id and str(concept_id) not in topic_ids:
                topic_ids.append(str(concept_id))
    return {
        "plan_id": plan_record.get("plan_id"),
        "path_id": plan_record.get("path_id"),
        "day": int(day),
        "scheduled_minutes": int(plan_day.get("total_minutes") or sum(int(item.get("estimated_minutes") or item.get("minutes") or 0) for item in activities) or 45),
        "study_blocks": activities,
        "topic_ids": topic_ids,
        "topic_labels": list(plan_day.get("focus_topics") or []),
        "plan_day": plan_day,
    }

def _v4_document_ids(path_id: str) -> list[str]:
    """Private documents enrich v4 when present; they are never required."""
    try:
        return list(daily_learning_store.document_ids(str(path_id or "")) or [])
    except Exception:
        return []

def _v4_seed_lecture_from_daily(daily: dict[str, Any], plan_record: dict[str, Any], day: int) -> dict[str, Any]:
    """Build the isolated v4 section skeleton directly from the scheduled day.

    v4 should not depend on the v3 lecture generator. The seed only supplies
    section order, concept ids, labels, and minutes; source linking and the v4
    generator fill in source-grounded teaching content.
    """
    plan = plan_record.get("plan") or {}
    goal_text = str(plan_record.get("goal_text") or plan.get("goal_text") or "")
    concept_nodes = plan.get("concept_path") or []
    labels: dict[str, str] = {}
    for index, node in enumerate(concept_nodes, 1):
        concept_id = str(node.get("concept_id") or node.get("id") or node.get("name") or "")
        label = (
            node.get("display_name")
            or node.get("name")
            or node.get("title")
            or node.get("label")
            or (f"Private concept {index}" if concept_id.startswith("private:") else concept_id)
        )
        if concept_id:
            labels[concept_id] = str(label)
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    verified_goal_concepts = verified_golden_sources.recommended_concepts_for_goal(goal_text)
    catalog_match = resolve_goal_chain(goal_text)
    if not verified_goal_concepts and catalog_match:
        spec = catalog_match[1]
        ordered = [
            {"concept_id": concept_id, "concept_name": name}
            for concept_id, name in zip(spec["canonical_path"], spec["display_names"])
        ]
        seen = set(spec["canonical_path"])
    if verified_goal_concepts:
        # For the normal golden demo goal, v4 must be seeded from the verified
        # canonical source chain. Planning still creates a normal plan; this only
        # keeps the content layer from drifting into broad or unsupported topics.
        ordered = [
            {"concept_id": concept_name, "concept_name": concept_name}
            for concept_name in verified_goal_concepts
        ]
        seen = set(verified_goal_concepts)
    plan_day = next((item for item in plan.get("days", []) if int(item.get("day", 0)) == int(day)), {}) or {}
    activities = plan_day.get("activities") or daily.get("study_blocks") or []
    if not ordered:
        for activity in activities:
            ids = activity.get("concept_ids") or []
            if not ids and activity.get("concept_id"):
                ids = [activity.get("concept_id")]
            for concept_id in ids:
                cid = str(concept_id)
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                ordered.append({"concept_id": cid, "concept_name": labels.get(cid, cid)})
    if not ordered:
        for label in daily.get("topic_labels") or plan_day.get("focus_topics") or []:
            cid = str(label)
            if cid not in seen:
                seen.add(cid)
                ordered.append({"concept_id": cid, "concept_name": str(label)})
    total_minutes = int(plan_day.get("total_minutes") or daily.get("scheduled_minutes") or 0)
    if not ordered:
        ordered = [{"concept_id": "day-topic", "concept_name": plan_record.get("goal_text") or "Today's topic"}]
    minutes_each = max(15, round((total_minutes or 45) / max(1, len(ordered))))
    sections = []
    for index, item in enumerate(ordered, 1):
        concept_name = item["concept_name"]
        section_id = f"v4-day{int(day)}-section{index}-{re.sub(r'[^a-z0-9]+', '-', concept_name.lower()).strip('-')[:32] or index}"
        sections.append({
            "section_id": section_id,
            "sequence": index,
            "title": concept_name,
            "concept_name": concept_name,
            "concept_ids": [item["concept_id"]],
            "estimated_minutes": minutes_each,
            "source_links": [],
            "source_pages": [],
            "v4_status": "pending_source_linking",
        })
    return {
        "contract_version": "source-grounded-lecture-v4-seed",
        "plan_id": plan_record.get("plan_id"),
        "path_id": plan_record.get("path_id"),
        "day": int(day),
        "lecture_overview": {
            "title": f"Day {int(day)}: Source-grounded lecture for {plan_record.get('goal_text') or plan.get('goal_text') or 'today'}",
            "focus_concepts": [item["concept_name"] for item in ordered],
            "estimated_minutes": total_minutes or sum(section["estimated_minutes"] for section in sections),
        },
        "lecture_sections": sections,
        "generation_metadata": {
            "seed_source": "daily_plan_v4",
            "isolated_from_v3": True,
            "verified_source_policy": "golden-goal-canonical-v2" if verified_goal_concepts else ("approved-goal-catalog-v1" if catalog_match else "daily-plan-seed"),
        },
    }


def _v4_learner_context(user_id: str, plan_record: dict[str, Any]) -> dict[str, Any]:
    """Compose current stable profile with this plan's situational context."""
    profile = backend.get_profile_record(user_id) or {}
    return {
        **profile,
        "user_id": user_id,
        "path_context": copy.deepcopy(plan_record.get("path_context") or {}),
    }


def _v4_queued_snapshot(plan_record: dict[str, Any], day: int, scenario_fingerprint: str, attempt_count: int = 1) -> dict[str, Any]:
    """Persist a small, valid pending snapshot before background work starts."""
    daily = _v4_daily_runtime_from_plan(plan_record, day)
    seed = _v4_seed_lecture_from_daily(daily, plan_record, day)
    queued = create_v4_baseline(
        seed,
        source_links=None,
        source_link_version=SOURCE_LINK_VERSION,
        golden_path=verified_golden_sources.audit(),
    )
    queued["v4_status"] = "generating"
    queued["can_generate"] = False
    planned_sections = list(seed.get("lecture_sections") or [])
    # Persist the day outline now, but only mark the first unit as being built.
    # Later units are deliberately hidden until the learner completes the
    # previous one.
    queued["lecture_sections"] = [
        {
            **section,
            "v4_status": "generating" if index == 0 else "waiting_for_previous_section",
            "retryable": False,
        }
        for index, section in enumerate(planned_sections)
    ]
    queued.setdefault("generation_metadata", {}).update({
        "scenario_fingerprint": scenario_fingerprint,
        "generation_state": "queued",
        "cache_status": "queued",
        "generator_version": S4_GENERATOR_VERSION,
        "source_link_version": SOURCE_LINK_VERSION,
        "attempt_count": int(attempt_count),
        "max_attempts": V4_MAX_RETRY_ATTEMPTS,
        "planned_section_count": len(planned_sections),
        "queued_at": datetime.now(timezone.utc).isoformat(),
    })
    return queued


def _v4_build_lecture(
    user_id: str, plan_record: dict[str, Any], day: int, scenario_fingerprint: str,
    section_id: str | None = None, existing_lecture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one learner-visible V4 section at a time.

    Day 1 used to wait for every source-grounded section before returning any
    content.  This retains the full plan but only creates the requested next
    unit, so completing one unit is the explicit trigger for the next.
    """
    daily = _v4_daily_runtime_from_plan(plan_record, day)
    seed = _v4_seed_lecture_from_daily(daily, plan_record, day)
    full_sections = list(seed.get("lecture_sections") or [])
    if section_id:
        selected = [item for item in full_sections if str(item.get("section_id")) == str(section_id)]
        if not selected:
            raise ValueError("Requested V4 section is not part of this learning day")
        seed["lecture_sections"] = selected
    document_ids = _v4_document_ids(str(daily.get("path_id") or ""))
    projected_links = links_from_lecture(
        seed,
        daily,
        source_provenance_backfill,
        public_source_resolver,
        private_source_link_resolver,
        user_id,
        document_ids,
    )
    profile_context = _v4_learner_context(user_id, plan_record)
    tier = _learner_source_tier(profile_context)
    tiered_links = []
    for link in projected_links:
        candidate = full_experience_sources.resolve(
            concept_id=str(link.get("concept_id") or link.get("concept_name") or ""),
            concept_name=str(link.get("concept_name") or link.get("concept_id") or ""),
            learner_tier=tier,
        )
        tiered_links.append({**link, **candidate} if candidate else link)
    source_links = concept_source_link_index.replace_day(
        user_id, str(plan_record.get("plan_id") or ""), day, tiered_links
    )
    # Day 1 is the first impression and the evaluation surface, so it uses
    # the higher-quality configured model. Later days remain source-grounded
    # but use the economical model explicitly configured for that purpose.
    content_model = (
        os.getenv("PATHLY_V4_DAY1_MODEL", os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4"))
        if int(day) == 1
        else os.getenv("PATHLY_V4_LATER_DAY_MODEL", "gpt-4.1")
    )
    built = build_source_grounded_lecture_v4(
        v3_lecture=seed,
        source_links=source_links,
        daily=daily,
        user_id=user_id,
        profile=profile_context,
        private_documents=document_store,
        public_provenance=source_provenance_backfill,
        verified_registry=full_experience_sources,
        content_model=content_model,
    )
    # Preserve already completed/generated units and keep later units invisible
    # until the learner completes the current one.  These waiting placeholders
    # never enter the learner-facing renderer.
    generated_by_id = {str(item.get("section_id")): item for item in (built.get("lecture_sections") or [])}
    existing_by_id = {str(item.get("section_id")): item for item in ((existing_lecture or {}).get("lecture_sections") or [])}
    assembled_sections: list[dict[str, Any]] = []
    for position, template in enumerate(full_sections):
        sid = str(template.get("section_id"))
        if sid in generated_by_id:
            assembled_sections.append(generated_by_id[sid])
        elif sid in existing_by_id:
            assembled_sections.append(existing_by_id[sid])
        else:
            assembled_sections.append({
                **template,
                "v4_status": "waiting_for_previous_section",
                "retryable": False,
                "source_links": [],
                "source_pages": [],
            })
    lecture = {**built, "lecture_sections": assembled_sections}
    lecture["golden_path_sources"] = verified_golden_sources.audit()
    metadata = lecture.setdefault("generation_metadata", {})
    ready_count = sum(item.get("v4_status") == "ready" for item in assembled_sections)
    metadata.update({
        "scenario_fingerprint": scenario_fingerprint,
        "generation_state": "complete" if ready_count == len(assembled_sections) else "waiting_for_completion",
        "cache_status": "ready" if ready_count == len(assembled_sections) else "partial",
        "generator_version": S4_GENERATOR_VERSION,
        "prompt_version": V4_PROMPT_VERSION,
        "treatment_version": V4_TREATMENT_VERSION,
        "generated_for_user_id": user_id,
        "profile_version": (_v4_learner_context(user_id, plan_record).get("profile_version") or 1),
        "source_link_version": SOURCE_LINK_VERSION,
        "planned_section_count": len(full_sections),
        "ready_section_count": ready_count,
        "generated_section_id": section_id or (full_sections[0].get("section_id") if full_sections else None),
    })
    lecture["can_generate"] = True
    lecture["v4_status"] = "generated" if ready_count else "unavailable"
    return lecture


def _v4_generation_worker(user_id: str, plan_id: str, day: int, scenario_fingerprint: str, section_id: str | None = None) -> None:
    """Run the expensive source linking/generation outside the request lifecycle."""
    job_key = (user_id, plan_id, int(day))
    plan_record = None
    lecture = None
    # A pilot runs one process/replica.  The semaphore turns concurrent browser
    # requests into an in-process FIFO wait rather than an OpenAI rate-limit
    # burst, while preserving the durable queued snapshot for polling.
    _v4_generation_slots.acquire()
    try:
        plan_record = backend.plans.get_plan(plan_id)
        if plan_record is None or str(plan_record.get("user_id") or "") != user_id:
            return
        existing = source_grounded_v4_store.get(user_id, plan_id, day)
        if existing is not None:
            metadata = existing.setdefault("generation_metadata", {})
            metadata["generation_state"] = "generating"
            metadata["cache_status"] = "generating"
            metadata["started_at"] = datetime.now(timezone.utc).isoformat()
            existing["v4_status"] = "generating"
            source_grounded_v4_store.save(user_id, plan_id, day, existing)
        attempt_count = int(((existing or {}).get("generation_metadata") or {}).get("attempt_count") or 1)
        lecture = _v4_build_lecture(
            user_id, plan_record, day, scenario_fingerprint,
            section_id=section_id, existing_lecture=existing,
        )
        sections = list(lecture.get("lecture_sections") or [])
        ready_sections = [item for item in sections if item.get("v4_status") == "ready"]
        if not sections:
            raise ValueError("V4 generation produced no lecture sections")
        generated = [item for item in sections if str(item.get("section_id")) == str(section_id)] if section_id else ready_sections
        if not generated or any(item.get("v4_status") != "ready" for item in generated):
            failures = ", ".join(
                f"{item.get('concept_id')}: {item.get('failure_code') or item.get('v4_status')}"
                for item in generated if item.get("v4_status") != "ready"
            )
            raise ValueError(f"V4 section generation incomplete: {failures}")
        if not any(item.get("source_pages") for item in generated):
            raise ValueError("V4 generation produced no auditable source evidence")
        lecture.setdefault("generation_metadata", {}).update({"attempt_count": attempt_count, "max_attempts": V4_MAX_RETRY_ATTEMPTS, "completed_at": datetime.now(timezone.utc).isoformat()})
        source_grounded_v4_store.save(user_id, plan_id, day, lecture)
        experience_run_store.save(
            user_id=user_id, plan_id=plan_id, day=day, status="success",
            payload=build_experience_run(user_id=user_id, plan_record=plan_record, day=day, lecture=lecture, success=True),
        )
    except Exception as exc:  # keep a recoverable state; never strand the page in loading
        security_logger.exception("v4 generation failed for plan=%s day=%s: %s", plan_id, day, type(exc).__name__)
        existing = source_grounded_v4_store.get(user_id, plan_id, day)
        failed_snapshot = lecture if lecture is not None else existing
        if failed_snapshot is not None:
            metadata = failed_snapshot.setdefault("generation_metadata", {})
            metadata.update({
                "generation_state": "failed",
                "cache_status": "failed",
                "failure_code": "v4_generation_failed",
                # Keep a bounded diagnostic so the UI/API can distinguish a
                # deterministic pipeline failure from a transient model retry.
                "failure_detail": f"{type(exc).__name__}: {str(exc)[:240]}",
                "scenario_fingerprint": scenario_fingerprint,
            })
            failed_snapshot["v4_status"] = "failed"
            failed_snapshot["can_generate"] = True
            source_grounded_v4_store.save(user_id, plan_id, day, failed_snapshot)
            if plan_record is not None:
                experience_run_store.save(
                    user_id=user_id, plan_id=plan_id, day=day, status="failed",
                    payload=build_experience_run(user_id=user_id, plan_record=plan_record, day=day, lecture=failed_snapshot, success=False, error_reason=metadata.get("failure_detail")),
                )
    finally:
        _v4_generation_slots.release()
        with _v4_jobs_lock:
            _v4_active_jobs.discard(job_key)


def _queue_v4_generation(user_id: str, plan_record: dict[str, Any], day: int, scenario_fingerprint: str, force: bool = False) -> dict[str, Any]:
    """Return immediately with pending state and run one idempotent background job."""
    plan_id = str(plan_record.get("plan_id") or "")
    job_key = (user_id, plan_id, int(day))
    existing = source_grounded_v4_store.get(user_id, plan_id, day)
    previous_attempts = int(((existing or {}).get("generation_metadata") or {}).get("attempt_count") or 0)
    # An explicit user retry starts a fresh bounded generation window. Automatic
    # retries remain capped, but a transient outage must not permanently brick
    # the page after the first window has been exhausted.
    if force and previous_attempts >= V4_MAX_RETRY_ATTEMPTS:
        previous_attempts = 0
    attempt_count = previous_attempts + 1
    with _v4_jobs_lock:
        active = job_key in _v4_active_jobs
        if not active:
            _v4_active_jobs.add(job_key)
    if not active:
        snapshot = _v4_queued_snapshot(plan_record, day, scenario_fingerprint, attempt_count)
        initial_sections = snapshot.get("lecture_sections") or []
        first_section_id = str(initial_sections[0].get("section_id")) if initial_sections else None
        source_grounded_v4_store.save(user_id, plan_id, day, snapshot)
        threading.Thread(
            target=_v4_generation_worker,
            args=(user_id, plan_id, int(day), scenario_fingerprint, first_section_id),
            daemon=True,
            name=f"pathly-v4-{plan_id[:8]}-{day}",
        ).start()
        return snapshot
    return existing or _v4_queued_snapshot(plan_record, day, scenario_fingerprint, attempt_count)


def _queue_next_v4_section(user_id: str, plan_record: dict[str, Any], day: int, lecture: dict[str, Any]) -> str | None:
    """Start only the next locked unit after the learner completes one."""
    plan_id = str(plan_record.get("plan_id") or "")
    target = next(
        (item for item in lecture.get("lecture_sections") or [] if item.get("v4_status") == "waiting_for_previous_section"),
        None,
    )
    if target is None:
        return None
    section_id = str(target.get("section_id") or "")
    if not section_id:
        return None
    job_key = (user_id, plan_id, int(day))
    with _v4_jobs_lock:
        if job_key in _v4_active_jobs:
            return None
        _v4_active_jobs.add(job_key)
    target["v4_status"] = "generating"
    lecture["v4_status"] = "generating"
    lecture.setdefault("generation_metadata", {}).update({
        "generation_state": "generating",
        "cache_status": "partial",
        "generating_section_id": section_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    source_grounded_v4_store.save(user_id, plan_id, day, lecture)
    threading.Thread(
        target=_v4_generation_worker,
        args=(user_id, plan_id, int(day), _v4_scenario_fingerprint(plan_record), section_id),
        daemon=True,
        name=f"pathly-v4-next-{plan_id[:8]}-{day}",
    ).start()
    return section_id

def _v4_section_retry_worker(user_id: str, plan_id: str, day: int, section_id: str, scenario_fingerprint: str) -> None:
    job_key = (user_id, plan_id, int(day))
    try:
        plan_record = backend.plans.get_plan(plan_id)
        lecture = source_grounded_v4_store.get(user_id, plan_id, day)
        if not plan_record or not lecture:
            return
        target = next((copy.deepcopy(item) for item in lecture.get("lecture_sections", []) if str(item.get("section_id")) == section_id), None)
        if target is None:
            return
        metadata = lecture.setdefault("generation_metadata", {})
        metadata.update({"generation_state": "validating", "cache_status": "validating", "started_at": datetime.now(timezone.utc).isoformat()})
        source_grounded_v4_store.save(user_id, plan_id, day, lecture)
        daily = _v4_daily_runtime_from_plan(plan_record, day)
        isolated = {key: copy.deepcopy(value) for key, value in lecture.items() if key != "lecture_sections"}
        isolated["lecture_sections"] = [target]
        links = list(target.get("source_links") or [])
        result = build_source_grounded_lecture_v4(
            v3_lecture=isolated, source_links=links, daily=daily, user_id=user_id,
            profile=_v4_learner_context(user_id, plan_record), private_documents=document_store,
            public_provenance=source_provenance_backfill, verified_registry=full_experience_sources,
            content_model=(
                os.getenv("PATHLY_V4_DAY1_MODEL", os.getenv("PATHLY_CONTENT_MODEL", "gpt-5.4"))
                if int(day) == 1 else os.getenv("PATHLY_V4_LATER_DAY_MODEL", "gpt-4.1")
            ),
        )
        replacement = (result.get("lecture_sections") or [target])[0]
        replacement["retry_attempts"] = int(target.get("retry_attempts") or 0)
        latest = source_grounded_v4_store.get(user_id, plan_id, day) or lecture
        latest["lecture_sections"] = [replacement if str(item.get("section_id")) == section_id else item for item in latest.get("lecture_sections", [])]
        ready_count = sum(item.get("v4_status") == "ready" for item in latest["lecture_sections"])
        latest["v4_status"] = "generated" if ready_count else "unavailable"
        latest.setdefault("generation_metadata", {}).update({
            "generation_state": "complete", "cache_status": "ready" if ready_count else "failed",
            "scenario_fingerprint": scenario_fingerprint, "retrying_section_id": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        source_grounded_v4_store.save(user_id, plan_id, day, latest)
    except Exception as exc:
        security_logger.exception("v4 section retry failed plan=%s day=%s section=%s", plan_id, day, section_id)
        lecture = source_grounded_v4_store.get(user_id, plan_id, day)
        if lecture:
            lecture.setdefault("generation_metadata", {}).update({"generation_state": "complete", "cache_status": "partial", "retrying_section_id": None, "section_failure_code": type(exc).__name__})
            source_grounded_v4_store.save(user_id, plan_id, day, lecture)
    finally:
        with _v4_jobs_lock:
            _v4_active_jobs.discard(job_key)

@app.get("/api/plans/{plan_id}/days/{day}/lecture-v4")
async def get_source_grounded_lecture_v4(plan_id: str, day: int, request: Request, user_id: str | None = None):
    _v4_enabled_or_404()
    user_id, plan_record = _v4_request_user(request, user_id, plan_id)
    scenario_fingerprint = _v4_scenario_fingerprint(plan_record)
    lecture = await run_in_threadpool(source_grounded_v4_store.get, user_id, plan_id, day)
    original_state = str(((lecture or {}).get("generation_metadata") or {}).get("generation_state") or "")
    with _v4_jobs_lock:
        active = (user_id, plan_id, int(day)) in _v4_active_jobs
    recovered = _v4_recover_interrupted(lecture, active=active)
    if recovered is not None and original_state in {"queued", "generating", "validating"} and (recovered.get("generation_metadata") or {}).get("generation_state") == "failed":
        await run_in_threadpool(source_grounded_v4_store.save, user_id, plan_id, day, recovered)
    lecture = recovered
    if lecture is None:
        pending = _v4_pending_payload(plan_id, day, scenario_fingerprint, "cache_missing")
        return envelope(data=_with_v4_progress(pending, user_id, plan_id, day), request_id=request_id_for(request), mode="v4_not_generated")
    if not _v4_cache_is_current(lecture, scenario_fingerprint):
        # A completed private-document lecture is tied to the learner's own
        # uploaded files.  Do not hide that finished result merely because a
        # later server/config fingerprint changed; explicit regeneration is
        # still available when the learner wants fresh content.
        document_ids = _v4_document_ids(str(plan_record.get("path_id") or ""))
        metadata = lecture.get("generation_metadata") or {}
        if (
            document_ids
            and metadata.get("generation_state") == "complete"
            and any(item.get("v4_status") == "ready" for item in lecture.get("lecture_sections") or [])
        ):
            return envelope(data=_with_v4_progress(lecture, user_id, plan_id, day), request_id=request_id_for(request), mode="stored_private_document_lecture")
        pending = _v4_pending_payload(plan_id, day, scenario_fingerprint, "cache_stale")
        if active:
            pending["v4_status"] = "generating"
            pending.setdefault("generation_metadata", {})["generation_state"] = "generating"
            pending["generation_metadata"]["cache_status"] = "generating"
            pending["can_generate"] = False
        return envelope(data=_with_v4_progress(pending, user_id, plan_id, day), request_id=request_id_for(request), mode="v4_stale")
    return envelope(data=_with_v4_progress(lecture, user_id, plan_id, day), request_id=request_id_for(request), mode="stored")


@app.get("/api/plans/{plan_id}/days/{day}/experience-run")
async def get_experience_run(plan_id: str, day: int, request: Request, user_id: str | None = None):
    user_id, _ = _v4_request_user(request, user_id, plan_id)
    record = await run_in_threadpool(experience_run_store.latest, user_id, plan_id, day)
    if record is None:
        raise HTTPException(status_code=404, detail="No completed experience run is available for this day.")
    return envelope(data=record, request_id=request_id_for(request), mode="audit")

@app.post("/api/plans/{plan_id}/days/{day}/lecture-v4/generate", status_code=201)
async def generate_source_grounded_lecture_v4(plan_id: str, day: int, payload: SourceGroundedLectureV4GeneratePayload, request: Request):
    _v4_enabled_or_404()
    user_id, plan_record = _v4_request_user(request, payload.user_id, plan_id)
    scenario_fingerprint = _v4_scenario_fingerprint(plan_record)
    existing = await run_in_threadpool(source_grounded_v4_store.get, user_id, plan_id, day)
    state = str((existing or {}).get("generation_metadata", {}).get("generation_state") or "")
    if existing is not None and not payload.force and _v4_cache_is_current(existing, scenario_fingerprint):
        return envelope(data=_with_v4_progress(existing, user_id, plan_id, day), request_id=request_id_for(request), mode="cached")
    # A normal Day 1 must be allowed to initialise v4 directly.  Do not require a
    # legacy daily/v3 record or an unlocked quiz loop: those are separate products.
    queued = await run_in_threadpool(_queue_v4_generation, user_id, plan_record, day, scenario_fingerprint, payload.force)
    return envelope(
        data=_with_v4_progress(queued, user_id, plan_id, day),
        request_id=request_id_for(request),
        mode="v4_generation_queued" if state != "complete" else "v4_regeneration_queued",
    )

@app.get("/api/plans/{plan_id}/days/{day}/lecture-v4/source-links")
async def get_source_grounded_lecture_v4_links(
    plan_id: str, day: int, request: Request, user_id: str | None = None
):
    _v4_enabled_or_404()
    user_id, _ = _v4_request_user(request, user_id, plan_id)
    links = await run_in_threadpool(
        concept_source_link_index.list_day, user_id, plan_id, day
    )
    return envelope(
        data={
            "source_link_version": SOURCE_LINK_VERSION,
            "golden_path_version": GOLDEN_PATH_VERSION,
            "links": links,
            "sections": [
                {
                    "concept_id": item["concept_id"],
                    "concept_name": item["concept_name"],
                    "status": item["review_status"],
                    "source_scope": item["source_scope"],
                    "document_title": item.get("document_title"),
                    "page_sequence": item["page_sequence"],
                    "match_reason": item["match_reason"],
                    "source_readiness": item.get("source_readiness"),
                    "coverage_summary": (f"{len(item['page_sequence'])} consecutive source page(s)" if item["page_sequence"] else "No reliable source pages"),
                }
                for item in links
            ],
            "verified": sum(item["review_status"] == "verified" for item in links),
            "usable": sum(item["review_status"] == "usable" for item in links),
            "unlinked": sum(item["review_status"] == "unlinked" for item in links),
        },
        request_id=request_id_for(request),
        mode="read_only_index",
    )


@app.get("/api/concepts/{concept_id}/verified-sources")
async def get_verified_public_sources(concept_id: str, request: Request, concept_name: str = ""):
    """Return reusable public coverage; never returns learner-private sources."""
    source = await run_in_threadpool(
        public_source_registry.resolve,
        concept_id=concept_id,
        concept_name=concept_name or concept_id,
    )
    if source is None:
        return envelope(
            data={
                "canonical_concept": concept_name or concept_id,
                "source_version": PUBLIC_SOURCE_VERSION,
                "status": "unlinked",
                "sources": [],
            },
            request_id=request_id_for(request),
            mode="public_source_registry",
        )
    return envelope(
        data={
            "canonical_concept": source["canonical_concept_name"],
            "canonical_concept_id": source["canonical_concept_id"],
            "source_version": source["source_version"],
            "status": source["review_status"],
            "sources": [source],
        },
        request_id=request_id_for(request),
        mode="public_source_registry",
    )


@app.post("/api/internal/source-links/rebuild")
async def rebuild_public_source_links(request: Request):
    """Local maintenance endpoint; reads Neo4j/Chroma and replaces the sidecar only."""
    host = str(request.client.host if request.client else "")
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="This maintenance action is local only")
    try:
        result = await run_in_threadpool(public_source_registry.rebuild)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return envelope(
        data=result,
        request_id=request_id_for(request),
        mode="neo4j_chroma_public_registry_rebuild",
    )

@app.get("/api/lecture-v4/golden-path")
async def get_lecture_v4_golden_path(request: Request):
    _v4_enabled_or_404()
    audit = await run_in_threadpool(verified_golden_sources.audit)
    return envelope(
        data={
            "golden_path_version": GOLDEN_PATH_VERSION,
            "concepts": audit,
            "verified": sum(item["status"] == "verified" for item in audit),
            "total": len(audit),
        },
        request_id=request_id_for(request),
        mode="read_only_verified_registry",
    )


@app.post("/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/complete", status_code=201)
async def complete_source_grounded_lecture_v4_section(plan_id: str, day: int, section_id: str, payload: SourceGroundedLectureV4SectionPayload, request: Request):
    _v4_enabled_or_404()
    user_id, plan_record = _v4_request_user(request, payload.user_id, plan_id)
    lecture = await run_in_threadpool(source_grounded_v4_store.get, user_id, plan_id, day)
    if lecture is None:
        raise HTTPException(status_code=404, detail="Source-Grounded Lecture View v4 has not been generated")
    valid_ids = {str(item.get("section_id")) for item in lecture.get("lecture_sections", [])}
    if section_id not in valid_ids:
        raise HTTPException(status_code=404, detail="v4 lecture section not found")
    saved = await run_in_threadpool(source_grounded_v4_store.set_progress, user_id, plan_id, day, section_id, payload.completed)
    # V4 is a complete learning experience in its own right.  Once every
    # source-grounded section is marked complete, advance the shared path
    # progress so the next scheduled day unlocks without requiring the legacy
    # v1/v2/v3 quiz flow.
    if payload.completed:
        progress = await run_in_threadpool(source_grounded_v4_store.progress, user_id, plan_id, day)
        sections = lecture.get("lecture_sections") or []
        # The next source-grounded unit is intentionally generated only after
        # this one is completed.  This keeps Day 1 responsive and prevents
        # background generation from consuming requests the learner may never
        # reach.
        next_section_id = await run_in_threadpool(_queue_next_v4_section, user_id, plan_record, day, lecture)
        if next_section_id:
            saved["next_section_queued"] = next_section_id
        if sections and all(
            item.get("v4_status") == "ready"
            and (progress.get(str(item.get("section_id")), {}).get("status") == "completed")
            for item in sections
        ):
            path_id = str(plan_record.get("path_id") or "")
            if path_id:
                await run_in_threadpool(
                    learning_loop_store.upsert_progress,
                    user_id=user_id, path_id=path_id, plan_id=plan_id, day=int(day),
                    status="completed", content_progress=1, actual_minutes=0, completed=True,
                )
                saved["day_completed"] = True
    return envelope(data=saved, request_id=request_id_for(request), mode="v4_stored")

@app.post("/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/exercises/{question_id}/answer", status_code=201)
async def answer_source_grounded_lecture_v4_exercise(plan_id: str, day: int, section_id: str, question_id: str, payload: SourceGroundedLectureV4ExerciseAnswerPayload, request: Request):
    _v4_enabled_or_404()
    user_id, _ = _v4_request_user(request, payload.user_id, plan_id)
    lecture = await run_in_threadpool(source_grounded_v4_store.get, user_id, plan_id, day)
    section = next((item for item in (lecture or {}).get("lecture_sections", []) if str(item.get("section_id")) == section_id), None)
    if section is None:
        raise HTTPException(status_code=404, detail="v4 lecture section not found")
    question = next((item for item in ((section.get("lecture_content") or {}).get("objective_exercise") or {}).get("questions") or [] if str(item.get("question_id")) == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="v4 objective question not found")
    option = next((item for item in question.get("options") or [] if str(item.get("id")) == payload.answer_id), None)
    if option is None:
        raise HTTPException(status_code=422, detail="The selected answer is not an option for this question")
    saved = await run_in_threadpool(source_grounded_v4_store.set_exercise_answer, user_id, plan_id, day, section_id, question_id, payload.answer_id, bool(option.get("correct")))
    saved["explanation"] = option.get("feedback") or question.get("explanation") or ""
    return envelope(data=saved, request_id=request_id_for(request), mode="v4_exercise_answered")

@app.post("/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/open-answer", status_code=201)
async def grade_source_grounded_lecture_v4_open_answer(plan_id: str, day: int, section_id: str, payload: SourceGroundedLectureV4OpenAnswerPayload, request: Request):
    _v4_enabled_or_404()
    user_id, _ = _v4_request_user(request, payload.user_id, plan_id)
    lecture = await run_in_threadpool(source_grounded_v4_store.get, user_id, plan_id, day)
    section = next((item for item in (lecture or {}).get("lecture_sections", []) if str(item.get("section_id")) == section_id), None)
    if section is None:
        raise HTTPException(status_code=404, detail="v4 lecture section not found")
    concept = section.get("concept_name") or section.get("title") or "the concept"
    prompt = f"Grade this learner answer as a supportive machine-learning tutor. Concept: {concept}. Answer: {payload.answer}\nReturn JSON with score (0 to 1), correct (boolean), and feedback (one concise sentence explaining the mechanism or the missing idea). Do not require exact wording."
    try:
        result = await run_in_threadpool(_controlled_openai_json, {"prompt": prompt}, max_output_tokens=300, temperature=0)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Open answer grading unavailable: {error}")
    return envelope(data={"correct": bool(result.get("correct")), "score": result.get("score"), "feedback": result.get("feedback") or "Thanks for explaining your reasoning."}, request_id=request_id_for(request), mode="v4_open_answer_graded")

@app.post("/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/retry")
async def retry_source_grounded_lecture_v4_section(plan_id: str, day: int, section_id: str, payload: SourceGroundedLectureV4GeneratePayload, request: Request):
    _v4_enabled_or_404()
    user_id, plan_record = _v4_request_user(request, payload.user_id, plan_id)
    lecture = await run_in_threadpool(source_grounded_v4_store.get, user_id, plan_id, day)
    target = next((item for item in (lecture or {}).get("lecture_sections", []) if str(item.get("section_id")) == section_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="v4 lecture section not found")
    attempts = int(target.get("retry_attempts") or 0)
    limit = int(target.get("max_retry_attempts") or V4_MAX_RETRY_ATTEMPTS)
    if attempts >= limit:
        raise HTTPException(status_code=409, detail="Maximum section retry attempts reached")
    scenario_fingerprint = _v4_scenario_fingerprint(plan_record)
    job_key = (user_id, plan_id, int(day))
    with _v4_jobs_lock:
        if job_key in _v4_active_jobs:
            return envelope(data=lecture, request_id=request_id_for(request), mode="v4_generation_active")
        _v4_active_jobs.add(job_key)
    target["v4_status"] = "generating"
    target["retry_attempts"] = attempts + 1
    lecture.setdefault("generation_metadata", {}).update({
        "generation_state": "generating", "cache_status": "partial",
        "retrying_section_id": section_id, "queued_at": datetime.now(timezone.utc).isoformat(),
    })
    await run_in_threadpool(source_grounded_v4_store.save, user_id, plan_id, day, lecture)
    threading.Thread(target=_v4_section_retry_worker, args=(user_id, plan_id, int(day), section_id, scenario_fingerprint), daemon=True, name=f"pathly-v4-retry-{plan_id[:8]}-{day}").start()
    return envelope(data=lecture, request_id=request_id_for(request), mode="v4_section_retry_queued")

@app.get("/api/plans/{plan_id}/days/{day}/annotated-session/readings/{reading_id}/source-context")
async def annotated_reading_source_context(plan_id: str, day: int, reading_id: str, user_id: str, request: Request):
    try:
        try:
            await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=user_id, plan_id=plan_id, day=day)
        except LearningLoopNotFoundError:
            pass
        record = await run_in_threadpool(
            annotated_content_service.source_context,
            user_id=user_id,
            plan_id=plan_id,
            day=day,
            reading_id=reading_id,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except AnnotatedSessionNotFoundError:
        raise HTTPException(status_code=404, detail="Annotated reading not found")
    return envelope(data=record, request_id=request_id_for(request))

@app.post("/api/plans/{plan_id}/days/{day}/annotated-session/readings/{reading_id}/complete")
async def complete_annotated_reading(plan_id: str, day: int, reading_id: str, payload: AnnotatedReadingCompletePayload, request: Request):
    try:
        try:
            await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=payload.user_id, plan_id=plan_id, day=day)
        except LearningLoopNotFoundError:
            pass
        record = await run_in_threadpool(
            annotated_content_service.update_reading,
            user_id=payload.user_id,
            plan_id=plan_id,
            day=day,
            reading_id=reading_id,
            status=payload.status,
            response=payload.response,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except AnnotatedSessionNotFoundError:
        raise HTTPException(status_code=404, detail="Annotated reading not found")
    except AnnotatedSessionValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="annotated_reading_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/plans/{plan_id}/days/{day}/annotated-session/exercises/{exercise_id}/submit")
async def submit_annotated_exercise(plan_id: str, day: int, exercise_id: str, payload: AnnotatedExerciseSubmitPayload, request: Request):
    try:
        try:
            await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=payload.user_id, plan_id=plan_id, day=day)
        except LearningLoopNotFoundError:
            pass
        record = await run_in_threadpool(
            annotated_content_service.submit_exercise,
            user_id=payload.user_id,
            plan_id=plan_id,
            day=day,
            exercise_id=exercise_id,
            answer=payload.answer,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except AnnotatedSessionNotFoundError:
        raise HTTPException(status_code=404, detail="Annotated exercise not found")
    except AnnotatedSessionValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="annotated_exercise_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=record, request_id=request_id_for(request))

@app.patch("/api/plans/{plan_id}/days/{day}/blocks/{block_id}/progress")
async def update_study_block(plan_id: str, day: int, block_id: str, payload: StudyBlockProgressPayload, request: Request):
    await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=payload.user_id, plan_id=plan_id, day=day)
    record = await run_in_threadpool(daily_learning_service.update_block, user_id=payload.user_id, plan_id=plan_id, day=day, block_id=block_id, status=payload.status, progress=payload.progress, actual_seconds=payload.actual_seconds, answer=payload.answer, feedback=payload.feedback)
    await run_in_threadpool(learning_loop_service.sync_content_progress, user_id=payload.user_id, plan_id=plan_id, day=day, session=record["session"])
    return envelope(data=record, request_id=request_id_for(request))

@app.post("/api/plans/{plan_id}/days/{day}/blocks/{block_id}/complete")
async def complete_study_block(plan_id: str, day: int, block_id: str, payload: StudyBlockCompletePayload, request: Request):
    await run_in_threadpool(learning_loop_service.assert_unlocked, user_id=payload.user_id, plan_id=plan_id, day=day)
    record = await run_in_threadpool(daily_learning_service.update_block, user_id=payload.user_id, plan_id=plan_id, day=day, block_id=block_id, status="completed", progress=1, actual_seconds=payload.actual_seconds, answer=payload.answer)
    await run_in_threadpool(learning_loop_service.sync_content_progress, user_id=payload.user_id, plan_id=plan_id, day=day, session=record["session"])
    return envelope(data=record, request_id=request_id_for(request))

@app.post("/api/plans/{plan_id}/days/{day}/blocks/{block_id}/feedback", status_code=201)
async def study_block_feedback(plan_id: str, day: int, block_id: str, payload: StudyBlockFeedbackPayload, request: Request):
    session = await run_in_threadpool(daily_learning_service.get_session, user_id=payload.user_id, plan_id=plan_id, day=day)
    block = next((item for item in session.get("study_blocks", []) if item["block_id"] == block_id), None)
    if not block: raise HTTPException(status_code=404, detail="Study block not found")
    record = await run_in_threadpool(learning_loop_service.feedback, user_id=payload.user_id, plan_id=plan_id, day=day, feedback_type=payload.feedback_type, concept_ids=block.get("concept_ids", []), note=payload.note, content_progress=session.get("session_progress", {}).get("fraction"))
    await run_in_threadpool(daily_learning_service.update_block, user_id=payload.user_id, plan_id=plan_id, day=day, block_id=block_id, status=block.get("progress_state", {}).get("status", "available"), progress=block.get("progress_state", {}).get("progress", 0), feedback={"feedback_type":payload.feedback_type,"note":payload.note})
    return envelope(data=record, request_id=request_id_for(request))

@app.post("/api/plans/{plan_id}/days/{day}/blocks/{block_id}/regenerate", status_code=201)
async def regenerate_study_block(plan_id: str, day: int, block_id: str, payload: StudyBlockRegeneratePayload, request: Request):
    record = await run_in_threadpool(daily_learning_service.regenerate_block, user_id=payload.user_id, plan_id=plan_id, day=day, block_id=block_id)
    return envelope(data=record, request_id=request_id_for(request), mode=record.get("generation_mode", "fallback"))

@app.get("/api/resources/{resource_id}/reading-context")
async def get_resource_reading_context(resource_id: str, user_id: str, request: Request):
    record = await run_in_threadpool(daily_learning_service.resource_context, user_id=user_id, resource_id=resource_id)
    return envelope(data=record, request_id=request_id_for(request))

@app.get("/api/plans/{plan_id}/days/{day}/resources")
async def get_daily_resources(plan_id: str, day: int, user_id: str, request: Request):
    try:
        try:
            await run_in_threadpool(
                learning_loop_service.assert_unlocked,
                user_id=user_id,
                plan_id=plan_id,
                day=day,
            )
        except LearningLoopNotFoundError:
            # Compatibility path for isolated DailyContent service tests and
            # legacy activated plans that do not yet have loop runtime rows.
            pass
        resources = await run_in_threadpool(
            daily_learning_service.resources,
            user_id=user_id,
            plan_id=plan_id,
            day=day,
        )
    except DailyLearningNotFoundError:
        raise HTTPException(status_code=404, detail="Plan or learning day not found")
    except DailyLearningValidationError as exc:
        return JSONResponse(status_code=400, content=error_envelope(
            code="daily_resources_unavailable", message=str(exc), request_id=request_id_for(request)))
    return envelope(data=resources, request_id=request_id_for(request))

@app.get("/api/paths/{path_id}/progress")
async def get_path_progress(path_id: str, user_id: str, request: Request):
    record = await run_in_threadpool(
        learning_loop_service.progress, user_id=user_id, path_id=path_id)
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/plans/{plan_id}/days/{day}/start")
async def start_learning_day(
    plan_id: str, day: int, payload: DocumentOwnerPayload, request: Request
):
    record = await run_in_threadpool(
        learning_loop_service.start_day,
        user_id=payload.user_id, plan_id=plan_id, day=day)
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/plans/{plan_id}/days/{day}/feedback", status_code=201)
async def save_daily_feedback(
    plan_id: str, day: int, payload: DailyFeedbackPayload, request: Request
):
    record = await run_in_threadpool(
        learning_loop_service.feedback,
        user_id=payload.user_id,
        plan_id=plan_id,
        day=day,
        feedback_type=payload.feedback_type,
        concept_ids=payload.concept_ids,
        note=payload.note,
        content_progress=payload.content_progress,
    )
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/plans/{plan_id}/days/{day}/chat")
async def get_daily_chat(plan_id: str, day: int, user_id: str, request: Request):
    record = await run_in_threadpool(
        learning_loop_service.chat_history,
        user_id=user_id, plan_id=plan_id, day=day)
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/chat", status_code=201)
async def contextual_chat(payload: ChatPayload, request: Request):
    record = await run_in_threadpool(
        learning_loop_service.chat,
        user_id=payload.user_id,
        plan_id=payload.plan_id,
        day=payload.day,
        message=payload.message,
        intent=payload.intent,
        content_id=payload.content_id,
        current_block_id=payload.current_block_id,
        completed_block_ids=payload.completed_block_ids,
        current_resource_id=payload.current_resource_id,
    )
    return envelope(
        data=record,
        request_id=request_id_for(request),
        mode=record.get("mode", "fallback"),
    )


@app.get("/api/paths/{path_id}/confusions")
async def get_path_confusions(path_id: str, user_id: str, request: Request):
    record = await run_in_threadpool(
        learning_loop_service.confusion_summary,
        user_id=user_id, path_id=path_id)
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/plans/{plan_id}/days/{day}/quiz")
async def get_daily_quiz(plan_id: str, day: int, user_id: str, request: Request):
    record = await run_in_threadpool(
        learning_loop_service.quiz,
        user_id=user_id, plan_id=plan_id, day=day)
    public_record = {**record, "questions": [
        {key: value for key, value in question.items()
         if key not in {"correct_answer", "expected_terms"}}
        for question in record["questions"]
    ]}
    return envelope(data=public_record, request_id=request_id_for(request))


@app.post("/api/plans/{plan_id}/days/{day}/quiz-attempts", status_code=201)
async def submit_daily_quiz(
    plan_id: str, day: int, payload: QuizAttemptPayload, request: Request
):
    record = await run_in_threadpool(
        learning_loop_service.submit_quiz,
        user_id=payload.user_id,
        plan_id=plan_id,
        day=day,
        answers=[answer.model_dump() for answer in payload.answers],
        duration_seconds=payload.duration_seconds,
    )
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/paths/{path_id}/adaptation-proposals", status_code=201)
async def create_adaptation_proposal(
    path_id: str, payload: AdaptationProposalPayload, request: Request
):
    record = await run_in_threadpool(
        learning_loop_service.create_proposal,
        user_id=payload.user_id, path_id=path_id)
    return envelope(data=record, request_id=request_id_for(request))


@app.get("/api/adaptation-proposals/{proposal_id}")
async def get_adaptation_proposal(
    proposal_id: str, user_id: str, request: Request
):
    record = await run_in_threadpool(
        learning_loop_service.proposal,
        user_id=user_id, proposal_id=proposal_id)
    return envelope(data=record, request_id=request_id_for(request))


@app.post("/api/adaptation-proposals/{proposal_id}/decision")
async def decide_adaptation_proposal(
    proposal_id: str, payload: AdaptationDecisionPayload, request: Request
):
    record = await run_in_threadpool(
        learning_loop_service.decide_proposal,
        user_id=payload.user_id,
        proposal_id=proposal_id,
        decision=payload.decision,
        modifications=payload.modifications,
    )
    return envelope(data=record, request_id=request_id_for(request))

@app.get("/api/health")
async def health(request: Request):
    checks = capabilities()
    return envelope(
        data={
            "status": "ok",
            "service_ready": True,
            "local_demo_shared_mode": LOCAL_DEMO_SHARED_MODE,
            "dependencies": checks,
        },
        request_id=request_id_for(request),
    )


@app.get("/api/capabilities")
async def get_capabilities(request: Request):
    return envelope(data=capabilities(), request_id=request_id_for(request))


@app.get("/", include_in_schema=False)
async def pathly_home():
    return FileResponse(PATHLY_DIR / "index.html", media_type="text/html")


@app.get("/pathly-ui.css", include_in_schema=False)
async def pathly_product_styles():
    return FileResponse(PATHLY_DIR / "pathly-ui.css", media_type="text/css")


@app.get("/pathly-app.js", include_in_schema=False)
async def pathly_product_script():
    return FileResponse(PATHLY_DIR / "pathly-app.js", media_type="text/javascript")


@app.get("/vendor/mathjax/tex-svg.js", include_in_schema=False)
async def pathly_math_renderer():
    """Local MathJax bundle so formula rendering does not depend on CDN access."""
    return FileResponse(PATHLY_DIR / "vendor" / "mathjax" / "tex-svg.js", media_type="text/javascript")































