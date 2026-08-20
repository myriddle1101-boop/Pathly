"""KQ5 review, publish, and rollback for approved V4 teaching knowledge.

This is intentionally a knowledge-base release service, not a runtime-question
review queue. Runtime questions are still checked by the KQ4 quality gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from golden_evidence_chain import build_evidence_manifest
from golden_teaching_semantics import KQ1_SEMANTICS_VERSION, teaching_profile, validate_profiles
from verified_golden_sources import GOLDEN_PATH


KQ5_RELEASE_VERSION = "kq5-knowledge-release-v1"
DEFAULT_RELEASE_DIR = Path(__file__).resolve().parent / "artifacts" / "kq5_knowledge_releases"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


class KnowledgeReleaseService:
    def __init__(self, *, kg_dir: str | Path, release_dir: str | Path = DEFAULT_RELEASE_DIR):
        self.kg_dir = Path(kg_dir)
        self.release_dir = Path(release_dir)
        self.candidates_dir = self.release_dir / "candidates"
        self.releases_dir = self.release_dir / "releases"
        self.current_path = self.release_dir / "current.json"

    def build_candidate(self) -> dict[str, Any]:
        errors = validate_profiles()
        evidence = build_evidence_manifest(self.kg_dir)
        evidence_by_name = {item["concept_name"]: item for item in evidence["records"]}
        records = []
        for concept_name in GOLDEN_PATH:
            profile = teaching_profile(concept_name)
            record = evidence_by_name[concept_name]
            records.append({
                "concept_name": concept_name,
                "canonical_id": profile["canonical_id"],
                "claims": profile["claims"],
                "misconceptions": profile["misconceptions"],
                "assessment_targets": profile["assessment_targets"],
                "evidence": {"resource_id": record["resource_id"], "document_id": record["document_id"], "pages": record["pages"]},
            })
        payload = {"release_schema_version": KQ5_RELEASE_VERSION, "semantics_version": KQ1_SEMANTICS_VERSION, "created_at": _now(), "status": "draft", "validation_errors": errors, "records": records}
        digest = hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        payload["candidate_id"] = f"kq5-{digest}"
        _write_atomic(self.candidates_dir / f"{payload['candidate_id']}.json", payload)
        return payload

    @staticmethod
    def review(candidate: dict[str, Any]) -> dict[str, Any]:
        checks = []
        for record in candidate.get("records") or []:
            claims = record.get("claims") or []
            page_numbers = {page.get("page_number") for page in (record.get("evidence") or {}).get("pages") or []}
            checks.append({
                "concept_name": record.get("concept_name"),
                "claims_complete": len(claims) >= 5,
                "misconceptions_complete": len(record.get("misconceptions") or []) >= 2,
                "targets_complete": len(record.get("assessment_targets") or []) == 3,
                "evidence_complete": bool(page_numbers) and all(set(claim.get("source_pages") or []).issubset(page_numbers) for claim in claims),
            })
        passed = not candidate.get("validation_errors") and len(checks) == 5 and all(all(value for key, value in item.items() if key != "concept_name") for item in checks)
        return {"candidate_id": candidate.get("candidate_id"), "passed": passed, "checks": checks}

    def publish(self, candidate: dict[str, Any]) -> dict[str, Any]:
        review = self.review(candidate)
        if not review["passed"]:
            raise ValueError("knowledge candidate has not passed review")
        manifest = {**candidate, "status": "published", "published_at": _now(), "review": review}
        release_path = self.releases_dir / f"{candidate['candidate_id']}.json"
        _write_atomic(release_path, manifest)
        _write_atomic(self.current_path, {"release_schema_version": KQ5_RELEASE_VERSION, "candidate_id": candidate["candidate_id"], "status": "published", "manifest_path": str(release_path), "published_at": manifest["published_at"]})
        return manifest

    def current(self) -> dict[str, Any] | None:
        if not self.current_path.exists():
            return None
        pointer = json.loads(self.current_path.read_text(encoding="utf-8"))
        manifest_path = Path(pointer.get("manifest_path") or "")
        return json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None

    def rollback(self, candidate_id: str) -> dict[str, Any]:
        target = self.releases_dir / f"{candidate_id}.json"
        if not target.exists():
            raise FileNotFoundError(candidate_id)
        manifest = json.loads(target.read_text(encoding="utf-8"))
        if manifest.get("status") != "published":
            raise ValueError("only a published manifest may be restored")
        _write_atomic(self.current_path, {"release_schema_version": KQ5_RELEASE_VERSION, "candidate_id": candidate_id, "status": "published", "manifest_path": str(target), "published_at": _now(), "rollback": True})
        return self.current() or manifest

    def status(self) -> dict[str, Any]:
        current = self.current()
        candidate_files = sorted(self.candidates_dir.glob("*.json")) if self.candidates_dir.exists() else []
        release_files = sorted(self.releases_dir.glob("*.json")) if self.releases_dir.exists() else []
        return {
            "release_version": KQ5_RELEASE_VERSION,
            "current_candidate_id": (current or {}).get("candidate_id"),
            "current_status": (current or {}).get("status"),
            "candidate_count": len(candidate_files),
            "published_count": len(release_files),
        }


def active_release_allows(concept_name: str, *, release_dir: str | Path = DEFAULT_RELEASE_DIR) -> bool:
    """Fail closed only once KQ5 has an active release pointer."""
    service = KnowledgeReleaseService(kg_dir=Path(__file__).resolve().parent.parent / "KG_construction", release_dir=release_dir)
    current = service.current()
    if current is None:
        return True
    return current.get("status") == "published" and any(item.get("concept_name") == concept_name for item in current.get("records") or [])
