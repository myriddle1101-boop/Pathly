"""Rebuildable, read-only source-link index for Source-Grounded Lecture v4.

This module projects existing KG/resource/RAG metadata into a SQLite sidecar.
It never mutates Neo4j, Chroma, source documents, plans, or v1-v3 content.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SOURCE_LINK_VERSION = "source-link-s3-v1"
RELEVANCE_THRESHOLD = 0.75
COVERAGE_THRESHOLD = 0.60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "concept"


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in _normal(value).split() if len(token) > 2}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _page_sequence(section: dict[str, Any]) -> list[dict[str, Any]]:
    raw = section.get("page_sequence") or []
    if not raw and section.get("page_start"):
        start = int(section["page_start"])
        end = int(section.get("page_end") or start)
        raw = [
            {"page_number": page, "role": "anchor" if page == start else "context_after"}
            for page in range(start, end + 1)
        ]
    pages: list[dict[str, Any]] = []
    by_page: dict[int, dict[str, Any]] = {}
    for item in raw:
        page = int(item.get("page_number") or item.get("page_start") or 0)
        if page <= 0:
            continue
        record = by_page.setdefault(
            page,
            {
                "page_number": page,
                "role": item.get("role") or ("introduction" if not by_page else "continuation"),
                "chunk_ids": [],
            },
        )
        for chunk_id in item.get("chunk_ids") or []:
            if chunk_id and chunk_id not in record["chunk_ids"]:
                record["chunk_ids"].append(str(chunk_id))
    pages = sorted(by_page.values(), key=lambda item: item["page_number"])
    if not pages:
        return []

    # A source sequence must be continuous. If retrieval returns disconnected
    # pages, retain only the strongest contiguous run rather than implying a
    # relationship between unrelated parts of a document.
    runs: list[list[dict[str, Any]]] = []
    for page in pages:
        if not runs or page["page_number"] != runs[-1][-1]["page_number"] + 1:
            runs.append([page])
        else:
            runs[-1].append(page)
    return max(runs, key=lambda run: (len(run), sum(len(p["chunk_ids"]) for p in run), -run[0]["page_number"]))


def _evidence_pages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for evidence in items:
        start = int(evidence.get("page_start") or 0)
        end = int(evidence.get("page_end") or start or 0)
        if start <= 0:
            continue
        chunk_id = str(evidence.get("chunk_id") or evidence.get("evidence_id") or "")
        for page in range(start, min(end, start + 12) + 1):
            raw.append({"page_number": page, "chunk_ids": [chunk_id] if chunk_id else []})
    sequence = _page_sequence({"page_sequence": raw})
    for index, page in enumerate(sequence):
        if index == 0:
            page["role"] = "introduction"
        elif index == len(sequence) - 1 and len(sequence) > 1:
            page["role"] = "worked_example"
        else:
            page["role"] = "mechanism"
    return sequence


def _resource_maps(daily: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_resource: dict[str, dict[str, Any]] = {}
    by_document: dict[str, dict[str, Any]] = {}
    for item in [*(daily.get("required_resources") or []), *(daily.get("optional_resources") or []), *(daily.get("resources") or [])]:
        if item.get("resource_id"):
            by_resource[str(item["resource_id"])] = item
        if item.get("document_id"):
            by_document[str(item["document_id"])] = item
    return by_resource, by_document


def _candidate_groups(
    daily: dict[str, Any], concept_id: str, concept_name: str
) -> list[dict[str, Any]]:
    by_resource, by_document = _resource_maps(daily)
    concept_norm = _normal(concept_id)
    name_tokens = _tokens(concept_name)
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for evidence in [*(daily.get("prepared_evidence") or []), *(daily.get("citations") or [])]:
        evidence_concept = _normal(evidence.get("concept_id"))
        text = " ".join(
            str(evidence.get(key) or "")
            for key in ("clean_text", "excerpt", "title", "section_title")
        )
        overlap = len(name_tokens & _tokens(text)) / max(1, len(name_tokens))
        direct = bool(concept_norm and evidence_concept == concept_norm)
        if not direct and overlap < 0.5:
            continue
        document_id = str(evidence.get("document_id") or "")
        resource_id = str(evidence.get("resource_id") or "")
        source_type = str(evidence.get("source_type") or "")
        scope = "private" if source_type == "private_document" else "public"
        key = (document_id, resource_id, scope)
        group = groups.setdefault(key, {"items": [], "document_id": document_id or None, "resource_id": resource_id or None, "source_scope": scope})
        group["items"].append(evidence)
        group["direct"] = group.get("direct", False) or direct
        group["overlap"] = max(group.get("overlap", 0.0), overlap)
    output: list[dict[str, Any]] = []
    for group in groups.values():
        items = group["items"]
        resource = by_resource.get(str(group.get("resource_id") or "")) or by_document.get(str(group.get("document_id") or "")) or {}
        pages = _evidence_pages(items)
        chunk_ids = list(dict.fromkeys(str(item.get("chunk_id") or item.get("evidence_id")) for item in items if item.get("chunk_id") or item.get("evidence_id")))
        explicit_scores = [_number(item.get("relevance_score"), -1.0) for item in items]
        explicit_scores = [score for score in explicit_scores if score >= 0]
        relevance = max(explicit_scores, default=0.0)
        if group.get("direct"):
            relevance = max(relevance, 0.86)
        relevance = max(relevance, min(0.9, 0.65 + 0.25 * group.get("overlap", 0.0)))
        coverage = min(1.0, 0.38 + 0.14 * min(len(pages), 3) + 0.08 * min(len(chunk_ids), 2)) if pages else 0.0
        title = resource.get("title") or resource.get("document_title")
        if not title:
            metadata = next((item.get("metadata") for item in items if isinstance(item.get("metadata"), dict)), {}) or {}
            title = metadata.get("title") or metadata.get("filename")
        output.append({**group, "page_sequence": pages, "chunk_ids": chunk_ids, "relevance_score": relevance, "coverage_score": coverage, "document_title": title})
    return sorted(output, key=lambda item: (item["relevance_score"], item["coverage_score"], len(item["page_sequence"])), reverse=True)


def _link_record(
    *,
    section: dict[str, Any],
    position: int,
    concept_id: str,
    concept_name: str,
    candidate: dict[str, Any] | None,
    link_role: str = "primary",
) -> dict[str, Any]:
    candidate = dict(candidate or {})
    pages = candidate.get("page_sequence") or []
    resource_id = candidate.get("resource_id") or section.get("resource_id")
    document_id = candidate.get("document_id") or section.get("document_id")
    document_title = candidate.get("document_title") or section.get("document_title") or section.get("source_title")
    chunk_ids = list(dict.fromkeys(candidate.get("chunk_ids") or []))
    relevance = _number(candidate.get("relevance_score"))
    coverage = _number(candidate.get("coverage_score"))
    method = candidate.get("match_method") or "daily_prepared_evidence"
    if not candidate:
        pages = _page_sequence(section)
        source_refs = section.get("source_refs") or section.get("citations") or []
        chunk_ids = list(dict.fromkeys(str(ref.get("chunk_id") or ref.get("evidence_id")) for ref in source_refs if isinstance(ref, dict) and (ref.get("chunk_id") or ref.get("evidence_id"))))
        alignment = section.get("source_alignment") or {}
        relevance = _number(alignment.get("score") or section.get("relevance_score"))
        source_text = " ".join(str(value or "") for value in (section.get("title"), section.get("source_excerpt"), alignment.get("reason")))
        if _tokens(concept_name) & _tokens(source_text):
            relevance = max(relevance, 0.78)
        coverage = min(1.0, 0.38 + 0.14 * min(len(pages), 3) + 0.08 * min(len(chunk_ids), 2)) if pages else 0.0
        method = "existing_source_metadata"
    reliable = bool((document_id or resource_id) and pages and relevance >= RELEVANCE_THRESHOLD and coverage >= COVERAGE_THRESHOLD)
    status = str(candidate.get("review_status") or (section.get("source_alignment") or {}).get("review_status") or "")
    review_status = "verified" if reliable and status == "verified" else ("usable" if reliable else "unlinked")
    if not reliable:
        pages = []
        chunk_ids = []
    scope = candidate.get("source_scope") or section.get("source_scope") or ("private" if section.get("source_type") == "private_document" else "public")
    if review_status in {"usable", "verified"}:
        page_label = (
            f"page {pages[0]['page_number']}"
            if len(pages) == 1
            else f"pages {pages[0]['page_number']}-{pages[-1]['page_number']}"
        )
        reason = candidate.get("match_reason") or (section.get("source_alignment") or {}).get("reason") or f"The indexed evidence explicitly connects {concept_name} to {page_label} in this source."
    else:
        reason = "No PDF page sequence passed the concept relevance and source coverage checks."
    identity = f"{concept_id}|{resource_id or ''}|{document_id or ''}|{json.dumps(pages, sort_keys=True)}"
    return {
        "link_id": f"v4link-{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
        "concept_id": concept_id,
        "concept_name": concept_name,
        "resource_id": resource_id,
        "document_id": document_id,
        "document_title": document_title,
        "page_sequence": pages,
        "chunk_ids": chunk_ids,
        "source_scope": scope,
        "relevance_score": round(relevance, 4),
        "coverage_score": round(coverage, 4),
        "match_method": method,
        "review_status": review_status,
        "match_reason": reason,
        "source_readiness": candidate.get("source_readiness"),
        "link_role": link_role,
        "canonical_concept_id": candidate.get("canonical_concept_id"),
        "golden_path_position": candidate.get("golden_path_position"),
        "golden_path_version": candidate.get("golden_path_version"),
        "source_version": SOURCE_LINK_VERSION,
        "upstream_source_version": candidate.get("source_version"),
        "experience_source_id": candidate.get("experience_source_id"),
        "asset_concept_id": candidate.get("asset_concept_id"),
        "asset_scope": candidate.get("asset_scope"),
        "asset_manifest_version": candidate.get("asset_manifest_version"),
        "catalog_version": candidate.get("catalog_version"),
    }


def links_from_lecture(
    lecture: dict[str, Any], daily_session: dict[str, Any] | None = None,
    provenance_backfill: Any | None = None,
    verified_source_resolver: Any | None = None,
    private_source_resolver: Any | None = None,
    user_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build conservative, explainable links from existing read-only metadata."""
    daily = daily_session or {}
    result: list[dict[str, Any]] = []
    for position, section in enumerate(lecture.get("lecture_sections") or [], 1):
        concept_ids = section.get("concept_ids") or [section.get("concept_id")]
        concept_ids = [str(value) for value in concept_ids if value]
        concept_name = str(section.get("concept_name") or section.get("title") or (concept_ids[0] if concept_ids else f"Concept {position}")).replace(": from source to understanding", "")
        concept_id = concept_ids[0] if concept_ids else _slug(concept_name)
        candidates = _candidate_groups(daily, concept_id, concept_name)
        if private_source_resolver is not None:
            candidates = [candidate for candidate in candidates if candidate.get("source_scope") != "private"]
        best = candidates[0] if candidates else None
        if verified_source_resolver is not None:
            verified = verified_source_resolver.resolve(concept_id=concept_id, concept_name=concept_name)
            if verified:
                best = verified
        has_pages = bool(best and best.get("page_sequence")) or bool(_page_sequence(section))
        if not has_pages and provenance_backfill is not None:
            resource_ids: list[str] = []
            for value in [section.get("resource_id"), *(item.get("resource_id") for item in candidates)]:
                if value and str(value) not in resource_ids:
                    resource_ids.append(str(value))
            recovered = provenance_backfill.resolve(
                concept_id=concept_id,
                concept_name=concept_name,
                resource_ids=resource_ids,
            )
            if recovered:
                best = recovered[0]
        primary = _link_record(section=section, position=position, concept_id=concept_id, concept_name=concept_name, candidate=best)
        private_candidates = []
        if private_source_resolver is not None and user_id:
            private_candidates = private_source_resolver.resolve(
                user_id=user_id, document_ids=document_ids or [],
                concept_id=concept_id, concept_name=concept_name,
            )
        supplemental_links: list[dict[str, Any]] = []
        if primary.get("review_status") == "unlinked" and private_candidates:
            primary = _link_record(section=section, position=position, concept_id=concept_id, concept_name=concept_name, candidate=private_candidates.pop(0), link_role="primary")
        elif private_candidates:
            strongest_private = _link_record(section=section, position=position, concept_id=concept_id, concept_name=concept_name, candidate=private_candidates[0], link_role="primary")
            primary_quality = (float(primary.get("relevance_score") or 0), float(primary.get("coverage_score") or 0))
            private_quality = (float(strongest_private.get("relevance_score") or 0), float(strongest_private.get("coverage_score") or 0))
            if primary.get("review_status") != "verified" and private_quality > primary_quality:
                primary["link_role"] = "supplemental"
                supplemental_links.append(primary)
                primary = strongest_private
                private_candidates.pop(0)
        result.append(primary)
        result.extend(supplemental_links)
        for candidate in private_candidates[:2]:
            if str(candidate.get("document_id") or "") == str(primary.get("document_id") or ""):
                continue
            result.append(_link_record(section=section, position=position, concept_id=concept_id, concept_name=concept_name, candidate=candidate, link_role="supplemental"))
    return result


class ConceptSourceLinkIndex:
    """SQLite sidecar index scoped to one anonymous owner and learning day."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS concept_source_links (
                    link_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    concept_id TEXT NOT NULL,
                    concept_name TEXT NOT NULL,
                    resource_id TEXT,
                    document_id TEXT,
                    document_title TEXT,
                    page_sequence_json TEXT NOT NULL,
                    chunk_ids_json TEXT NOT NULL,
                    source_scope TEXT NOT NULL,
                    relevance_score REAL NOT NULL,
                    coverage_score REAL NOT NULL,
                    match_method TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    match_reason TEXT NOT NULL,
                    source_readiness TEXT,
                    link_role TEXT NOT NULL DEFAULT 'primary',
                    canonical_concept_id TEXT,
                    golden_path_position INTEGER,
                    golden_path_version TEXT,
                    experience_source_id TEXT,
                    asset_concept_id TEXT,
                    asset_scope TEXT,
                    asset_manifest_version TEXT,
                    catalog_version TEXT,
                    upstream_source_version TEXT,
                    source_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_concept_source_links_day
                    ON concept_source_links(user_id, plan_id, day, concept_id);
                CREATE INDEX IF NOT EXISTS idx_concept_source_links_document
                    ON concept_source_links(user_id, document_id);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(concept_source_links)")}
            if "document_title" not in columns:
                connection.execute("ALTER TABLE concept_source_links ADD COLUMN document_title TEXT")
            for name, kind in (
                ("source_readiness", "TEXT"),
                ("link_role", "TEXT NOT NULL DEFAULT 'primary'"),
                ("canonical_concept_id", "TEXT"),
                ("golden_path_position", "INTEGER"),
                ("golden_path_version", "TEXT"),
                ("experience_source_id", "TEXT"),
                ("asset_concept_id", "TEXT"),
                ("asset_scope", "TEXT"),
                ("asset_manifest_version", "TEXT"),
                ("catalog_version", "TEXT"),
                ("upstream_source_version", "TEXT"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE concept_source_links ADD COLUMN {name} {kind}")

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["page_sequence"] = json.loads(item.pop("page_sequence_json") or "[]")
        item["chunk_ids"] = json.loads(item.pop("chunk_ids_json") or "[]")
        return item

    def replace_day(self, user_id: str, plan_id: str, day: int, links: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        stamp = _now()
        rows_by_id: dict[str, dict[str, Any]] = {}
        for raw_item in links:
            item = dict(raw_item)
            scoped = f"{user_id}|{plan_id}|{int(day)}|{item.get('link_id') or item.get('concept_id') or ''}"
            item["link_id"] = f"v4link-{hashlib.sha256(scoped.encode()).hexdigest()[:20]}"
            existing = rows_by_id.get(item["link_id"])
            if existing is None:
                rows_by_id[item["link_id"]] = item
                continue

            # The same concept/source can arrive through the lecture section and
            # evidence backfill. It is one link; keep the stronger record.
            existing_rank = (
                existing.get("review_status") == "verified",
                float(existing.get("relevance_score") or 0),
                float(existing.get("coverage_score") or 0),
                len(existing.get("page_sequence") or []),
            )
            candidate_rank = (
                item.get("review_status") == "verified",
                float(item.get("relevance_score") or 0),
                float(item.get("coverage_score") or 0),
                len(item.get("page_sequence") or []),
            )
            if candidate_rank > existing_rank:
                rows_by_id[item["link_id"]] = item
        rows = list(rows_by_id.values())
        with self._connect() as connection:
            connection.execute("DELETE FROM concept_source_links WHERE user_id=? AND plan_id=? AND day=?", (user_id, plan_id, int(day)))
            for item in rows:
                connection.execute(
                    """INSERT INTO concept_source_links(
                        link_id,user_id,plan_id,day,concept_id,concept_name,resource_id,document_id,
                        document_title,page_sequence_json,chunk_ids_json,source_scope,relevance_score,
                        coverage_score,match_method,review_status,match_reason,source_readiness,link_role,canonical_concept_id,
                        golden_path_position,golden_path_version,experience_source_id,asset_concept_id,asset_scope,
                        asset_manifest_version,catalog_version,upstream_source_version,source_version,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item["link_id"], user_id, plan_id, int(day), item["concept_id"], item["concept_name"],
                        item.get("resource_id"), item.get("document_id"), item.get("document_title"),
                        json.dumps(item.get("page_sequence") or [], ensure_ascii=False),
                        json.dumps(item.get("chunk_ids") or [], ensure_ascii=False),
                        item.get("source_scope") or "public", float(item.get("relevance_score") or 0),
                        float(item.get("coverage_score") or 0), item.get("match_method") or "unknown",
                        item.get("review_status") or "unlinked", item.get("match_reason") or "",
                        item.get("source_readiness"), item.get("link_role") or "primary", item.get("canonical_concept_id"), item.get("golden_path_position"), item.get("golden_path_version"),
                        item.get("experience_source_id"), item.get("asset_concept_id"), item.get("asset_scope"),
                        item.get("asset_manifest_version"), item.get("catalog_version"), item.get("upstream_source_version"),
                        item.get("source_version") or SOURCE_LINK_VERSION, stamp, stamp,
                    ),
                )
        return self.list_day(user_id, plan_id, day)

    def list_day(self, user_id: str, plan_id: str, day: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM concept_source_links WHERE user_id=? AND plan_id=? AND day=? ORDER BY concept_name, link_id""",
                (user_id, plan_id, int(day)),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def delete_day(self, user_id: str, plan_id: str, day: int) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM concept_source_links WHERE user_id=? AND plan_id=? AND day=?", (user_id, plan_id, int(day)))
        return int(cursor.rowcount)

    def delete_document(self, user_id: str, document_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM concept_source_links WHERE user_id=? AND document_id=?", (user_id, document_id))
        return int(cursor.rowcount)

    def delete_all(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM concept_source_links")
        return int(cursor.rowcount)
