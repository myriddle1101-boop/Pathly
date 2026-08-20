"""Adapters between the Pathly HTTP API and the existing learning backend."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PATHLY_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
if str(KG_DIR) not in sys.path:
    sys.path.insert(0, str(KG_DIR))

from env_loader import load_project_env  # noqa: E402

load_project_env()

from agents.planning_agent import PlanningAgent  # noqa: E402
from infra.profile_schema import LearnerProfile  # noqa: E402
from infra.profile_store import ProfileStore  # noqa: E402
from pathly_contracts import build_path_context, profile_v2_from_legacy  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402


PROFILE_DB = Path(os.getenv("PATHLY_PROFILE_DB", str(KG_DIR / "data" / "learner_profiles.db"))).resolve()
PLAN_DB = Path(os.getenv("PATHLY_PLAN_DB", str(KG_DIR / "data" / "pathly_learning.db"))).resolve()
CALIBRATED_KG = Path(
    os.getenv(
        "PATHLY_KG_JSON",
        str(KG_DIR / "web_data" / "global" / "global_knowledge_graph_calibrated.json"),
    )
).resolve()
GLOBAL_KG = KG_DIR / "web_data" / "global" / "global_knowledge_graph.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PathlyStore:
    def __init__(self, db_path: Path = PLAN_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_plans (
                    plan_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            # A user can own several independent learning paths. Version
            # belongs to one path (adaptation history), not to the user as a
            # whole. These additive migrations keep existing local databases
            # readable without deleting learner data.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(learning_plans)")}
            if "path_id" not in columns:
                conn.execute("ALTER TABLE learning_plans ADD COLUMN path_id TEXT")
            if "goal_text" not in columns:
                conn.execute("ALTER TABLE learning_plans ADD COLUMN goal_text TEXT")
            if "profile_snapshot_json" not in columns:
                conn.execute("ALTER TABLE learning_plans ADD COLUMN profile_snapshot_json TEXT")
            conn.execute("UPDATE learning_plans SET path_id = plan_id WHERE path_id IS NULL OR path_id = ''")

    def save_plan(
        self,
        user_id: str,
        plan: dict[str, Any],
        mode: str,
        sources: list[str],
        *,
        path_id: str | None = None,
        goal_text: str = "",
        profile_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan_id = str(plan.get("plan_id") or uuid.uuid4())
        plan["plan_id"] = plan_id
        learning_path_id = path_id or str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM learning_plans WHERE user_id = ? AND path_id = ?",
                (user_id, learning_path_id),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO learning_plans
                    (plan_id, user_id, version, status, mode, sources_json,
                     plan_json, created_at, path_id, goal_text, profile_snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    user_id,
                    version,
                    "active",
                    mode,
                    json.dumps(sources, ensure_ascii=False),
                    json.dumps(plan, ensure_ascii=False),
                    now_iso(),
                    learning_path_id,
                    goal_text,
                    json.dumps(profile_snapshot or {}, ensure_ascii=False),
                ),
            )
        return self.get_plan(plan_id) or {}

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM learning_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        return self._row(row) if row else None

    def list_plans(self, user_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM learning_plans WHERE user_id = ? ORDER BY version DESC", (user_id,)
            ).fetchall()
        return [self._row(row) for row in rows]

    def delete_path(self, user_id: str, path_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT plan_id FROM learning_plans WHERE user_id = ? AND path_id = ?",
                (user_id, path_id),
            ).fetchall()
            if not rows:
                return 0
            conn.execute(
                "DELETE FROM learning_plans WHERE user_id = ? AND path_id = ?",
                (user_id, path_id),
            )
        return len(rows)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "plan_id": row["plan_id"],
            "path_id": row["path_id"] or row["plan_id"],
            "user_id": row["user_id"],
            "version": row["version"],
            "status": row["status"],
            "mode": row["mode"],
            "sources": json.loads(row["sources_json"]),
            "created_at": row["created_at"],
            "goal_text": row["goal_text"] or "",
            "profile_snapshot": json.loads(row["profile_snapshot_json"] or "{}"),
            "path_context": (
                json.loads(row["path_context_json"] or "{}")
                if "path_context_json" in row.keys()
                else {}
            ),
            "plan": json.loads(row["plan_json"]),
        }


def profile_from_payload(payload: dict[str, Any], existing: LearnerProfile | None = None) -> LearnerProfile:
    base = existing.to_dict() if existing else {}
    merged = {**base, **payload}
    return LearnerProfile(
        user_id=str(merged.get("user_id") or f"demo-{uuid.uuid4().hex[:10]}"),
        name=str(merged.get("name") or "Pathly Learner"),
        academic_level=str(merged.get("academic_level") or "undergraduate"),
        domain=str(merged.get("domain") or "computer science"),
        goal_text=str(merged.get("goal_text") or "Learn neural network basics"),
        target_days=max(1, min(90, int(merged.get("target_days") or 7))),
        daily_minutes=max(15, min(480, int(merged.get("daily_minutes") or 75))),
        prior_knowledge_level=int(merged.get("prior_knowledge_level") or 3),
        math_foundation=int(merged.get("math_foundation") or 3),
        programming_foundation=int(merged.get("programming_foundation") or 4),
        self_regulation=int(merged.get("self_regulation") or 3),
        interest_tags=list(merged.get("interest_tags") or ["neural networks"]),
        preferred_style=str(merged.get("preferred_style") or "intuitive_with_code"),
        motivation_level=int(merged.get("motivation_level") or 4),
        confidence_level=int(merged.get("confidence_level") or 3),
        anxiety_level=int(merged.get("anxiety_level") or 2),
        known_topics=list(merged.get("known_topics") or []),
        skill_tree=dict(merged.get("skill_tree") or {}),
        preferred_examples=list(merged.get("preferred_examples") or ["code", "visual analogy"]),
        pace_preference=str(merged.get("pace_preference") or "medium"),
        mastery_vector=dict(merged.get("mastery_vector") or {}),
        completed_topics=list(merged.get("completed_topics") or []),
        current_day=int(merged.get("current_day") or 1),
        last_practice=merged.get("last_practice"),
    )


class PlanningUnavailableError(RuntimeError):
    def __init__(self, attempts: list[str]):
        super().__init__("Planning is temporarily unavailable")
        self.attempts = attempts


class PlanningClarificationRequiredError(RuntimeError):
    def __init__(self, mappings: list[dict[str, Any]]):
        super().__init__("Planning requires goal clarification")
        self.mappings = mappings

class PathlyBackend:
    def __init__(self):
        self.profiles = ProfileStore(str(PROFILE_DB))
        self.plans = PathlyStore()
        self.contracts = PathlyContractStore(self.plans.db_path)

    def save_profile(
        self,
        profile: LearnerProfile,
        contract_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = contract_payload or {}
        self.profiles.upsert_profile(profile)
        self.contracts.save_profile_extension(
            profile.user_id,
            cognitive_traits=payload.get("cognitive_traits"),
            affective_defaults=payload.get("affective_defaults"),
            inference_records=payload.get("inference_records"),
            profile_version=int(payload.get("profile_version") or 2),
        )
        return self.get_profile_record(profile.user_id) or {}

    def get_profile_record(self, user_id: str) -> dict[str, Any] | None:
        profile = self.profiles.get_profile(user_id)
        if not profile:
            return None
        extension = self.contracts.get_profile_extension(user_id)
        v2 = profile_v2_from_legacy(profile, extension).to_dict()
        # Flat legacy fields remain temporarily for current UI and agents.
        return {**profile.to_dict(), **v2}

    def create_plan(
        self,
        user_id: str,
        goal_text: str | None = None,
        path_id: str | None = None,
        confirmed_mappings: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        profile = self.profiles.get_profile(user_id)
        if not profile:
            raise KeyError("profile_not_found")
        if goal_text:
            profile.goal_text = goal_text
            self.save_profile(profile)

        attempts: list[tuple[str, str | None, list[str]]] = []
        if os.getenv("NEO4J_PASSWORD"):
            attempts.append(("neo4j", None, ["sqlite_profile", "neo4j"]));
        graph_path = CALIBRATED_KG if CALIBRATED_KG.exists() else GLOBAL_KG
        attempts.append(("json", str(graph_path), ["sqlite_profile", "kg_json"]))

        errors = []
        clarifications = []
        for backend, path, sources in attempts:
            try:
                planner = PlanningAgent(graph_path=path, kg_backend=backend)
                if confirmed_mappings:
                    plan = planner.generate_plan(
                        profile.goal_text,
                        profile,
                        confirmed_mappings=confirmed_mappings,
                    )
                else:
                    plan = planner.generate_plan(profile.goal_text, profile)
                mapping = plan.get("mapping", {})
                unresolved = list(plan.get("uncovered_constraints", []))
                pending = list(mapping.get("confirmation_required", []))
                if unresolved or pending:
                    clarifications.append({
                        "backend": backend,
                        "sources": sources,
                        "unmatched_terms": unresolved,
                        "confirmation_required": pending,
                        "mapping_explanations": mapping.get("mapping_explanations", []),
                    })
                    continue
                if plan.get("days") and any(day.get("focus_topics") for day in plan["days"]):
                    mode = "live" if backend == "neo4j" else "fallback"
                    profile_snapshot = self.get_profile_record(user_id) or profile.to_dict()
                    record = self.plans.save_plan(
                        user_id,
                        plan,
                        mode,
                        sources,
                        path_id=path_id,
                        goal_text=profile.goal_text,
                        profile_snapshot=profile_snapshot,
                    )
                    context = build_path_context(
                        path_id=record["path_id"],
                        user_id=user_id,
                        goal_text=profile.goal_text,
                        target_days=profile.target_days,
                        max_daily_minutes=profile.daily_minutes,
                        profile_snapshot=profile_snapshot,
                        plan=plan,
                    ).to_dict()
                    self.contracts.save_path_context(record["plan_id"], context)
                    return self.plans.get_plan(record["plan_id"]) or {**record, "path_context": context}
                errors.append(f"{backend}: empty plan")
            except Exception as exc:
                errors.append(f"{backend}: {type(exc).__name__}")

        if clarifications:
            raise PlanningClarificationRequiredError(clarifications)
        raise PlanningUnavailableError(errors)


