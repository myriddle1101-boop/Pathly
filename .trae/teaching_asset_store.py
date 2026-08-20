"""Versioned, evidence-linked Teaching Asset Store for V4.

Neo4j remains the relationship/index layer and Chroma remains the RAG text
layer. This store owns approved, learner-tiered teaching material that the
Content Agent may select and arrange.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ASSET_SCHEMA_VERSION = "teaching-assets-v1"
ASSET_TYPES = {
    "foundation_intuition", "foundation_worked_example", "advanced_derivation",
    "advanced_worked_example", "visual_or_coordinate_description",
    "formula_explanation", "code_exercise", "contextual_example_variant",
    "transfer_challenge", "boundary_challenge",
}
TIERS = {"shared", "foundation", "advanced"}
STATUSES = {"draft", "in_review", "approved", "published", "superseded"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class TeachingAssetValidationError(ValueError):
    pass


class TeachingAssetStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("PATHLY_TEACHING_ASSET_DB", str(Path(__file__).with_name("pathly_teaching_assets.db"))))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS teaching_assets (
                    asset_id TEXT PRIMARY KEY,
                    canonical_concept_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    learner_tier TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    assessment_targets_json TEXT NOT NULL DEFAULT '[]',
                    misconception_ids_json TEXT NOT NULL DEFAULT '[]',
                    knowledge_version TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS teaching_asset_evidence (
                    asset_id TEXT NOT NULL REFERENCES teaching_assets(asset_id) ON DELETE CASCADE,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_id TEXT,
                    PRIMARY KEY(asset_id, document_id, page_number, chunk_id)
                );
                CREATE TABLE IF NOT EXISTS teaching_asset_manifests (
                    manifest_version TEXT PRIMARY KEY,
                    asset_ids_json TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT
                );
                CREATE TABLE IF NOT EXISTS teaching_asset_scope_manifests (
                    scope_id TEXT NOT NULL,
                    manifest_version TEXT NOT NULL,
                    asset_ids_json TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    PRIMARY KEY(scope_id, manifest_version)
                );
                CREATE INDEX IF NOT EXISTS idx_teaching_assets_lookup
                    ON teaching_assets(canonical_concept_id, learner_tier, asset_type, review_status);
                """
            )

    @staticmethod
    def validate_asset(asset: dict[str, Any]) -> None:
        required = {"asset_id", "canonical_concept_id", "asset_type", "learner_tier", "content", "knowledge_version", "review_status", "evidence_refs"}
        missing = sorted(required - set(asset))
        if missing:
            raise TeachingAssetValidationError(f"missing asset fields: {', '.join(missing)}")
        if asset["asset_type"] not in ASSET_TYPES:
            raise TeachingAssetValidationError(f"unsupported asset_type: {asset['asset_type']}")
        if asset["learner_tier"] not in TIERS:
            raise TeachingAssetValidationError(f"unsupported learner_tier: {asset['learner_tier']}")
        if asset["review_status"] not in STATUSES:
            raise TeachingAssetValidationError(f"unsupported review_status: {asset['review_status']}")
        if not isinstance(asset["content"], dict) or not asset["content"]:
            raise TeachingAssetValidationError("content must be a non-empty object")
        evidence = asset.get("evidence_refs") or []
        if asset["review_status"] in {"approved", "published"} and not evidence:
            raise TeachingAssetValidationError("approved/published assets require evidence_refs")
        for ref in evidence:
            if not ref.get("document_id") or not int(ref.get("page_number") or 0) > 0:
                raise TeachingAssetValidationError("each evidence ref requires document_id and positive page_number")

    def upsert(self, asset: dict[str, Any]) -> dict[str, Any]:
        self.validate_asset(asset)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO teaching_assets
                (asset_id, canonical_concept_id, asset_type, learner_tier, content_json,
                 assessment_targets_json, misconception_ids_json, knowledge_version,
                 review_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                  canonical_concept_id=excluded.canonical_concept_id,
                  asset_type=excluded.asset_type,
                  learner_tier=excluded.learner_tier,
                  content_json=excluded.content_json,
                  assessment_targets_json=excluded.assessment_targets_json,
                  misconception_ids_json=excluded.misconception_ids_json,
                  knowledge_version=excluded.knowledge_version,
                  review_status=excluded.review_status,
                  updated_at=excluded.updated_at""",
                (asset["asset_id"], asset["canonical_concept_id"], asset["asset_type"], asset["learner_tier"],
                 _json(asset["content"]), _json(asset.get("assessment_targets") or []), _json(asset.get("misconception_ids") or []),
                 asset["knowledge_version"], asset["review_status"], now, now),
            )
            conn.execute("DELETE FROM teaching_asset_evidence WHERE asset_id = ?", (asset["asset_id"],))
            conn.executemany(
                "INSERT INTO teaching_asset_evidence(asset_id, document_id, page_number, chunk_id) VALUES (?, ?, ?, ?)",
                [(asset["asset_id"], ref["document_id"], int(ref["page_number"]), ref.get("chunk_id")) for ref in asset.get("evidence_refs") or []],
            )
        return self.get(asset["asset_id"]) or {}

    def get(self, asset_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM teaching_assets WHERE asset_id = ?", (asset_id,)).fetchone()
            if not row:
                return None
            evidence = conn.execute("SELECT document_id, page_number, chunk_id FROM teaching_asset_evidence WHERE asset_id = ? ORDER BY document_id, page_number", (asset_id,)).fetchall()
        return {"asset_id": row["asset_id"], "canonical_concept_id": row["canonical_concept_id"], "asset_type": row["asset_type"], "learner_tier": row["learner_tier"], "content": json.loads(row["content_json"]), "assessment_targets": json.loads(row["assessment_targets_json"]), "misconception_ids": json.loads(row["misconception_ids_json"]), "knowledge_version": row["knowledge_version"], "review_status": row["review_status"], "evidence_refs": [dict(item) for item in evidence], "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def list_assets(self, *, concept_id: str, learner_tier: str, asset_types: Iterable[str] | None = None, published_only: bool = True) -> list[dict[str, Any]]:
        types = list(asset_types or [])
        clauses = ["canonical_concept_id = ?", "learner_tier IN (?, 'shared')"]
        params: list[Any] = [concept_id, learner_tier]
        if types:
            clauses.append("asset_type IN (" + ",".join("?" for _ in types) + ")")
            params.extend(types)
        if published_only:
            clauses.append("review_status = 'published'")
        with self._connect() as conn:
            ids = [row[0] for row in conn.execute("SELECT asset_id FROM teaching_assets WHERE " + " AND ".join(clauses) + " ORDER BY asset_type, asset_id", params).fetchall()]
        return [self.get(asset_id) for asset_id in ids if self.get(asset_id)]

    def publish_bundle(self, *, manifest_version: str, asset_ids: list[str]) -> dict[str, Any]:
        if not asset_ids:
            raise TeachingAssetValidationError("cannot publish an empty asset bundle")
        assets = [self.get(asset_id) for asset_id in asset_ids]
        if any(asset is None for asset in assets):
            raise TeachingAssetValidationError("manifest references an unknown asset")
        if any(asset["review_status"] != "approved" for asset in assets if asset):
            raise TeachingAssetValidationError("only approved assets may be published")
        digest = hashlib.sha256(_json(sorted(asset_ids)).encode("utf-8")).hexdigest()[:16]
        now = _now()
        with self._connect() as conn:
            conn.execute("UPDATE teaching_asset_manifests SET status='superseded' WHERE status='published'")
            conn.execute("UPDATE teaching_assets SET review_status='superseded', updated_at=? WHERE review_status='published'", (now,))
            conn.executemany("UPDATE teaching_assets SET review_status='published', updated_at=? WHERE asset_id=?", [(now, asset_id) for asset_id in asset_ids])
            conn.execute("INSERT OR REPLACE INTO teaching_asset_manifests(manifest_version, asset_ids_json, digest, status, created_at, published_at) VALUES (?, ?, ?, 'published', ?, ?)", (manifest_version, _json(sorted(asset_ids)), digest, now, now))
        return {"manifest_version": manifest_version, "asset_count": len(asset_ids), "digest": digest, "status": "published"}

    def current_manifest(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM teaching_asset_manifests WHERE status='published' ORDER BY published_at DESC LIMIT 1").fetchone()
        if not row:
            return None
        return {"manifest_version": row["manifest_version"], "asset_ids": json.loads(row["asset_ids_json"]), "digest": row["digest"], "status": row["status"], "published_at": row["published_at"]}

    def publish_scoped_bundle(self, *, scope_id: str, manifest_version: str, asset_ids: list[str]) -> dict[str, Any]:
        """Publish an additive goal-scoped bundle without replacing another goal's manifest."""
        if not scope_id or not asset_ids:
            raise TeachingAssetValidationError("scope_id and non-empty asset_ids are required")
        assets = [self.get(asset_id) for asset_id in asset_ids]
        if any(asset is None for asset in assets):
            raise TeachingAssetValidationError("scoped manifest references an unknown asset")
        if any(asset["review_status"] not in {"approved", "published"} for asset in assets if asset):
            raise TeachingAssetValidationError("scoped manifest requires approved assets")
        digest = hashlib.sha256(_json(sorted(asset_ids)).encode("utf-8")).hexdigest()[:16]
        now = _now()
        with self._connect() as conn:
            conn.execute("UPDATE teaching_asset_scope_manifests SET status='superseded' WHERE scope_id=? AND status='published'", (scope_id,))
            conn.executemany("UPDATE teaching_assets SET review_status='published', updated_at=? WHERE asset_id=?", [(now, asset_id) for asset_id in asset_ids])
            conn.execute("INSERT OR REPLACE INTO teaching_asset_scope_manifests(scope_id, manifest_version, asset_ids_json, digest, status, created_at, published_at) VALUES (?, ?, ?, ?, 'published', ?, ?)", (scope_id, manifest_version, _json(sorted(asset_ids)), digest, now, now))
        return {"scope_id": scope_id, "manifest_version": manifest_version, "asset_count": len(asset_ids), "digest": digest, "status": "published"}

    def current_scoped_manifest(self, scope_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM teaching_asset_scope_manifests WHERE scope_id=? AND status='published' ORDER BY published_at DESC LIMIT 1", (scope_id,)).fetchone()
        if not row:
            return None
        return {"scope_id": row["scope_id"], "manifest_version": row["manifest_version"], "asset_ids": json.loads(row["asset_ids_json"]), "digest": row["digest"], "status": row["status"], "published_at": row["published_at"]}
