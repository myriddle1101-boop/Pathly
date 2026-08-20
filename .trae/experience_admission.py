"""Admission contract for a goal before it may enter a full Pathly experience.

Admission is intentionally stricter than planning.  A plan, cached lecture, or
fallback response is never evidence that a goal is eligible for a fresh-user
walkthrough.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import networkx as nx

from fresh_experience_baseline import TARGET_GOALS
from goal_chain_catalog import GOAL_CHAIN_CATALOG_VERSION, resolve_goal_chain
from experience_source_store import ExperienceSourceStore
from teaching_asset_store import TeachingAssetStore
from pathly_backend import CALIBRATED_KG, GLOBAL_KG
from verified_golden_sources import GOLDEN_PATH, GOLDEN_PATH_VERSION, verified_goal_concepts_for_goal


ADMISSION_VERSION = "full-experience-admission-v1"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "artifacts" / "n1_goal_admission_report.json"
VALID_STATUSES = {"eligible_for_full_experience", "planning_only", "blocked"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check(name: str, passed: bool, reason: str, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "reason": reason, "details": details}


def _failure_code(check: str) -> str:
    return {
        "goal_mapping": "unmapped_goal",
        "kg_path": "missing_prerequisite_path",
        "resource_coverage": "missing_source",
        "content_generation": "generation_failure",
        "grounding": "grounding_failure",
    }[check]


class GoalAdmissionValidator:
    """Combine independently auditable checks into the public admission state."""

    def validate(
        self,
        *,
        goal: str,
        mapping: dict[str, Any],
        kg_path: dict[str, Any],
        resource_coverage: dict[str, Any],
        content_generation: dict[str, Any],
        grounding: dict[str, Any],
    ) -> dict[str, Any]:
        checks = {
            "goal_mapping": mapping,
            "kg_path": kg_path,
            "resource_coverage": resource_coverage,
            "content_generation": content_generation,
            "grounding": grounding,
        }
        failed = [name for name, result in checks.items() if not result.get("passed")]
        failure_reasons = [
            {"code": _failure_code(name), "check": name, "reason": checks[name].get("reason")}
            for name in failed
        ]
        if not mapping.get("passed") or not kg_path.get("passed"):
            status = "blocked"
        elif failed:
            status = "planning_only"
        else:
            status = "eligible_for_full_experience"
        return {
            "admission_version": ADMISSION_VERSION,
            "goal": goal,
            "status": status,
            "eligible_for_full_experience": status == "eligible_for_full_experience",
            "target_concept": mapping.get("details", {}).get("target_concept"),
            "checks": checks,
            "failure_reasons": failure_reasons,
            "generated_at": _now(),
        }


def _golden_mapping(goal: str) -> dict[str, Any]:
    path = verified_goal_concepts_for_goal(goal)
    return _check(
        "goal_mapping", bool(path),
        "Goal matches the existing verified neural-foundations chain."
        if path else "No current verified full-experience mapping for this goal.",
        target_concept=path[-1] if path else None,
        canonical_path=path,
        mapping_method="verified_golden_registry" if path else "none",
        source_registry_version=GOLDEN_PATH_VERSION if path else None,
    )


def _controlled_golden_kg_path(mapping: dict[str, Any]) -> dict[str, Any]:
    path = list(mapping.get("details", {}).get("canonical_path") or [])
    expected = list(GOLDEN_PATH)
    return _check(
        "kg_path", path == expected,
        "The existing verified chain has a fixed acyclic prerequisite order."
        if path == expected else "No independently verified acyclic prerequisite path is registered.",
        ordered_concepts=path,
        acyclic=path == expected,
        path_provenance="verified_golden_registry" if path == expected else None,
    )


def _golden_resources(mapping: dict[str, Any]) -> dict[str, Any]:
    path = list(mapping.get("details", {}).get("canonical_path") or [])
    if path != list(GOLDEN_PATH):
        return _check("resource_coverage", False, "No source manifest exists for the mapped goal.", missing_concepts=path)
    # N1 certifies the already-reviewed static manifest. N2 will run a fresh
    # generation probe and page/chunk resolution without reading a lecture cache.
    return _check(
        "resource_coverage", True,
        "Every controlled golden node has a reviewed source manifest; fresh page/chunk resolution is still required at run time.",
        covered_concepts=path,
        source_registry_version=GOLDEN_PATH_VERSION,
    )


def _not_run_content_probe() -> dict[str, Any]:
    return _check(
        "content_generation", False,
        "No uncached live generation probe has been run for this admission decision.",
        generation_mode=None,
        cache_status="not_checked",
        fallback_accepted=False,
    )


def _not_run_grounding_probe() -> dict[str, Any]:
    return _check(
        "grounding", False,
        "No fresh schema and page/chunk grounding probe has been run for this admission decision.",
        source_refs=[],
        cache_status="not_checked",
    )


def baseline_admission(goal_spec: dict[str, str]) -> dict[str, Any]:
    """Return today's conservative admission result without making external calls."""
    mapping = _golden_mapping(goal_spec["goal"])
    catalog_match = resolve_goal_chain(goal_spec["goal"])
    if catalog_match:
        goal_id, spec = catalog_match
        source = ExperienceSourceStore(Path(__file__).with_name("pathly_experience_sources.db")).get(
            {"word_embeddings": "source:word-embeddings:cs224n-2026-wordvecs", "self_attention": "source:self-attention:cs224n-2026-transformers", "rag": "source:rag:cs224n-2026-rag-agents"}[goal_id]
        )
        manifest = TeachingAssetStore().current_scoped_manifest(spec["asset_scope"])
        path = list(spec["canonical_path"])
        mapping = _check("goal_mapping", True, "Goal matches an approved goal-scoped canonical chain.", target_concept=path[-1], canonical_path=path, mapping_method="goal_chain_catalog", catalog_version=GOAL_CHAIN_CATALOG_VERSION)
        kg_path = _check("kg_path", len(path) == len(set(path)), "Approved catalog path is ordered and acyclic.", ordered_concepts=path, acyclic=True, path_provenance="goal_chain_catalog")
        resource = _check("resource_coverage", bool(source and source.get("pages") and manifest), "Approved page-level source and scoped teaching-asset bundle are available." if source and source.get("pages") and manifest else "Approved source pages or scoped teaching assets are missing.", source_id=(source or {}).get("source_id"), page_count=len((source or {}).get("pages") or []), asset_manifest=(manifest or {}).get("manifest_version"))
        return GoalAdmissionValidator().validate(goal=goal_spec["goal"], mapping=mapping, kg_path=kg_path, resource_coverage=resource, content_generation=_not_run_content_probe(), grounding=_not_run_grounding_probe())
    kg_path = _controlled_golden_kg_path(mapping)
    return GoalAdmissionValidator().validate(
        goal=goal_spec["goal"],
        mapping=mapping,
        kg_path=kg_path,
        resource_coverage=_golden_resources(mapping),
        content_generation=_not_run_content_probe(),
        grounding=_not_run_grounding_probe(),
    )


def validate_with_probes(
    *, goal: str, mapping: dict[str, Any], kg_path: dict[str, Any], resource_coverage: dict[str, Any],
    content_probe: Callable[[], dict[str, Any]], grounding_probe: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Execution hook for N2+; probes must report cache and generation mode."""
    return GoalAdmissionValidator().validate(
        goal=goal,
        mapping=mapping,
        kg_path=kg_path,
        resource_coverage=resource_coverage,
        content_generation=content_probe(),
        grounding=grounding_probe(),
    )


def build_baseline_admission_report() -> dict[str, Any]:
    results = [{"goal_id": item["id"], **baseline_admission(item)} for item in TARGET_GOALS]
    return {
        "admission_version": ADMISSION_VERSION,
        "generated_at": _now(),
        "read_only": True,
        "purpose": "N1 protocol baseline; this report does not create users, plans, or lectures.",
        "results": results,
        "summary": {status: sum(item["status"] == status for item in results) for status in sorted(VALID_STATUSES)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_baseline_admission_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
