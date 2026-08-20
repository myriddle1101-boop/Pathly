"""Build reproducible, zero-model-call evaluation inventory and KG health outputs."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KG = ROOT.parent / "KG_construction"
RESULTS = ROOT / "evaluation" / "results"

sys.path.insert(0, str(ROOT))
from verified_golden_sources import VerifiedGoldenSourceRegistry, verified_goal_concepts_for_goal
from kg_corpus_audit import audit_runs, write_outputs


def _exists(path: Path) -> bool:
    return path.exists()


def build_inventory() -> list[dict[str, Any]]:
    locations = {
        "KG quality P/R/F1": [KG / "evaluation" / "kg_quality_eval.py", KG / "evaluation" / "annotations"],
        "KG benchmark harness": [KG / "evaluation" / "kg_benchmark.py", KG / "evaluation" / "task4_experiment_manifest.json"],
        "KG corpus health audit": [ROOT / "evaluation" / "kg_corpus_audit.py"],
        "Planning implementation/tests": [KG / "agents" / "planning_agent.py", KG / "tests" / "test_planning_agent.py", ROOT / "tests" / "test_pathly_planning_api.py"],
        "Content V4 quality gates": [ROOT / "source_grounded_v4_generator.py", ROOT / "v4_quality_baseline.py", ROOT / "tests" / "test_source_grounded_v4_s4.py"],
        "Adaptation candidate prototype": [KG / "agents" / "adaptation_candidate_service.py", KG / "tests" / "test_adaptation_candidate_service.py"],
        "Live golden-chain audit": [ROOT / "kg_golden_audit.py", ROOT / "artifacts" / "k1_golden_chain_audit_current.json"],
    }
    rows = []
    for target, paths in locations.items():
        present = [str(path) for path in paths if _exists(path)]
        rows.append({
            "evaluation_object": target,
            "existing_code": bool(present),
            "existing_data_or_artifact": bool(present[1:]),
            "missing_or_limit": "See evaluation README; tests are engineering evidence, not research results.",
            "directly_runnable": bool(present),
            "evidence_paths": " | ".join(present),
        })
    return rows


def build_goal_results() -> list[dict[str, Any]]:
    catalog = json.loads((ROOT / "evaluation" / "goal_catalog.json").read_text(encoding="utf-8"))
    registry = VerifiedGoldenSourceRegistry(KG)
    rows = []
    for tier in ("full_experience", "planning_exploratory_only"):
        for item in catalog[tier]:
            goal = item["goal_text"]
            concepts = verified_goal_concepts_for_goal(goal)
            rows.append({
                "case_id": item["id"], "tier": tier, "goal_text": goal,
                "verified_goal_match": registry.matches_goal(goal),
                "verified_concepts": " | ".join(concepts),
                "verified_concept_count": len(concepts),
                "intent_or_limit": item.get("intent") or item.get("reason", ""),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(); goals = build_goal_results()
    write_csv(RESULTS / "evaluation_status.csv", inventory)
    write_csv(RESULTS / "goal_catalog_validation.csv", goals)
    audit = audit_runs(); write_outputs(audit, RESULTS / "kg_corpus_audit.json")
    manifest = {
        "evaluation_pack_version": "2026-08-15-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_calls": 0,
        "files": ["evaluation_status.csv", "goal_catalog_validation.csv", "kg_corpus_audit.json", "kg_corpus_audit.csv", "kg_corpus_audit_summary.csv"],
        "scope_note": "Planning/content/adaptation score files require generated outputs or manual ratings and are intentionally not fabricated by this static pack.",
    }
    (RESULTS / "static_pack_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"inventory_rows": len(inventory), "goal_rows": len(goals), **audit["totals"]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
