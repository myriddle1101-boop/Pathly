"""Run uncached live Content Agent and grounding admission probes for four goals."""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experience_admission import baseline_admission, GoalAdmissionValidator, _check
from experience_source_store import ExperienceSourceStore
from fresh_experience_baseline import TARGET_GOALS
from goal_chain_catalog import resolve_goal_chain
from source_grounded_v4_generator import generate_source_grounded_lecture_v4
from teaching_asset_store import TeachingAssetStore
from verified_golden_sources import VerifiedGoldenSourceRegistry


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifacts" / "n4_live_admission_report.json"
SOURCE_IDS = {
    "word_embeddings": "source:word-embeddings:cs224n-2026-wordvecs",
    "self_attention": "source:self-attention:cs224n-2026-transformers",
    "rag": "source:rag:cs224n-2026-rag-agents",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperienceEvidenceResolver:
    def __init__(self, record: dict[str, Any]):
        self.record = record

    def page_evidence(self, link: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"page_number": page["page_number"], "text": page["text"], "chunk_id": page["chunk_id"]}
            for page in self.record.get("pages") or []
        ]


def _new_goal_input(goal_spec: dict[str, str]) -> tuple[str, dict[str, Any], Any]:
    if goal_spec["id"] == "xor":
        registry = VerifiedGoldenSourceRegistry(ROOT.parent / "KG_construction")
        concept_name = "XOR"
        link = registry.resolve(concept_id=concept_name, concept_name=concept_name)
        if not link:
            raise RuntimeError("verified XOR source is unavailable")
        link = {**link, "concept_id": concept_name, "concept_name": concept_name, "source_version": "source-grounded-golden-s2-v1", "link_role": "primary"}
        return concept_name, link, registry

    match = resolve_goal_chain(goal_spec["goal"])
    if not match:
        raise RuntimeError("goal chain catalog mapping is unavailable")
    goal_id, spec = match
    record = ExperienceSourceStore(ROOT / "pathly_experience_sources.db").get(SOURCE_IDS[goal_id])
    manifest = TeachingAssetStore().current_scoped_manifest(spec["asset_scope"])
    if not record or not manifest:
        raise RuntimeError("approved source or scoped asset manifest is unavailable")
    concept_id = spec["canonical_path"][-1]
    concept_name = {
        "word_embeddings": "Semantic Similarity",
        "self_attention": "Contextual Representations",
        "rag": "Retrieval-Augmented Generation",
    }[goal_id]
    link = {
        "link_id": f"admission:{goal_id}",
        "concept_id": concept_id,
        "concept_name": concept_name,
        "resource_id": record["resource_id"],
        "document_id": record["document_id"],
        "document_title": record["document_title"],
        "source_scope": "public",
        "page_sequence": [
            {"page_number": page["page_number"], "role": page["content_role"], "chunk_ids": [page["chunk_id"]]}
            for page in record["pages"]
        ],
        "chunk_ids": [page["chunk_id"] for page in record["pages"]],
        "review_status": "verified",
        "source_version": record["source_version"],
        "link_role": "primary",
        "asset_concept_id": concept_id,
        "asset_manifest_version": manifest["manifest_version"],
    }
    return concept_name, link, ExperienceEvidenceResolver(record)


def _grounding(section: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], list[str]]:
    pages = section.get("source_pages") or []
    refs = []
    for page in pages:
        link = (section.get("source_links") or [{}])[0]
        page_spec = next(
            (item for item in link.get("page_sequence") or [] if int(item.get("page_number") or 0) == int(page.get("page_number") or 0)),
            {},
        )
        refs.append({
            "resource_id": page.get("resource_id"),
            "document_id": page.get("document_id"),
            "page_number": page.get("page_number"),
            "chunk_id": next(iter(page_spec.get("chunk_ids") or []), None),
            "evidence_locator": next(iter(page_spec.get("chunk_ids") or []), None) or f"page:{page.get('page_number')}",
        })
    content = section.get("lecture_content") or {}
    required = {"concept_introduction", "prerequisite_recap", "page_walkthrough", "worked_example", "objective_exercise", "summary_connection"}
    errors: list[str] = []
    if not required.issubset(content):
        errors.append("schema_missing_fields")
    if not refs or any(not ref["resource_id"] or not ref["document_id"] or not ref["page_number"] or not ref["evidence_locator"] for ref in refs):
        errors.append("incomplete_page_chunk_provenance")
    questions = (content.get("objective_exercise") or {}).get("questions") or []
    if len(questions) != 3 or any(not item.get("source_refs") for item in questions):
        errors.append("exercise_grounding_incomplete")
    learner_text = json.dumps(content, ensure_ascii=False)
    corrupt_markers = ("锟", "鈥", "饾", "�", "\x00")
    if any(marker in learner_text for marker in corrupt_markers):
        errors.append("learner_content_contains_ocr_corruption")
    return not errors, refs, errors


def run_goal(goal_spec: dict[str, str]) -> dict[str, Any]:
    baseline = baseline_admission(goal_spec)
    run_id = f"admission-{goal_spec['id']}-{uuid.uuid4().hex[:12]}"
    try:
        concept_name, link, resolver = _new_goal_input(goal_spec)
        section_id = f"{run_id}:core"
        v3 = {
            "contract_version": "full-lecture-v3", "plan_id": run_id, "path_id": run_id, "day": 1,
            "lecture_sections": [{"section_id": section_id, "concept_id": link["concept_id"], "concept_name": concept_name, "title": concept_name, "estimated_minutes": 15}],
            "generation_metadata": {"generator_version": "n4-uncached-structural-seed", "generation_mode": "structural_seed"},
        }
        lecture = generate_source_grounded_lecture_v4(
            v3_lecture=v3, source_links=[link], daily={"prepared_evidence": []},
            user_id=f"evaluation-{uuid.uuid4()}",
            profile={"profile_version": 1, "prior_knowledge_level": 3, "math_foundation": 3, "programming_foundation": 3, "preferred_style": "balanced", "interest_tags": []},
            verified_registry=resolver,
        )
        section = (lecture.get("lecture_sections") or [{}])[0]
        mode = str(section.get("generation_mode") or "")
        exercise_mode = str(section.get("exercise_generation_mode") or "")
        content_passed = section.get("v4_status") == "ready" and mode in {"live", "live_augmented"} and exercise_mode == "live"
        grounded, refs, grounding_errors = _grounding(section)
        content_check = _check("content_generation", content_passed, "Uncached live lecture and live exercise generation completed." if content_passed else "The uncached probe did not produce both a live lecture and live exercise.", generation_mode=mode, cache_status="miss", fallback_accepted=False, run_id=run_id, failure_code=section.get("failure_code"), failure_reason=section.get("failure_reason"), fallback_reason=section.get("fallback_reason"), exercise_generation_mode=section.get("exercise_generation_mode"), exercise_generation_reason=section.get("exercise_generation_reason"))
        grounding_check = _check("grounding", grounded, "Schema and page/chunk provenance checks passed." if grounded else "Grounding or schema checks failed.", source_refs=refs, cache_status="miss", errors=grounding_errors)
        result = GoalAdmissionValidator().validate(goal=goal_spec["goal"], mapping=baseline["checks"]["goal_mapping"], kg_path=baseline["checks"]["kg_path"], resource_coverage=baseline["checks"]["resource_coverage"], content_generation=content_check, grounding=grounding_check)
        return {"goal_id": goal_spec["id"], "run_id": run_id, **result, "run_artifact": {"selected_system_version": "v4", "cache_status": "miss", "generation_metadata": lecture.get("generation_metadata"), "source_refs": refs, "core_content_output": section}}
    except Exception as exc:
        content_check = _check("content_generation", False, "Live probe raised an exception.", generation_mode=None, cache_status="miss", fallback_accepted=False, run_id=run_id, error_type=type(exc).__name__, error=str(exc))
        grounding_check = _check("grounding", False, "No live output was available for grounding validation.", source_refs=[], cache_status="miss")
        result = GoalAdmissionValidator().validate(goal=goal_spec["goal"], mapping=baseline["checks"]["goal_mapping"], kg_path=baseline["checks"]["kg_path"], resource_coverage=baseline["checks"]["resource_coverage"], content_generation=content_check, grounding=grounding_check)
        return {"goal_id": goal_spec["id"], "run_id": run_id, **result, "run_artifact": None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    results = [run_goal(spec) for spec in TARGET_GOALS]
    report = {"probe_version": "n4-live-admission-v1", "generated_at": _now(), "cache_policy": "direct generator invocation; no store reads or writes", "fallback_is_success": False, "results": results, "summary": {status: sum(item["status"] == status for item in results) for status in ("eligible_for_full_experience", "planning_only", "blocked")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
