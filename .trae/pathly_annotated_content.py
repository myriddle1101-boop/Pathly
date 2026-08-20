"""Source-first annotated daily learning sessions for Content Agent v2.

This module is intentionally parallel to pathly_daily.py. It does not replace
or mutate the existing Study Blocks / daily-content-v2 implementation.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pathly_daily import DailyLearningNotFoundError, EvidencePreparer

ANNOTATED_CONTRACT_VERSION = "annotated-session-v1"
ANNOTATED_AGENT_VERSION = "content-agent-v2-source-first-a8-related-page-sequence"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnnotatedSessionNotFoundError(LookupError):
    pass


class AnnotatedSessionValidationError(ValueError):
    pass


class AnnotatedContentStore:
    """Persistence for the parallel annotated-source experience."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.migrate()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS annotated_daily_sessions(
                    annotated_session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    path_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    source_hash TEXT NOT NULL,
                    contract_version TEXT NOT NULL,
                    source_mode TEXT NOT NULL,
                    session_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, plan_id, day, source_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_annotated_daily_lookup
                    ON annotated_daily_sessions(user_id, plan_id, day, created_at);

                CREATE TABLE IF NOT EXISTS annotated_reading_units(
                    reading_id TEXT PRIMARY KEY,
                    annotated_session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    reading_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_annotated_readings
                    ON annotated_reading_units(user_id, plan_id, day, sequence);

                CREATE TABLE IF NOT EXISTS annotated_reading_progress(
                    user_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    reading_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, plan_id, day, reading_id)
                );

                CREATE TABLE IF NOT EXISTS annotated_exercise_attempts(
                    attempt_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    exercise_id TEXT NOT NULL,
                    answer_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS annotated_source_citations(
                    citation_id TEXT NOT NULL,
                    annotated_session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    citation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(citation_id, annotated_session_id)
                );

                CREATE TABLE IF NOT EXISTS content_agent_v2_implementation_log(
                    entry_id TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    verification_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def latest_session(self, user_id: str, plan_id: str, day: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT session_json FROM annotated_daily_sessions
                WHERE user_id=? AND plan_id=? AND day=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, plan_id, int(day)),
            ).fetchone()
        return json.loads(row["session_json"]) if row else None

    def session_by_hash(self, user_id: str, plan_id: str, day: int, source_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT session_json FROM annotated_daily_sessions
                WHERE user_id=? AND plan_id=? AND day=? AND source_hash=?
                """,
                (user_id, plan_id, int(day), source_hash),
            ).fetchone()
        return json.loads(row["session_json"]) if row else None

    def save_session(self, session: dict[str, Any]) -> dict[str, Any]:
        stamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO annotated_daily_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    session["annotated_session_id"], session["user_id"], session["path_id"],
                    session["plan_id"], int(session["day"]), session["source_hash"],
                    session["contract_version"], session["source_mode"],
                    json.dumps(session, ensure_ascii=False), stamp, stamp,
                ),
            )
            row = conn.execute(
                """
                SELECT annotated_session_id, session_json FROM annotated_daily_sessions
                WHERE user_id=? AND plan_id=? AND day=? AND source_hash=?
                """,
                (session["user_id"], session["plan_id"], int(session["day"]), session["source_hash"]),
            ).fetchone()
            saved = json.loads(row["session_json"])
            session_id = row["annotated_session_id"]
            conn.execute("DELETE FROM annotated_reading_units WHERE annotated_session_id=?", (session_id,))
            conn.execute("DELETE FROM annotated_source_citations WHERE annotated_session_id=?", (session_id,))
            conn.executemany(
                "INSERT OR REPLACE INTO annotated_reading_units VALUES(?,?,?,?,?,?,?,?)",
                [
                    (
                        reading["reading_id"], session_id, saved["user_id"], saved["plan_id"],
                        int(saved["day"]), int(reading["sequence"]), reading["source_type"],
                        json.dumps(reading, ensure_ascii=False),
                    )
                    for reading in saved.get("reading_sequence", [])
                ],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO annotated_source_citations VALUES(?,?,?,?,?)",
                [
                    (
                        citation["citation_id"], session_id, saved["user_id"],
                        json.dumps(citation, ensure_ascii=False), stamp,
                    )
                    for citation in saved.get("citations", [])
                ],
            )
        return saved

    def reading_progress(self, user_id: str, plan_id: str, day: int) -> dict[str, dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM annotated_reading_progress WHERE user_id=? AND plan_id=? AND day=?",
                (user_id, plan_id, int(day)),
            ).fetchall()
        return {
            row["reading_id"]: {
                "status": row["status"],
                "response": json.loads(row["response_json"]) if row["response_json"] else None,
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def save_reading_progress(self, *, user_id: str, plan_id: str, day: int, reading_id: str, status: str, response: Any = None) -> dict[str, Any]:
        stamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO annotated_reading_progress VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(user_id, plan_id, day, reading_id)
                DO UPDATE SET status=excluded.status, response_json=COALESCE(excluded.response_json, annotated_reading_progress.response_json), updated_at=excluded.updated_at
                """,
                (user_id, plan_id, int(day), reading_id, status, json.dumps(response, ensure_ascii=False) if response is not None else None, stamp),
            )
        return self.reading_progress(user_id, plan_id, day)[reading_id]

    def save_exercise_attempt(self, *, user_id: str, plan_id: str, day: int, exercise_id: str, answer: Any) -> dict[str, Any]:
        record = {
            "attempt_id": str(uuid.uuid4()),
            "user_id": user_id,
            "plan_id": plan_id,
            "day": int(day),
            "exercise_id": exercise_id,
            "answer": answer,
            "created_at": now_iso(),
        }
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO annotated_exercise_attempts VALUES(?,?,?,?,?,?,?)",
                (record["attempt_id"], user_id, plan_id, int(day), exercise_id, json.dumps(answer, ensure_ascii=False), record["created_at"]),
            )
        return record
    def log_progress(self, *, stage: str, status: str, summary: str, verification: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "entry_id": str(uuid.uuid4()),
            "stage": stage,
            "status": status,
            "summary": summary,
            "verification": verification,
            "created_at": now_iso(),
        }
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO content_agent_v2_implementation_log VALUES(?,?,?,?,?,?)",
                (
                    entry["entry_id"], stage, status, summary,
                    json.dumps(verification, ensure_ascii=False), entry["created_at"],
                ),
            )
        return entry


class AnnotatedContentService:
    def __init__(self, backend, store: AnnotatedContentStore, daily_learning_service):
        self.backend = backend
        self.store = store
        self.daily = daily_learning_service

    def plan(self, user_id: str, plan_id: str) -> dict[str, Any]:
        record = self.backend.plans.get_plan(plan_id)
        if not record or record.get("user_id") != user_id:
            raise DailyLearningNotFoundError(plan_id)
        return record

    def with_progress(self, session: dict[str, Any]) -> dict[str, Any]:
        progress = self.store.reading_progress(session["user_id"], session["plan_id"], int(session["day"]))
        readings = []
        completed = 0
        for reading in session.get("reading_sequence", []):
            row = progress.get(reading["reading_id"]) or {"status": "available", "response": None}
            if row.get("status") == "completed":
                completed += 1
            readings.append({**reading, "progress_state": row})
        total = len(readings)
        return {**session, "reading_sequence": readings, "annotated_progress": {"completed_readings": completed, "total_readings": total, "fraction": round(completed / total, 4) if total else 0}}

    def update_reading(self, *, user_id: str, plan_id: str, day: int, reading_id: str, status: str = "completed", response: Any = None) -> dict[str, Any]:
        session = self.get_session(user_id=user_id, plan_id=plan_id, day=day)
        reading = next((item for item in session.get("reading_sequence", []) if item["reading_id"] == reading_id), None)
        if not reading:
            raise AnnotatedSessionNotFoundError(reading_id)
        if status not in {"available", "in_progress", "completed"}:
            raise AnnotatedSessionValidationError("Unsupported annotated reading status")
        progress = self.store.save_reading_progress(user_id=user_id, plan_id=plan_id, day=day, reading_id=reading_id, status=status, response=response)
        return {"reading_progress": progress, "session": self.get_session(user_id=user_id, plan_id=plan_id, day=day)}

    def submit_exercise(self, *, user_id: str, plan_id: str, day: int, exercise_id: str, answer: Any) -> dict[str, Any]:
        session = self.get_session(user_id=user_id, plan_id=plan_id, day=day)
        exercise = next((item for item in session.get("guided_exercises", []) if item["exercise_id"] == exercise_id), None)
        if not exercise:
            raise AnnotatedSessionNotFoundError(exercise_id)
        grading = self.grade_objective_exercise(exercise, answer)
        attempt_payload = {"answer": answer, "grading": grading}
        attempt = self.store.save_exercise_attempt(user_id=user_id, plan_id=plan_id, day=day, exercise_id=exercise_id, answer=attempt_payload)
        return {"attempt": attempt, "grading": grading, "expected_answer_outline": exercise.get("expected_answer_outline", []), "exercise": exercise}

    @staticmethod
    def grade_objective_exercise(exercise: dict[str, Any], answer: Any) -> dict[str, Any]:
        submitted = answer.get("answers") if isinstance(answer, dict) else None
        if not isinstance(submitted, dict):
            submitted = {}
        results = []
        correct = 0
        for question in exercise.get("questions", []) or []:
            qid = str(question.get("question_id"))
            qtype = question.get("question_type")
            expected = question.get("correct_answer")
            value = submitted.get(qid)
            if qtype == "multi_select":
                expected_set = {str(x) for x in (expected or [])}
                value_set = {str(x) for x in (value or [])} if isinstance(value, list) else set()
                is_correct = value_set == expected_set
            else:
                is_correct = str(value) == str(expected)
            if is_correct:
                correct += 1
            results.append({
                "question_id": qid,
                "question_type": qtype,
                "submitted_answer": value,
                "correct_answer": expected,
                "correct": is_correct,
                "explanation": question.get("explanation") or "Review the source annotation for this question.",
            })
        total = len(results)
        score = round(correct / total, 4) if total else 0
        return {"score": score, "correct": correct, "total": total, "passed": score >= 0.7, "results": results}


    def source_context(self, *, user_id: str, plan_id: str, day: int, reading_id: str) -> dict[str, Any]:
        session = self.get_session(user_id=user_id, plan_id=plan_id, day=day)
        reading = next((item for item in session.get("reading_sequence", []) if item["reading_id"] == reading_id), None)
        if not reading:
            raise AnnotatedSessionNotFoundError(reading_id)
        chunks: list[dict[str, Any]] = []
        document_id = reading.get("document_id")
        if reading.get("source_type") == "private_document" and document_id:
            for row in self.daily.documents.get_chunks(user_id, document_id):
                page_start = row.get("page_start")
                page_end = row.get("page_end")
                target_start = reading.get("page_start")
                target_end = reading.get("page_end") or target_start
                if target_start and page_start and page_end:
                    overlaps = int(page_start) <= int(target_end or target_start) and int(page_end) >= int(target_start)
                    near = abs(int(page_start) - int(target_start)) <= 1
                    if not (overlaps or near):
                        continue
                chunks.append({
                    "chunk_id": row.get("chunk_id"),
                    "chunk_index": row.get("chunk_index"),
                    "page_start": page_start,
                    "page_end": page_end,
                    "text": " ".join(str(row.get("text") or "").split())[:1800],
                    "word_count": row.get("word_count"),
                    "selected": False,
                })
                if len(chunks) >= 5:
                    break
        if not chunks:
            chunks.append({
                "chunk_id": reading_id,
                "chunk_index": 0,
                "page_start": reading.get("page_start"),
                "page_end": reading.get("page_end"),
                "text": reading.get("clean_excerpt") or "No source excerpt is available.",
                "word_count": len(str(reading.get("clean_excerpt") or "").split()),
                "selected": True,
            })
        selected_text = " ".join(str(reading.get("clean_excerpt") or "").split())[:1800]
        for chunk in chunks:
            if selected_text and selected_text[:120] in chunk.get("text", ""):
                chunk["selected"] = True
        return {
            "reading_id": reading_id,
            "source_type": reading.get("source_type"),
            "source_label": reading.get("source_label"),
            "document_id": document_id,
            "document_title": reading.get("document_title"),
            "reading_scope": reading.get("reading_scope"),
            "page_start": reading.get("page_start"),
            "page_end": reading.get("page_end"),
            "selected_excerpt": selected_text,
            "context_chunks": chunks,
            "annotation_targets": [
                {"label": "definition", "instruction": "Find the sentence that defines the concept or states its role."},
                {"label": "mechanism", "instruction": "Find the line that explains what changes or how the idea works."},
                {"label": "application", "instruction": "Find where the material implies how the concept is used."},
            ],
            "access": {
                "mode": "private_chunk_context" if reading.get("source_type") == "private_document" else "excerpt_context",
                "full_pdf_url": None,
                "reason": "Only the selected source context is shown here; original private files are not exposed through a public URL.",
            },
        }

    @staticmethod
    def topic_ids(plan_day: dict[str, Any]) -> list[str]:
        seen: dict[str, None] = {}
        for activity in plan_day.get("activities", []) or []:
            for concept_id in activity.get("concept_ids", []) or []:
                value = str(concept_id)
                if value:
                    seen.setdefault(value, None)
        return list(seen.keys())

    @staticmethod
    def concept_labels(record: dict[str, Any]) -> dict[str, str]:
        labels = {}
        for index, node in enumerate(record.get("plan", {}).get("concept_path", []) or [], 1):
            cid = str(node.get("concept_id") or "")
            if cid:
                labels[cid] = str(
                    node.get("display_name") or node.get("requested_term") or node.get("label") or node.get("name") or cid
                )
                if labels[cid].startswith("private:"):
                    labels[cid] = f"Private concept {index}"
        return labels

    def source_hash(self, *, record: dict[str, Any], plan_day: dict[str, Any], contexts: list[dict[str, Any]]) -> str:
        source = {
            "contract_version": ANNOTATED_CONTRACT_VERSION,
            "agent_version": ANNOTATED_AGENT_VERSION,
            "plan_id": record["plan_id"],
            "plan_version": record.get("version"),
            "day": int(plan_day["day"]),
            "activities": plan_day.get("activities", []),
            "context_signals": [
                {
                    "concept_id": c.get("concept_id"),
                    "kg_source": c.get("kg_source"),
                    "private_ids": [x.get("id") or x.get("chunk_id") for x in c.get("private_chunks", [])],
                    "public_ids": [x.get("id") or x.get("chunk_id") for x in c.get("public_chunks", [])],
                }
                for c in contexts
            ],
        }
        return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

    @staticmethod
    def document_title(context: dict[str, Any], evidence: dict[str, Any]) -> str:
        document_id = evidence.get("document_id")
        for chunk in [*(context.get("private_chunks") or []), *(context.get("public_chunks") or [])]:
            metadata = chunk.get("metadata") or {}
            if document_id and metadata.get("document_id") != document_id:
                continue
            for key in ("display_name", "filename", "document_title", "title", "source"):
                value = metadata.get(key)
                if value:
                    return str(value)
        if evidence.get("source_type") == "private_document":
            return "Uploaded PDF excerpt"
        if evidence.get("source_type") == "public_rag":
            return "Public learning resource"
        return "Pathly-generated reading"

    @staticmethod
    def _sentences(text: str, limit: int = 4) -> list[str]:
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            return []
        parts = []
        current = []
        for token in cleaned.split(" "):
            current.append(token)
            if token.endswith((".", "?", "!", ";")) and len(" ".join(current)) > 35:
                parts.append(" ".join(current).strip())
                current = []
            if len(parts) >= limit:
                break
        if current and len(parts) < limit:
            parts.append(" ".join(current).strip())
        return [x[:320] for x in parts if x]

    @staticmethod
    def _concept_description(context: dict[str, Any], label: str) -> str:
        kg = context.get("kg_context") or {}
        concept = kg.get("concept") or {}
        for key in ("description", "definition", "summary"):
            value = concept.get(key) if isinstance(concept, dict) else None
            if value:
                return str(value)
        return f"{label} is one of today's scheduled concepts. The selected material is used to define its role, mechanism, practical use, and boundary."

    @staticmethod
    def _profile_teaching_style(profile: dict[str, Any]) -> str:
        style = str(profile.get("learning_style") or profile.get("affective_defaults", {}).get("learning_style") or "steady")
        examples = profile.get("preferred_examples") or profile.get("affective_defaults", {}).get("preferred_examples") or []
        if isinstance(examples, str):
            examples = [examples]
        if "hands" in style or "code" in examples:
            return "hands-on"
        if "theory" in style:
            return "theory-first"
        return "source-first"

    _GENERIC_ALIGNMENT_TERMS = {"ai", "application", "applications", "concept", "concepts", "data", "learning", "machine", "model", "models", "system", "systems", "introduction", "basic", "basics", "overview", "method", "methods"}
    # These terms identify a page's concrete subject. A generic word such as dataset must not override them.
    _PAGE_TOPIC_TERMS = {"bagging", "bootstrap", "boosting", "ensemble", "regularization", "gradient", "descent", "backpropagation", "neural", "convolution", "transformer", "attention", "embedding", "retrieval", "rag", "regression", "classification", "clustering", "reinforcement", "xor", "separability", "overfitting"}

    @classmethod
    def _alignment_terms(cls, label: str) -> list[str]:
        raw_terms = re.findall(r"[a-z0-9]{2,}", str(label or "").lower())
        terms = [term for term in raw_terms if term not in cls._GENERIC_ALIGNMENT_TERMS]
        # A source often uses a standard acronym (RAG, KG) while the path stores the expanded label.
        expanded_words = [term for term in raw_terms if term not in cls._GENERIC_ALIGNMENT_TERMS]
        if len(expanded_words) >= 2:
            acronym = "".join(word[0] for word in expanded_words)
            if len(acronym) >= 2:
                terms.append(acronym)
        return list(dict.fromkeys(terms))

    @classmethod
    def source_alignment(cls, item: dict[str, Any], label: str) -> dict[str, Any]:
        """Reject a source when its visible page cannot support the scheduled concept."""
        terms = cls._alignment_terms(label)
        section_text = str(item.get("section_title") or "").lower()
        excerpt = str(item.get("clean_text") or "").lower()
        body = " ".join((section_text, excerpt))
        # The title/first lines normally carry the page's primary topic, while later lines can contain generic context words.
        topic_window = f"{section_text} {excerpt[:260]}"
        page_topics = sorted(term for term in cls._PAGE_TOPIC_TERMS if re.search(rf"\b{re.escape(term)}\b", topic_window))
        matched = [term for term in terms if re.search(rf"\b{re.escape(term)}\b", body)]
        relevance = float(item.get("relevance_score") or 0.0)
        coverage = len(matched) / len(terms) if terms else 0.0
        score = round(min(1.0, 0.75 * coverage + 0.25 * max(0.0, min(1.0, relevance))), 4)
        if not terms:
            return {"status": "rejected", "score": 0.0, "matched_terms": [], "page_topics": page_topics, "reason": "The scheduled concept is too broad to anchor this specific source page."}
        if page_topics and not set(page_topics).intersection(terms):
            return {"status": "rejected", "score": score, "matched_terms": matched, "page_topics": page_topics, "reason": f"The page's main topic is {', '.join(page_topics)}, not {label}."}
        if not matched:
            return {"status": "rejected", "score": score, "matched_terms": [], "page_topics": page_topics, "reason": "The source page does not mention the scheduled concept's specific terms."}
        if score < 0.35:
            return {"status": "weak", "score": score, "matched_terms": matched, "page_topics": page_topics, "reason": "The source has only weak evidence for the scheduled concept."}
        return {"status": "aligned", "score": score, "matched_terms": matched, "page_topics": page_topics, "reason": "The source page directly supports the scheduled concept."}

    @classmethod
    def related_page_sequence(cls, anchor: dict[str, Any], candidates: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
        """Build a bounded, ordered page sequence around the best aligned anchor page."""
        document_id = anchor.get("document_id")
        anchor_page = anchor.get("page_start")
        if not document_id or not anchor_page:
            return []
        anchor_page = int(anchor_page)
        selected: list[dict[str, Any]] = []
        seen_pages: set[int] = set()
        for candidate in candidates:
            if candidate.get("document_id") != document_id or not candidate.get("page_start"):
                continue
            page = int(candidate["page_start"])
            alignment = candidate.get("source_alignment") or cls.source_alignment(candidate, label)
            same_section = bool(anchor.get("section_title") and candidate.get("section_title") == anchor.get("section_title"))
            if page != anchor_page and alignment.get("status") != "aligned" and not (same_section and abs(page - anchor_page) <= 2):
                continue
            if abs(page - anchor_page) > 3 and not same_section:
                continue
            if page in seen_pages:
                continue
            seen_pages.add(page)
            selected.append({"page_start": page, "page_end": int(candidate.get("page_end") or page), "section_title": candidate.get("section_title") or label, "clean_excerpt": candidate.get("clean_text") or "", "evidence_id": candidate.get("evidence_id"), "relevance_score": candidate.get("relevance_score"), "alignment_score": alignment.get("score"), "role": "anchor" if page == anchor_page else ("context_before" if page < anchor_page else "context_after")})
        if anchor_page not in seen_pages:
            selected.append({"page_start": anchor_page, "page_end": int(anchor.get("page_end") or anchor_page), "section_title": anchor.get("section_title") or label, "clean_excerpt": anchor.get("clean_text") or "", "evidence_id": anchor.get("evidence_id"), "relevance_score": anchor.get("relevance_score"), "alignment_score": (anchor.get("source_alignment") or {}).get("score"), "role": "anchor"})
        selected.sort(key=lambda item: (int(item["page_start"]), 0 if item["role"] == "anchor" else 1))
        return selected[:6]
    @staticmethod
    def _generated_evidence(concept_id: str, labels: dict[str, str], alignment_reason: str) -> dict[str, Any]:
        label = labels.get(concept_id, concept_id)
        return {
            "evidence_id": f"generated:{concept_id}", "concept_id": concept_id,
            "clean_text": f"{label} is introduced here as a learning concept in your path. Start by asking what problem it solves, what inputs it uses, what output it produces, and how it helps with the goal. This fallback source is generated because no suitable source page could be matched to this exact concept.",
            "source_type": "generated_fallback", "page_start": None, "page_end": None,
            "section_title": label, "quality_flags": ["generated_fallback"],
            "source_alignment": {"status": "generated", "score": 0.0, "matched_terms": [], "reason": alignment_reason},
        }

    def build_readings(self, *, record, plan_day, contexts, evidence, labels) -> tuple[list[dict[str, Any]], str]:
        selected = []
        alignment_rejections = []
        for concept_id in self.topic_ids(plan_day)[:4] or ["today"]:
            label = labels.get(concept_id, concept_id)
            candidates = [dict(item) for item in evidence if str(item.get("concept_id")) == str(concept_id)]
            aligned = []
            for candidate in candidates:
                alignment = self.source_alignment(candidate, label)
                candidate["source_alignment"] = alignment
                if alignment["status"] == "aligned":
                    aligned.append(candidate)
                else:
                    alignment_rejections.append(alignment["reason"])
            private = [item for item in aligned if item.get("source_type") == "private_document"]
            public = [item for item in aligned if item.get("source_type") == "public_rag"]
            if private:
                chosen = max(private, key=lambda item: float(item.get("source_alignment", {}).get("score", 0)))
                chosen["page_sequence"] = self.related_page_sequence(chosen, candidates, label)
                selected.append(chosen)
            elif public:
                chosen = max(public, key=lambda item: float(item.get("source_alignment", {}).get("score", 0)))
                chosen["page_sequence"] = self.related_page_sequence(chosen, candidates, label)
                selected.append(chosen)
            else:
                selected.append(self._generated_evidence(str(concept_id), labels, alignment_rejections[-1] if alignment_rejections else "No source evidence was available for this concept."))
        real_sources = [item for item in selected if item.get("source_type") != "generated_fallback"]
        source_mode = "private_pdf_first" if any(item.get("source_type") == "private_document" for item in real_sources) else ("public_resource_first" if real_sources else "generated_fallback")
        readings = []
        total_minutes = int(plan_day.get("total_minutes") or 45)
        per_source = max(12, min(45, total_minutes // max(1, len(selected))))
        profile = record.get("profile_snapshot") or {}
        teaching_style = self._profile_teaching_style(profile)
        for sequence, item in enumerate(selected, 1):
            concept_id = str(item.get("concept_id") or "today")
            label = labels.get(concept_id, concept_id)
            context = next((c for c in contexts if c.get("concept_id") == concept_id), {})
            kg = context.get("kg_context") or {}
            prereq = kg.get("prerequisites") or kg.get("prerequisite_concepts") or []
            related = kg.get("related") or kg.get("similar_concepts") or []
            source_type = item.get("source_type") or "generated_fallback"
            document_id = item.get("document_id")
            clean_text = item.get("clean_text") or "No clean excerpt was available."
            excerpt_sentences = self._sentences(clean_text, 4)
            if not excerpt_sentences:
                excerpt_sentences = [clean_text[:260]]
            core_claim = excerpt_sentences[0]
            reading_id = f"reading-day{int(plan_day['day'])}-{sequence:02d}-{hashlib.sha1(str(item.get('evidence_id')).encode()).hexdigest()[:8]}"
            page_label = "retrieved excerpt"
            if item.get("page_start") and item.get("page_end"):
                page_label = f"pages {item.get('page_start')}-{item.get('page_end')}"
            elif item.get("page_start"):
                page_label = f"page {item.get('page_start')}"
            source_walkthrough = []
            for idx, sentence in enumerate(excerpt_sentences[:3], 1):
                source_walkthrough.append({
                    "step": idx,
                    "source_line": sentence,
                    "what_it_means": f"Read this as evidence about how {label} is defined, used, or limited. Do not memorize the wording; translate the claim into your own operational rule.",
                    "why_it_matters": f"This helps you decide when {label} is relevant to {record.get('goal_text') or 'your current learning goal'}.",
                    "check_yourself": f"Can you name the input, process, or output described by this line for {label}?",
                })
            readings.append({
                "reading_id": reading_id,
                "sequence": sequence,
                "source_type": source_type,
                "source_label": "Your uploaded PDF" if source_type == "private_document" else ("Public learning resource" if source_type == "public_rag" else "Pathly-generated fallback"),
                "document_id": document_id,
                "document_title": self.document_title(context, item),
                "page_start": item.get("page_start"),
                "page_end": item.get("page_end"),
                "page_sequence": item.get("page_sequence") or [],
                "section_title": label,
                "source_section_title": item.get("section_title"),
                "source_alignment": item.get("source_alignment") or {"status": "unknown", "score": None, "matched_terms": [], "reason": "Legacy evidence did not include alignment metadata."},
                "linked_concept_ids": [concept_id],
                "estimated_minutes": per_source,
                "reading_scope": {"label": page_label, "page_start": item.get("page_start"), "page_end": item.get("page_end"), "section_title": item.get("section_title") or label},
                "reading_purpose": f"Use this material to understand the definition, mechanism, use case, and limitation of {label}.",
                "clean_excerpt": clean_text,
                "teaching_expansion": {
                    "concept_intro": self._concept_description(context, label),
                    "mental_model": f"Treat {label} as a tool in a pipeline: something goes in, a transformation happens, and a more useful output comes out. While reading, keep asking which part of that pipeline the source is describing.",
                    "worked_interpretation": f"In this material, the important domain statement is: '{core_claim}'. It gives a concrete handle on {label}: what it refers to, what operation is happening, or why the concept exists.",
                    "source_to_goal": f"In practice, {label} matters when you need to explain what the concept does, identify when it applies, or use it in a small example.",
                    "common_traps": [
                        f"Assuming {label} applies without checking its input conditions or assumptions.",
                        f"Confusing {label} with a related concept that solves a different part of the problem.",
                        f"Using the term {label} without explaining the mechanism behind it.",
                    ],
                    "prerequisite_bridge": f"Before this idea is stable, connect it to: {', '.join(map(str, prereq[:3])) if isinstance(prereq, list) and prereq else 'the earlier concepts in your path'}."
                },
                "pathly_annotation": {
                    "read_for": f"Identify the definition, mechanism, use case, and limitation of {label}.",
                    "teaching_note": f"Focus on what {label} does, what assumptions it depends on, and what it cannot explain by itself.",
                    "plain_explanation": f"This material introduces {label} through its role, mechanism, and boundary.",
                    "key_terms": [
                        {"term": label, "meaning": self._concept_description(context, label), "kg_concept_id": concept_id},
                        {"term": "mechanism", "meaning": f"The process or relationship that makes {label} work in this topic.", "kg_concept_id": concept_id},
                        {"term": "limitation", "meaning": f"A condition where {label} is not sufficient or needs another concept.", "kg_concept_id": concept_id},
                    ],
                    "why_it_matters": f"Understanding {label} helps explain the current topic and solve related problems.",
                    "common_confusion": f"Do not confuse {label} with superficially similar concepts; check its assumptions, inputs, and outputs.",
                    "read_this_way": [
                        f"Define {label}: what does it mean in this topic?",
                        "Identify the mechanism: what changes, compares, predicts, retrieves, or represents something?",
                        "Find one concrete use case or example.",
                        "State one limitation or assumption.",
                    ],
                    "personalization_reason": "The explanation emphasizes examples and checks matched to the current concept.",
                },
                "source_walkthrough": source_walkthrough,
                "focus_questions": [
                    f"What problem does {label} help solve?",
                    f"Which sentence best defines {label} or describes how it works?",
                    f"How would you explain {label} to someone without using the source wording?",
                    f"What would be a small concrete example of {label}?",
                ],
                "learner_task": {
                    "prompt": f"Write a 4-part note about {label}: definition, mechanism, one example, and one limitation.",
                    "placeholder": f"{label} means... It works by... For example... A limitation is...",
                    "minimum_words": 60,
                },
            })
        return readings, source_mode

    @staticmethod
    def concept_bridges(readings: list[dict[str, Any]], contexts: list[dict[str, Any]], labels: dict[str, str]) -> list[dict[str, Any]]:
        by_concept: dict[str, list[str]] = {}
        for reading in readings:
            for concept_id in reading.get("linked_concept_ids", []):
                by_concept.setdefault(concept_id, []).append(reading["reading_id"])
        bridges = []
        for concept_id, reading_ids in by_concept.items():
            context = next((c for c in contexts if c.get("concept_id") == concept_id), {})
            kg = context.get("kg_context") or {}
            prereq = kg.get("prerequisites") or kg.get("prerequisite_concepts") or []
            related = kg.get("related") or kg.get("similar_concepts") or []
            bridges.append({
                "bridge_id": f"bridge-{hashlib.sha1(concept_id.encode()).hexdigest()[:8]}",
                "concept_id": concept_id,
                "display_name": labels.get(concept_id, concept_id),
                "source_reading_ids": reading_ids,
                "prerequisites": prereq[:5] if isinstance(prereq, list) else [],
                "next_unlocks": related[:5] if isinstance(related, list) else [],
                "explanation": f"The selected source material gives concrete evidence for {labels.get(concept_id, concept_id)}. The KG adds structure: prerequisite ideas, neighboring concepts, and domain relationships.",
                "learner_takeaway": f"After reading, you should be able to define {labels.get(concept_id, concept_id)}, describe how it works, give one example, and name one limitation.",
                "visual_hint": {"type": "mini_graph", "nodes": [concept_id], "edges": []},
            })
        return bridges

    @staticmethod
    def exercises(readings: list[dict[str, Any]], labels: dict[str, str]) -> list[dict[str, Any]]:
        output = []
        for reading in readings:
            concept_id = reading.get("linked_concept_ids", ["today"])[0]
            label = labels.get(concept_id, concept_id)
            reading_id = reading["reading_id"]
            source_title = reading.get("document_title") or reading.get("source_label") or "the source"
            output.append({
                "exercise_id": f"exercise-{reading_id}",
                "exercise_type": "objective_check",
                "source_reading_ids": [reading_id],
                "linked_concept_ids": [concept_id],
                "title": f"Check your understanding of {label}",
                "prompt": f"Answer these objective questions about {label}.",
                "instructions": [
                    "Use the explanation, source excerpt, and concept notes before answering.",
                    "These questions check the concept definition, mechanism, use case, and limitation.",
                    "You will get immediate deterministic feedback after submission.",
                ],
                "questions": [
                    {
                        "question_id": f"{reading_id}-q1",
                        "question_type": "single_choice",
                        "prompt": f"Which statement best describes {label}?",
                        "options": [
                            {"id": "A", "text": reading.get("teaching_expansion", {}).get("concept_intro") or f"{label} has a defined role, mechanism, and boundary in this topic."},
                            {"id": "B", "text": "A citation style, author-list format, or publication metadata pattern."},
                            {"id": "C", "text": "A random label without a defined role in the topic."},
                            {"id": "D", "text": "A file-management step unrelated to the concept itself."},
                        ],
                        "correct_answer": "A",
                        "explanation": f"The correct option describes the role or meaning of {label}.",
                    },
                    {
                        "question_id": f"{reading_id}-q2",
                        "question_type": "true_false",
                        "prompt": f"{label} can be applied correctly without considering its assumptions, inputs, or limitations.",
                        "options": [
                            {"id": "true", "text": "True"},
                            {"id": "false", "text": "False"},
                        ],
                        "correct_answer": "false",
                        "explanation": f"Correct use of {label} requires knowing when the concept applies and what conditions it depends on.",
                    },
                    {
                        "question_id": f"{reading_id}-q3",
                        "question_type": "multi_select",
                        "prompt": f"Which statements are useful for explaining {label}?",
                        "options": [
                            {"id": "definition", "text": f"What {label} means in this topic"},
                            {"id": "mechanism", "text": f"How {label} works or what relationship it describes"},
                            {"id": "limitation", "text": f"When {label} may not be sufficient or may not apply"},
                            {"id": "metadata", "text": "The author's email address or institution formatting"},
                        ],
                        "correct_answer": ["definition", "mechanism", "limitation"],
                        "explanation": f"A useful explanation of {label} includes its meaning, mechanism, and boundary.",
                    },
                ],
                "expected_answer_outline": [
                    f"Question 1: select the option that describes {label}.",
                    f"Question 2: applying {label} requires checking conditions and limitations.",
                    "Question 3: select definition, mechanism, and limitation.",
                ],
                "scoring": {"type": "deterministic_objective", "pass_threshold": 0.7},
                "learner_response_required": True,
            })
        return output

    @staticmethod
    def citations(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "citation_id": f"citation-{reading['reading_id']}",
                "reading_id": reading["reading_id"],
                "source_type": reading["source_type"],
                "document_id": reading.get("document_id"),
                "document_title": reading.get("document_title"),
                "page_start": reading.get("page_start"),
                "page_end": reading.get("page_end"),
                "excerpt": reading.get("clean_excerpt", "")[:260],
            }
            for reading in readings
        ]

    def generate_session(self, *, user_id: str, plan_id: str, day: int, force: bool = False) -> dict[str, Any]:
        record = self.plan(user_id, plan_id)
        plan_day = self.daily.day(record, day)
        labels = self.concept_labels(record)
        profile = record.get("profile_snapshot") or {}
        concepts = self.topic_ids(plan_day)
        contexts = [self.daily.context(user_id, record["path_id"], concept_id, profile) for concept_id in concepts]
        evidence = EvidencePreparer.prepare(contexts)
        source_hash = self.source_hash(record=record, plan_day=plan_day, contexts=contexts)
        if not force:
            cached = self.store.session_by_hash(user_id, plan_id, day, source_hash)
            if cached and cached.get("content_agent_version") == ANNOTATED_AGENT_VERSION:
                return self.with_progress({**cached, "cache_status": "hit"})
        readings, source_mode = self.build_readings(record=record, plan_day=plan_day, contexts=contexts, evidence=evidence, labels=labels)
        bridges = self.concept_bridges(readings, contexts, labels)
        exercises = self.exercises(readings, labels)
        citations = self.citations(readings)
        total = int(plan_day.get("total_minutes") or sum(r["estimated_minutes"] for r in readings))
        private_count = sum(1 for r in readings if r["source_type"] == "private_document")
        public_count = sum(1 for r in readings if r["source_type"] == "public_rag")
        generated_count = sum(1 for r in readings if r["source_type"] == "generated_fallback")
        session = {
            "contract_version": ANNOTATED_CONTRACT_VERSION,
            "content_agent_version": ANNOTATED_AGENT_VERSION,
            "annotated_session_id": str(uuid.uuid4()),
            "content_id": str(uuid.uuid4()),
            "user_id": user_id,
            "path_id": record["path_id"],
            "plan_id": plan_id,
            "plan_version": record.get("version"),
            "day": int(day),
            "scheduled_minutes": total,
            "source_hash": source_hash,
            "source_mode": source_mode,
            "cache_status": "miss",
            "session_overview": {
                "title": f"Day {int(day)}: Annotated Sources for {record.get('goal_text') or 'today'}",
                "goal_for_today": "Use source material to understand " + (', '.join(labels.get(c, c) for c in concepts[:3]) or "today's concepts") + ".",
                "why_these_sources": "These readings match today's scheduled concepts and available private/public evidence.",
                "estimated_minutes": total,
                "source_summary": {
                    "private_pdf_count": private_count,
                    "public_resource_count": public_count,
                    "generated_fallback_count": generated_count,
                },
            },
            "reading_sequence": readings,
            "concept_bridges": bridges,
            "guided_exercises": exercises,
            "checkpoint": {
                "checkpoint_id": f"checkpoint-day{int(day)}",
                "prompt": "Explain today's main concepts using definition, mechanism, example, and limitation.",
                "required_elements": ["definition", "mechanism", "example or application", "limitation or assumption"],
                "minimum_words": 40,
            },
            "quiz_seed": {
                "source_reading_ids": [r["reading_id"] for r in readings],
                "exercise_ids": [e["exercise_id"] for e in exercises],
                "rule": "Quiz should only cover completed readings, exercises, and concept bridges from this annotated session.",
            },
            "citations": citations,
            "generation_metadata": {
                "contract_version": ANNOTATED_CONTRACT_VERSION,
                "content_agent_version": ANNOTATED_AGENT_VERSION,
                "source_mode": source_mode,
                "private_reading_units": private_count,
                "public_reading_units": public_count,
                "generated_reading_units": generated_count,
                "source_hash": source_hash,
            },
            "created_at": now_iso(),
        }
        self.validate(session)
        return self.with_progress(self.store.save_session(session))

    def get_session(self, *, user_id: str, plan_id: str, day: int) -> dict[str, Any]:
        record = self.plan(user_id, plan_id)
        self.daily.day(record, day)
        session = self.store.latest_session(user_id, plan_id, day)
        if session and session.get("content_agent_version") == ANNOTATED_AGENT_VERSION:
            return self.with_progress(session)
        return self.generate_session(user_id=user_id, plan_id=plan_id, day=day)

    @staticmethod
    def validate(session: dict[str, Any]) -> None:
        if session.get("contract_version") != ANNOTATED_CONTRACT_VERSION:
            raise AnnotatedSessionValidationError("Invalid annotated content contract")
        readings = session.get("reading_sequence") or []
        if not readings:
            raise AnnotatedSessionValidationError("Annotated session requires at least one reading")
        for reading in readings:
            if not reading.get("clean_excerpt") or not reading.get("pathly_annotation"):
                raise AnnotatedSessionValidationError("Every reading needs clean excerpt and annotation")
            if not reading.get("teaching_expansion") or not reading.get("source_walkthrough"):
                raise AnnotatedSessionValidationError("Every reading needs learner-facing teaching expansion and source walkthrough")
            if reading.get("source_type") == "private_document" and str(reading.get("clean_excerpt", "")).startswith("private:"):
                raise AnnotatedSessionValidationError("Private IDs must not be exposed as reading text")
        if not session.get("guided_exercises"):
            raise AnnotatedSessionValidationError("Annotated session requires source-grounded exercises")



