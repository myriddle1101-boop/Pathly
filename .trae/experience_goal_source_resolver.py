"""Runtime resolver for approved goal-scoped full-experience sources."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from experience_source_store import ExperienceSourceStore
from goal_chain_catalog import GOAL_CHAINS, GOAL_CHAIN_CATALOG_VERSION
from teaching_asset_store import TeachingAssetStore


class ExperienceGoalSourceResolver:
    def __init__(self, root: str | Path | None = None):
        root = Path(root or Path(__file__).resolve().parent)
        self.sources = ExperienceSourceStore(root / "pathly_experience_sources.db")
        self.assets = TeachingAssetStore(root / "pathly_teaching_assets.db")

    @staticmethod
    def _match(concept_id: str, concept_name: str) -> tuple[str, dict[str, Any], int] | None:
        for goal_id, spec in GOAL_CHAINS.items():
            for index, (cid, name) in enumerate(zip(spec["canonical_path"], spec["display_names"])):
                if concept_id == cid or concept_name.casefold() == name.casefold():
                    return goal_id, spec, index
        return None

    def resolve(self, *, concept_id: str, concept_name: str, learner_tier: str = "shared") -> dict[str, Any] | None:
        match = self._match(str(concept_id), str(concept_name))
        if not match:
            return None
        goal_id, spec, index = match
        source = self.sources.get(spec["source_id"])
        tiered_source_ids = spec.get("tiered_source_ids") or {}
        preferred_id = tiered_source_ids.get(str(learner_tier)) or tiered_source_ids.get("shared")
        if preferred_id:
            source = self.sources.get(preferred_id) or source
        manifest = self.assets.current_scoped_manifest(spec["asset_scope"])
        if not source or source.get("review_status") != "approved" or not manifest:
            return None
        tier_pages = (spec.get("tiered_concept_pages") or {}).get(str(learner_tier))
        page_number = int((tier_pages or spec["concept_pages"])[index])
        page = next((item for item in source.get("pages") or [] if int(item["page_number"]) == page_number), None)
        if not page:
            return None
        return {
            "link_id": f"experience:{goal_id}:{concept_id}",
            "concept_id": concept_id,
            "concept_name": spec["display_names"][index],
            "canonical_concept_id": concept_id,
            "resource_id": source["resource_id"],
            "document_id": source["document_id"],
            "document_title": source["document_title"],
            "source_scope": "public",
            "page_sequence": [{"page_number": page_number, "role": page["content_role"], "chunk_ids": [page["chunk_id"]]}],
            "chunk_ids": [page["chunk_id"]],
            "relevance_score": 1.0,
            "coverage_score": 1.0,
            "match_method": "approved_goal_chain_catalog",
            "match_reason": "The approved canonical concept is bound to its reviewed page-level evidence.",
            "review_status": "verified",
            "source_readiness": "approved_experience_source",
            "source_version": source["source_version"],
            "learner_tier": source.get("learner_tier", "shared"),
            "catalog_version": GOAL_CHAIN_CATALOG_VERSION,
            "asset_concept_id": concept_id,
            "asset_scope": spec["asset_scope"],
            "asset_manifest_version": manifest["manifest_version"],
            "experience_source_id": source["source_id"],
            "link_role": "primary",
        }

    def page_evidence(self, link: dict[str, Any]) -> list[dict[str, Any]]:
        source = self.sources.get(str(link.get("experience_source_id") or ""))
        if not source:
            return []
        wanted = {int(item.get("page_number") or 0) for item in link.get("page_sequence") or []}
        return [
            {"page_number": item["page_number"], "text": item["text"], "chunk_id": item["chunk_id"]}
            for item in source.get("pages") or [] if int(item["page_number"]) in wanted
        ]


class FullExperienceSourceResolver:
    """Preserve legacy golden resolution, then use approved scoped sources."""
    def __init__(self, legacy: Any, scoped: ExperienceGoalSourceResolver):
        self.legacy = legacy
        self.scoped = scoped

    def resolve(self, *, concept_id: str, concept_name: str, learner_tier: str = "shared") -> dict[str, Any] | None:
        return self.legacy.resolve(concept_id=concept_id, concept_name=concept_name) or self.scoped.resolve(concept_id=concept_id, concept_name=concept_name, learner_tier=learner_tier)

    def page_evidence(self, link: dict[str, Any]) -> list[dict[str, Any]]:
        if link.get("experience_source_id"):
            return self.scoped.page_evidence(link)
        return self.legacy.page_evidence(link)
