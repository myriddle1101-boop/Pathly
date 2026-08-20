"""Generate controlled Planning Agent cases and rule-based checks.

The script calls the live configured KG, but never writes learner profiles or
plans to the production Pathly stores.  It is therefore safe to rerun.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KG = ROOT.parent / "KG_construction"
sys.path.insert(0, str(KG)); sys.path.insert(0, str(ROOT))

from env_loader import load_project_env
from agents.planning_agent import PlanningAgent
from infra.profile_schema import LearnerProfile

RESULTS = ROOT / "evaluation" / "results"


def profile(tier: str, goal: str, user_id: str) -> LearnerProfile:
    advanced = tier == "advanced"
    return LearnerProfile(
        user_id=user_id, name=tier.title(), academic_level="postgraduate",
        domain="self-directed machine learning", goal_text=goal,
        target_days=14, daily_minutes=60, prior_knowledge_level=5 if advanced else 1,
        math_foundation=5 if advanced else 2, programming_foundation=5 if advanced else 2,
        self_regulation=4 if advanced else 2, preferred_style="theory" if advanced else "example",
        preferred_examples=["research", "code"] if advanced else ["daily_life"],
        interest_tags=["computer_vision"] if advanced else ["no_preference"],
        pace_preference="intensive" if advanced else "steady",
        confidence_level=5 if advanced else 2, anxiety_level=2 if advanced else 4,
        known_topics=["Linear Separability", "XOR"] if advanced else [],
        mastery_vector={"Linear Separability": 0.9, "XOR": 0.85} if advanced else {},
    )


def plan_topic_order(plan: dict[str, Any]) -> list[str]:
    return [str(item) for item in (plan.get("ordered_topics") or plan.get("target_topics") or [])]


def auto_checks(plan: dict[str, Any], learner: LearnerProfile) -> dict[str, Any]:
    days = list(plan.get("days") or [])
    daily_totals = [int(day.get("total_minutes") or day.get("estimated_minutes") or 0) for day in days]
    ordered = plan_topic_order(plan)
    feasibility = plan.get("feasibility") or {}
    excluded = set(learner.known_topics) | {key for key, value in learner.mastery_vector.items() if value >= 0.8}
    has_warning = bool(feasibility.get("status") or feasibility.get("warning") or feasibility.get("warnings"))
    return {
        "has_nonempty_plan": bool(days and ordered),
        "within_daily_limit": all(minutes <= learner.daily_minutes for minutes in daily_totals),
        "has_feasibility_status": has_warning,
        "time_constraint_handled": all(minutes <= learner.daily_minutes for minutes in daily_totals) or bool(feasibility.get("warning") or feasibility.get("warnings")),
        "per_item_limit_warning": bool(feasibility.get("warning") or feasibility.get("warnings")),
        "known_or_mastered_not_repeated": not bool(set(ordered) & excluded),
        "target_mapping_present": bool((plan.get("mapping") or {}).get("matched_targets") or plan.get("target_topics")),
        "day_count": len(days), "max_daily_minutes_observed": max(daily_totals, default=0),
        "ordered_topics": ordered,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=RESULTS)
    parser.add_argument("--catalog", type=Path, default=ROOT / "evaluation" / "goal_catalog.json")
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    load_project_env(); os.environ["KG_BACKEND"] = "neo4j"
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    planner = PlanningAgent(kg_backend="neo4j")
    cases, summary = [], []
    for goal_case in catalog["full_experience"]:
        for tier in ("foundation", "advanced"):
            case_id = f"{goal_case['id']}-{tier}"
            learner = profile(tier, goal_case["goal_text"], f"evaluation-{case_id}")
            record: dict[str, Any] = {"case_id": case_id, "goal_id": goal_case["id"], "tier": tier, "goal_text": goal_case["goal_text"], "profile": learner.to_dict()}
            try:
                plan = planner.generate_plan(learner.goal_text, learner)
                checks = auto_checks(plan, learner)
                record.update({"status": "generated", "plan": plan, "automatic_checks": checks})
                summary.append({"case_id": case_id, "goal_id": goal_case["id"], "tier": tier, "status": "generated", **{key: value for key, value in checks.items() if key != "ordered_topics"}})
            except Exception as exc:  # preserves failure evidence instead of hiding it
                record.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
                summary.append({"case_id": case_id, "goal_id": goal_case["id"], "tier": tier, "status": "failed", "has_nonempty_plan": False, "within_daily_limit": False, "has_feasibility_status": False, "time_constraint_handled": False, "per_item_limit_warning": False, "known_or_mastered_not_repeated": False, "target_mapping_present": False, "day_count": 0, "max_daily_minutes_observed": 0})
            cases.append(record)
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "protocol": "five controlled goal phrasings x two profiles; same 14-day and 60-minute budget", "kg_backend": "neo4j", "cases": cases}
    (args.output_dir / "planning_cases.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(args.output_dir / "planning_scores.csv", summary)
    aggregate = [{"metric": key, "value": sum(bool(row.get(key)) for row in summary if row["status"] == "generated") / max(1, sum(row["status"] == "generated" for row in summary))} for key in ("has_nonempty_plan", "within_daily_limit", "has_feasibility_status", "time_constraint_handled", "per_item_limit_warning", "known_or_mastered_not_repeated", "target_mapping_present")]
    write_csv(args.output_dir / "planning_summary.csv", aggregate)
    print(json.dumps({"generated": sum(row["status"] == "generated" for row in summary), "total": len(summary)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
