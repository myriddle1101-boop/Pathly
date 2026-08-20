"""Read-only N0 baseline for fresh-user and multi-goal experience work.

This module deliberately does not create users, plans, lectures, cache entries,
or KG records.  It records what the currently shipped product can prove before
the new admission and evaluation features are added.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verified_golden_sources import GOLDEN_PATH, GOLDEN_PATH_VERSION, verified_goal_concepts_for_goal


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "artifacts" / "n0_fresh_experience_baseline.json"
BASELINE_VERSION = "fresh-experience-n0-v1"

TARGET_GOALS = (
    {
        "id": "xor",
        "goal": "Explain how neural networks learn to solve XOR.",
        "expected_domain": "neural_foundations",
    },
    {
        "id": "word_embeddings",
        "goal": "Understand how word embeddings represent semantic similarity.",
        "expected_domain": "representation_learning",
    },
    {
        "id": "self_attention",
        "goal": "Understand how self-attention enables transformers to model context.",
        "expected_domain": "transformers",
    },
    {
        "id": "rag",
        "goal": "Understand how retrieval-augmented generation uses retrieved evidence to answer a query.",
        "expected_domain": "retrieval_augmented_generation",
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_version_matrix() -> list[dict[str, Any]]:
    """Describe the actual shipped views, not desired ablation labels."""
    return [
        {
            "current_id": "v1",
            "current_name": "Study Blocks View v1",
            "contract": "daily-content-v2",
            "generator": "content-agent-v7",
            "profile": True,
            "kg_or_retrieval_context": True,
            "source_grounding": "bounded retrieved evidence when available; not a page-level source contract",
            "teaching_assets": False,
            "model_dependency": "live model with existing fallback path",
            "is_controlled_ablation": False,
        },
        {
            "current_id": "v2",
            "current_name": "Annotated Source View v2",
            "contract": "annotated-session-v1",
            "generator": "content-agent-v2-source-first-a8-related-page-sequence",
            "profile": True,
            "kg_or_retrieval_context": True,
            "source_grounding": "source-first annotated readings and citations",
            "teaching_assets": False,
            "model_dependency": "session generator",
            "is_controlled_ablation": False,
        },
        {
            "current_id": "v3",
            "current_name": "Full Lecture View v3",
            "contract": "full-lecture-v3",
            "generator": "deterministic transformation of the v2 annotated session",
            "profile": "inherits upstream session rather than being an isolated treatment",
            "kg_or_retrieval_context": "inherits upstream session",
            "source_grounding": "preserves v2 citations",
            "teaching_assets": False,
            "model_dependency": "no direct model dependency in the v3 generator",
            "is_controlled_ablation": False,
        },
        {
            "current_id": "v4",
            "current_name": "Source-Grounded Lecture View v4",
            "contract": "source-grounded-lecture-v4",
            "generator": "source-grounded-v4-live-assets-v3",
            "profile": True,
            "kg_or_retrieval_context": True,
            "source_grounding": "page-level verified/public source links",
            "teaching_assets": True,
            "model_dependency": "live model with approved asset-backed completion/fallback",
            "is_controlled_ablation": False,
        },
    ]


def goal_probe(goal: dict[str, str]) -> dict[str, Any]:
    """Report only currently certified coverage; never infer a new golden chain."""
    canonical_path = verified_goal_concepts_for_goal(goal["goal"])
    if canonical_path:
        return {
            **goal,
            "baseline_status": "candidate_for_revalidation",
            "certified_canonical_path": canonical_path,
            "certified_path_version": GOLDEN_PATH_VERSION,
            "reason": "Matches the existing neural-foundations verified path; N1 must still run the new admission checks.",
        }
    return {
        **goal,
        "baseline_status": "not_certified_for_full_experience",
        "certified_canonical_path": [],
        "certified_path_version": None,
        "reason": "No current verified full-experience path is registered for this goal; do not reuse the XOR chain or fallback as evidence of success.",
    }


def build_baseline() -> dict[str, Any]:
    return {
        "baseline_version": BASELINE_VERSION,
        "generated_at": _now(),
        "read_only": True,
        "scope": {
            "existing_benchmark_preserved": True,
            "fresh_user_created": False,
            "plan_created": False,
            "content_cache_created": False,
        },
        "existing_verified_path": {
            "concepts": list(GOLDEN_PATH),
            "version": GOLDEN_PATH_VERSION,
            "scope": "neural-foundations only",
        },
        "fresh_user_baseline": {
            "anonymous_sessions_exist": True,
            "first_time_onboarding_exists": True,
            "onboarding_generates_profile": True,
            "demo_profiles_exist": ["Foundation Learner", "Advanced Learner"],
            "gap": "No explicit product entry yet guarantees a new empty user and prevents demo fixture reuse.",
        },
        "current_version_matrix": current_version_matrix(),
        "goal_probes": [goal_probe(goal) for goal in TARGET_GOALS],
        "required_next_step": "N1 admission validation; baseline statuses are not eligibility decisions.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_baseline()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "goals": len(payload["goal_probes"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
