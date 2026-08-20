"""Document-grounded goal interpretation and private KG overlay for Stage O2."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
import uuid

from agents.goal_parser import GoalParser
from agents.topic_mapper import TopicMapper
from infra.kg_repository_factory import create_kg_repository
from pathly_backend import CALIBRATED_KG, GLOBAL_KG
from pathly_documents import DocumentNotFoundError, PrivateDocumentStore
from verified_golden_sources import (
    verified_canonical_concept_name,
    verified_goal_concepts_for_goal,
)
from goal_chain_catalog import resolve_goal_chain


SOURCE_MODES = {"private_plus_kg", "private_only", "kg_only"}
DOCUMENT_ROLES = {"core", "supplementary", "exam_scope", "assignment", "project"}


class GoalInterpretationValidationError(ValueError):
    pass


class GoalInterpretationNotFoundError(KeyError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: str) -> str:
    value = re.sub(r"[-_]+", " ", value.strip().casefold())
    value = re.sub(r"[^\w\s\u3400-\u9fff]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _private_concept_id(user_id: str, term: str) -> str:
    digest = hashlib.sha256(f"{user_id}:{_normalize(term)}".encode("utf-8")).hexdigest()[:16]
    return f"private:{digest}"


class GoalInterpretationStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS goal_interpretations (
                    interpretation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_mode TEXT NOT NULL,
                    interpretation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_goal_interpretations_user
                    ON goal_interpretations(user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS document_concept_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    interpretation_id TEXT NOT NULL,
                    document_id TEXT,
                    user_id TEXT NOT NULL,
                    requested_term TEXT NOT NULL,
                    canonical_concept_id TEXT,
                    private_concept_id TEXT,
                    chunk_ids_json TEXT NOT NULL,
                    mapping_confidence REAL NOT NULL,
                    mapping_reason TEXT NOT NULL,
                    mapping_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_document_evidence_owner
                    ON document_concept_evidence(user_id, document_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, interpretation: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        now = _now_iso()
        interpretation_id = interpretation["interpretation_id"]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO goal_interpretations(
                    interpretation_id, user_id, status, source_mode,
                    interpretation_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(interpretation_id) DO UPDATE SET
                    status=excluded.status,
                    source_mode=excluded.source_mode,
                    interpretation_json=excluded.interpretation_json,
                    updated_at=excluded.updated_at
                """,
                (
                    interpretation_id,
                    interpretation["user_id"],
                    interpretation["status"],
                    interpretation["source_mode"],
                    json.dumps(interpretation, ensure_ascii=False),
                    interpretation.get("created_at") or now,
                    now,
                ),
            )
            conn.execute(
                "DELETE FROM document_concept_evidence WHERE interpretation_id = ?",
                (interpretation_id,),
            )
            conn.executemany(
                """
                INSERT INTO document_concept_evidence(
                    evidence_id, interpretation_id, document_id, user_id,
                    requested_term, canonical_concept_id, private_concept_id,
                    chunk_ids_json, mapping_confidence, mapping_reason,
                    mapping_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["evidence_id"],
                        interpretation_id,
                        item.get("document_id"),
                        interpretation["user_id"],
                        item["requested_term"],
                        item.get("canonical_concept_id"),
                        item.get("private_concept_id"),
                        json.dumps(item.get("chunk_ids") or [], ensure_ascii=False),
                        float(item["mapping_confidence"]),
                        item["mapping_reason"],
                        item["mapping_status"],
                        now,
                        now,
                    )
                    for item in evidence
                ],
            )
        return self.get(interpretation["user_id"], interpretation_id) or {}

    def get(self, user_id: str, interpretation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM goal_interpretations
                WHERE interpretation_id = ? AND user_id = ?
                """,
                (interpretation_id, user_id),
            ).fetchone()
        if not row:
            return None
        data = json.loads(row["interpretation_json"])
        for item in data.get("private_concepts") or []:
            item.setdefault(
                "display_name",
                item.get("requested_term") or "Unrecognized private concept",
            )
        data["status"] = row["status"]
        data["updated_at"] = row["updated_at"]
        return data

    def evidence(self, user_id: str, interpretation_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_concept_evidence
                WHERE interpretation_id = ? AND user_id = ?
                ORDER BY mapping_confidence DESC, requested_term
                """,
                (interpretation_id, user_id),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["chunk_ids"] = json.loads(item.pop("chunk_ids_json") or "[]")
            result.append(item)
        return result


    def accepted_evidence_for_documents(
        self, user_id: str, document_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Return confirmed evidence without crossing the anonymous owner boundary."""
        scoped_ids = list(dict.fromkeys(str(value) for value in document_ids if value))
        if not scoped_ids:
            return []
        placeholders = ",".join("?" for _ in scoped_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT evidence.* FROM document_concept_evidence AS evidence
                JOIN goal_interpretations AS interpretation
                  ON interpretation.interpretation_id = evidence.interpretation_id
                 AND interpretation.user_id = evidence.user_id
                WHERE evidence.user_id = ?
                  AND evidence.document_id IN ({placeholders})
                  AND evidence.mapping_status IN ('accepted', 'accepted_private')
                  AND interpretation.status = 'confirmed'
                ORDER BY evidence.mapping_confidence DESC, evidence.requested_term
                """,
                (user_id, *scoped_ids),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["chunk_ids"] = json.loads(item.pop("chunk_ids_json") or "[]")
            result.append(item)
        return result

class GoalInterpretationService:
    def __init__(
        self,
        store: GoalInterpretationStore,
        documents: PrivateDocumentStore,
    ):
        self.store = store
        self.documents = documents

    def create(
        self,
        *,
        user_id: str,
        goal_text: str,
        source_mode: str,
        document_selections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_id = user_id.strip()
        goal_text = goal_text.strip()
        if not user_id or not goal_text:
            raise GoalInterpretationValidationError("user_id and goal_text are required")
        if source_mode not in SOURCE_MODES:
            raise GoalInterpretationValidationError(f"Unsupported source_mode: {source_mode}")
        selections = [] if source_mode == "kg_only" else list(document_selections or [])
        if source_mode != "kg_only" and not selections:
            raise GoalInterpretationValidationError("This source mode requires at least one document")

        scoped_chunks: list[dict[str, Any]] = []
        normalized_selections = []
        for selection in selections:
            document_id = str(selection.get("document_id") or "")
            document = self.documents.get_document(user_id, document_id)
            if not document:
                raise DocumentNotFoundError(document_id)
            if document.get("parse_status") != "ready":
                raise GoalInterpretationValidationError(
                    f"Document {document_id} is not ready for interpretation"
                )
            normalized = self._normalize_selection(selection, document)
            chunks = self._scoped_chunks(user_id, document_id, normalized)
            normalized["selected_chunk_count"] = len(chunks)
            normalized_selections.append(normalized)
            scoped_chunks.extend(chunks)

        repository, kg_source, repository_warning = self._repository()
        try:
            target_terms = self._goal_terms(goal_text)
            candidates = self._candidate_terms(scoped_chunks, repository)
            term_sources: dict[str, dict[str, Any]] = {}
            for term in target_terms:
                term_sources[_normalize(term)] = {
                    "term": term,
                    "document_id": None,
                    "chunk_ids": [],
                    "origin": "goal",
                }
            for item in candidates:
                key = _normalize(item["term"])
                existing = term_sources.get(key)
                if existing:
                    existing["chunk_ids"] = sorted(
                        set(existing["chunk_ids"]) | set(item["chunk_ids"])
                    )
                    existing["document_id"] = existing["document_id"] or item.get("document_id")
                    existing["origin"] = "goal_and_document"
                else:
                    term_sources[key] = item

            catalog_match = resolve_goal_chain(goal_text)
            catalog_ids = set((catalog_match or (None, {"canonical_path": []}))[1]["canonical_path"])
            evidence = [
                ({
                    "evidence_id": str(uuid.uuid4()), "requested_term": item["term"],
                    "canonical_concept_id": item["term"], "private_concept_id": None,
                    "document_id": item.get("document_id"), "chunk_ids": item.get("chunk_ids") or [],
                    "mapping_confidence": 1.0, "mapping_reason": "approved_goal_chain_catalog",
                    "mapping_status": "accepted",
                } if item["term"] in catalog_ids else self._map_term(
                    user_id=user_id,
                    repository=repository,
                    requested_term=item["term"],
                    document_id=item.get("document_id"),
                    chunk_ids=item.get("chunk_ids") or [],
                    origin=item.get("origin") or "document",
                ))
                for item in term_sources.values()
            ]
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                close()

        canonical = []
        private = []
        pending = []
        for item in evidence:
            if item["mapping_status"] == "accepted":
                canonical.append(
                    {
                        "requested_term": item["requested_term"],
                        "concept_id": item["canonical_concept_id"],
                        "confidence": item["mapping_confidence"],
                        "reason": item["mapping_reason"],
                        "chunk_ids": item["chunk_ids"],
                    }
                )
            elif item["mapping_status"] == "confirmation_required":
                pending.append(
                    {
                        "requested_term": item["requested_term"],
                        "candidate": item["canonical_concept_id"],
                        "confidence": item["mapping_confidence"],
                        "reason": item["mapping_reason"],
                        "chunk_ids": item["chunk_ids"],
                    }
                )
            else:
                private.append(
                    {
                        "requested_term": item["requested_term"],
                        "display_name": item["requested_term"],
                        "private_concept_id": item["private_concept_id"],
                        "confidence": item["mapping_confidence"],
                        "reason": item["mapping_reason"],
                        "chunk_ids": item["chunk_ids"],
                    }
                )

        warnings = []
        if repository_warning:
            warnings.append(repository_warning)
        if source_mode == "private_only" and private:
            warnings.append("Some requested concepts exist only in the private document overlay")
        if source_mode == "private_only" and not scoped_chunks:
            warnings.append("The selected document scope contains no indexed chunks")
        goal_coverage = self._goal_coverage(target_terms, evidence)
        if source_mode != "kg_only" and not goal_coverage["all_goal_terms_in_documents"]:
            warnings.append("Selected documents do not explicitly cover every goal term")
        status = "confirmation_required" if pending or private else "draft"
        interpretation_id = str(uuid.uuid4())
        now = _now_iso()
        interpretation = {
            "interpretation_id": interpretation_id,
            "user_id": user_id,
            "goal_text": goal_text,
            "source_mode": source_mode,
            "status": status,
            "documents": normalized_selections,
            "target_terms": target_terms,
            "canonical_concepts": self._dedupe(canonical, "concept_id"),
            "private_concepts": self._dedupe(private, "private_concept_id"),
            "confirmation_required": pending,
            "coverage": goal_coverage,
            "coverage_warnings": warnings,
            "kg_source": kg_source,
            "reason": self._reason(source_mode, normalized_selections, canonical, private),
            "created_at": now,
            "updated_at": now,
        }
        return self.store.save(interpretation, evidence)

    def confirm(
        self,
        *,
        user_id: str,
        interpretation_id: str,
        confirmed_mappings: dict[str, str] | None = None,
        accepted_private_concepts: list[str] | None = None,
        rejected_private_concepts: list[str] | None = None,
        rejected_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        interpretation = self.store.get(user_id, interpretation_id)
        if not interpretation:
            raise GoalInterpretationNotFoundError(interpretation_id)
        evidence = self.store.evidence(user_id, interpretation_id)
        mappings = confirmed_mappings or {}
        accepted_private = set(accepted_private_concepts or [])
        rejected_private = set(rejected_private_concepts or [])
        rejected = set(rejected_terms or [])
        repository, _, _ = self._repository()
        try:
            for item in evidence:
                term = item["requested_term"]
                if term in rejected:
                    item["mapping_status"] = "rejected"
                    continue
                if term in mappings:
                    topic = repository.get_topic(mappings[term])
                    if not topic:
                        raise GoalInterpretationValidationError(
                            f"Confirmed canonical concept does not exist: {mappings[term]}"
                        )
                    item["canonical_concept_id"] = topic["id"]
                    item["private_concept_id"] = None
                    item["mapping_confidence"] = 1.0
                    item["mapping_reason"] = "user_confirmed"
                    item["mapping_status"] = "accepted"
                elif item.get("private_concept_id") in accepted_private:
                    item["mapping_status"] = "accepted_private"
                    item["mapping_reason"] = "user_confirmed_private"
                elif item.get("private_concept_id") in rejected_private:
                    item["mapping_status"] = "rejected"
                    item["mapping_reason"] = "user_rejected_private"
        finally:
            close = getattr(repository, "close", None)
            if callable(close):
                close()

        unresolved = [
            item
            for item in evidence
            if item["mapping_status"] in {"confirmation_required", "private_candidate"}
        ]
        if unresolved:
            raise GoalInterpretationValidationError(
                "All pending mappings and private concepts must be accepted, mapped, or rejected"
            )
        canonical = [
            {
                "requested_term": item["requested_term"],
                "concept_id": item["canonical_concept_id"],
                "confidence": item["mapping_confidence"],
                "reason": item["mapping_reason"],
                "chunk_ids": item["chunk_ids"],
            }
            for item in evidence
            if item["mapping_status"] == "accepted" and item.get("canonical_concept_id")
        ]
        private = [
            {
                "requested_term": item["requested_term"],
                "display_name": item["requested_term"],
                "private_concept_id": item["private_concept_id"],
                "confidence": item["mapping_confidence"],
                "reason": item["mapping_reason"],
                "chunk_ids": item["chunk_ids"],
            }
            for item in evidence
            if item["mapping_status"] == "accepted_private"
        ]
        if interpretation["source_mode"] == "private_only" and not canonical and not private:

            raise GoalInterpretationValidationError(

                "Keep at least one concept from your materials, or return and choose a source strategy that includes the public knowledge graph"

            )
        interpretation["canonical_concepts"] = self._dedupe(canonical, "concept_id")
        interpretation["private_concepts"] = self._dedupe(private, "private_concept_id")
        interpretation["confirmation_required"] = []
        interpretation["status"] = "confirmed"
        interpretation["user_decision"] = {
            "confirmed_mappings": mappings,
            "accepted_private_concepts": sorted(accepted_private),
            "rejected_private_concepts": sorted(rejected_private),
            "rejected_terms": sorted(rejected),
            "confirmed_at": _now_iso(),
        }
        return self.store.save(interpretation, evidence)

    def update_document_scope(
        self,
        *,
        user_id: str,
        document_id: str,
        scope: dict[str, Any],
    ) -> dict[str, Any]:
        document = self.documents.get_document(user_id, document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        normalized = self._normalize_selection({"document_id": document_id, **scope}, document)
        return self.documents.update_document(
            user_id,
            document_id,
            default_learning_scope=normalized,
        )

    @staticmethod
    def _normalize_selection(
        selection: dict[str, Any],
        document: dict[str, Any],
    ) -> dict[str, Any]:
        role = str(selection.get("role") or "supplementary")
        if role not in DOCUMENT_ROLES:
            raise GoalInterpretationValidationError(f"Unsupported document role: {role}")
        page_count = int(document.get("page_count") or 0)
        included_pages = sorted(
            {
                int(page)
                for page in selection.get("included_pages") or []
                if int(page) >= 1 and (page_count == 0 or int(page) <= page_count)
            }
        )
        excluded_pages = sorted(
            {
                int(page)
                for page in selection.get("excluded_pages") or []
                if int(page) >= 1 and (page_count == 0 or int(page) <= page_count)
            }
        )
        if set(included_pages) & set(excluded_pages):
            raise GoalInterpretationValidationError(
                "A page cannot be both included and excluded"
            )
        included_sections = sorted({
            str(section).strip()
            for section in selection.get("included_sections") or []
            if str(section).strip()
        })
        excluded_sections = sorted({
            str(section).strip()
            for section in selection.get("excluded_sections") or []
            if str(section).strip()
        })
        if {_normalize(item) for item in included_sections} & {
            _normalize(item) for item in excluded_sections
        }:
            raise GoalInterpretationValidationError(
                "A section cannot be both included and excluded"
            )
        return {
            "document_id": document["document_id"],
            "display_name": document["display_name"],
            "role": role,
            "required": (
                role in {"core", "exam_scope"}
                if selection.get("required") is None
                else bool(selection.get("required"))
            ),
            "included_pages": included_pages,
            "excluded_pages": excluded_pages,
            "included_sections": included_sections,
            "excluded_sections": excluded_sections,
        }

    def _scoped_chunks(
        self,
        user_id: str,
        document_id: str,
        selection: dict[str, Any],
    ) -> list[dict[str, Any]]:
        chunks = self.documents.get_chunks(user_id, document_id)
        included = set(selection["included_pages"])
        excluded = set(selection["excluded_pages"])
        included_sections = [_normalize(item) for item in selection["included_sections"]]
        excluded_sections = [_normalize(item) for item in selection["excluded_sections"]]
        selected = []
        for chunk in chunks:
            page = int(chunk.get("page_start") or 0)
            if included and page not in included:
                continue
            if page in excluded:
                continue
            try:
                metadata = json.loads(chunk.get("metadata_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            section = str(metadata.get("section_path") or "").strip()
            if not section:
                section = str(chunk.get("text") or "").splitlines()[0][:120]
            normalized_section = _normalize(section)
            if included_sections and not any(
                item in normalized_section or normalized_section in item
                for item in included_sections
            ):
                continue
            if excluded_sections and any(
                item in normalized_section or normalized_section in item
                for item in excluded_sections
            ):
                continue
            selected.append(chunk)
        return selected

    @staticmethod
    def _goal_terms(goal_text: str) -> list[str]:
        verified_terms = verified_goal_concepts_for_goal(goal_text)
        if verified_terms:
            return verified_terms
        catalog = resolve_goal_chain(goal_text)
        if catalog:
            return list(catalog[1]["canonical_path"])
        parser = GoalParser()
        explicit = parser._extract_known_concept(goal_text)
        if explicit:
            return [explicit]
        return parser._clean_target_concepts([], goal_text)[:1]

    def _candidate_terms(self, chunks: list[dict[str, Any]], repository) -> list[dict[str, Any]]:
        if not chunks:
            return []
        names = repository.node_names()
        aliases = TopicMapper.DEFAULT_ALIASES
        found: dict[tuple[str, str | None], dict[str, Any]] = {}
        for chunk in chunks:
            text = str(chunk.get("text") or "")
            normalized_text = _normalize(text)
            document_id = chunk.get("document_id")
            chunk_id = chunk["chunk_id"]
            for name in names:
                normalized_name = _normalize(name)
                if len(normalized_name) >= 3 and re.search(
                    rf"(?<!\w){re.escape(normalized_name)}(?!\w)",
                    normalized_text,
                ):
                    key = (normalized_name, document_id)
                    item = found.setdefault(
                        key,
                        {
                            "term": name,
                            "document_id": document_id,
                            "chunk_ids": [],
                            "origin": "document",
                        },
                    )
                    item["chunk_ids"].append(chunk_id)
            for alias, canonical in aliases.items():
                if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized_text):
                    key = (_normalize(canonical), document_id)
                    item = found.setdefault(
                        key,
                        {
                            "term": canonical,
                            "document_id": document_id,
                            "chunk_ids": [],
                            "origin": "document_alias",
                        },
                    )
                    item["chunk_ids"].append(chunk_id)

        private_phrases = self._private_phrases(chunks)
        for phrase, document_id, chunk_ids in private_phrases:
            key = (_normalize(phrase), document_id)
            found.setdefault(
                key,
                {
                    "term": phrase,
                    "document_id": document_id,
                    "chunk_ids": chunk_ids,
                    "origin": "document_candidate",
                },
            )
        return list(found.values())[:40]

    @staticmethod
    def _private_phrases(
        chunks: list[dict[str, Any]],
    ) -> list[tuple[str, str | None, list[str]]]:
        generic = {
            "this",
            "that",
            "these",
            "those",
            "introduction",
            "overview",
            "example",
            "course",
            "chapter",
            "learning",
        }
        occurrences: dict[tuple[str, str | None], set[str]] = {}
        labels: dict[tuple[str, str | None], str] = {}
        for chunk in chunks:
            text = str(chunk.get("text") or "")
            phrases = re.findall(
                r"\b(?:[A-Z][A-Za-z0-9+#-]{2,})(?:\s+(?:[A-Z][A-Za-z0-9+#-]{2,})){0,3}\b",
                text,
            )
            phrases.extend(re.findall(r"[\u3400-\u9fff]{3,10}", text))
            for phrase in phrases:
                normalized = _normalize(phrase)
                is_cjk = bool(re.search(r"[\u3400-\u9fff]", phrase))
                if not is_cjk and " " not in phrase and not phrase.isupper():
                    continue
                if not normalized or normalized in generic or len(normalized) < 3:
                    continue
                key = (normalized, chunk.get("document_id"))
                labels[key] = phrase.strip()
                occurrences.setdefault(key, set()).add(chunk["chunk_id"])
        ranked = sorted(
            occurrences,
            key=lambda key: (-len(occurrences[key]), key[0]),
        )
        return [
            (labels[key], key[1], sorted(occurrences[key]))
            for key in ranked[:12]
        ]

    @staticmethod
    def _map_term(
        *,
        user_id: str,
        repository,
        requested_term: str,
        document_id: str | None,
        chunk_ids: list[str],
        origin: str,
    ) -> dict[str, Any]:
        direct = repository.get_topic(requested_term.strip())
        if direct:
            return GoalInterpretationService._evidence(
                requested_term,
                document_id,
                chunk_ids,
                direct["id"],
                None,
                1.0,
                f"exact_match:{origin}",
                "accepted",
            )
        normalized = _normalize(requested_term)
        alias = TopicMapper.DEFAULT_ALIASES.get(normalized)
        if alias:
            topic = repository.get_topic(alias)
            if topic:
                return GoalInterpretationService._evidence(
                    requested_term,
                    document_id,
                    chunk_ids,
                    topic["id"],
                    None,
                    1.0,
                    f"alias_exact:{origin}",
                    "accepted",
                )
        candidates = repository.search_topics(requested_term, limit=3)
        if candidates and candidates[0].score >= 0.78:
            return GoalInterpretationService._evidence(
                requested_term,
                document_id,
                chunk_ids,
                candidates[0].name,
                None,
                candidates[0].score,
                f"{candidates[0].reason}:{origin}",
                "accepted",
            )
        if candidates and candidates[0].score >= 0.60:
            return GoalInterpretationService._evidence(
                requested_term,
                document_id,
                chunk_ids,
                candidates[0].name,
                None,
                candidates[0].score,
                f"{candidates[0].reason}:{origin}",
                "confirmation_required",
            )
        verified_name = verified_canonical_concept_name(requested_term)
        if verified_name and not str(origin).startswith("document"):
            return GoalInterpretationService._evidence(
                requested_term,
                document_id,
                chunk_ids,
                verified_name,
                None,
                0.95,
                f"verified_public_goal_scope:{origin}",
                "accepted",
            )
        private_id = _private_concept_id(user_id, requested_term)
        score = candidates[0].score if candidates else 0.0
        reason = (
            f"below_canonical_threshold:{origin}"
            if candidates
            else f"no_canonical_candidate:{origin}"
        )
        return GoalInterpretationService._evidence(
            requested_term,
            document_id,
            chunk_ids,
            None,
            private_id,
            score,
            reason,
            "private_candidate",
        )

    @staticmethod
    def _evidence(
        requested_term: str,
        document_id: str | None,
        chunk_ids: list[str],
        canonical_concept_id: str | None,
        private_concept_id: str | None,
        confidence: float,
        reason: str,
        status: str,
    ) -> dict[str, Any]:
        return {
            "evidence_id": str(uuid.uuid4()),
            "requested_term": requested_term,
            "document_id": document_id,
            "chunk_ids": sorted(set(chunk_ids)),
            "canonical_concept_id": canonical_concept_id,
            "private_concept_id": private_concept_id,
            "mapping_confidence": round(float(confidence), 4),
            "mapping_reason": reason,
            "mapping_status": status,
        }

    @staticmethod
    def _repository():
        errors = []
        if os.getenv("NEO4J_PASSWORD"):
            repository = None
            try:
                repository = create_kg_repository(backend="neo4j")
                repository.node_names()
                return repository, "neo4j", None
            except Exception as exc:
                errors.append(f"neo4j:{type(exc).__name__}")
                close = getattr(repository, "close", None)
                if callable(close):
                    close()
        graph_path = CALIBRATED_KG if CALIBRATED_KG.exists() else GLOBAL_KG
        repository = create_kg_repository(graph_path=graph_path, backend="json")
        warning = (
            "Neo4j unavailable; canonical mapping used calibrated JSON KG"
            if errors
            else None
        )
        return repository, "json", warning

    @staticmethod
    def _goal_coverage(
        target_terms: list[str],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        document_terms = {
            _normalize(item["requested_term"])
            for item in evidence
            if item.get("document_id") and item.get("chunk_ids")
        }
        covered = [term for term in target_terms if _normalize(term) in document_terms]
        return {
            "goal_terms": target_terms,
            "document_covered_goal_terms": covered,
            "all_goal_terms_in_documents": len(covered) == len(target_terms),
        }

    @staticmethod
    def _dedupe(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        unique = {}
        for item in items:
            unique.setdefault(item[key], item)
        return list(unique.values())

    @staticmethod
    def _reason(
        source_mode: str,
        documents: list[dict[str, Any]],
        canonical: list[dict[str, Any]],
        private: list[dict[str, Any]],
    ) -> str:
        return (
            f"Interpreted with source_mode={source_mode}; "
            f"{len(documents)} scoped private document(s), "
            f"{len(canonical)} canonical mapping(s), "
            f"and {len(private)} private concept candidate(s)."
        )



