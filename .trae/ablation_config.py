"""Auditable system-version contract for controlled evaluations.

These flags describe the runtime treatment; they do not change the ordinary
New Learner product entry.  Keeping the contract in one module prevents the
four UI tabs from being mistaken for four experimental systems.
"""
from __future__ import annotations

from copy import deepcopy

ABLATION_VERSION = "ablation-contract-v2"

SYSTEM_CONFIGS = {
    "V0": {
        "name": "Pure LLM",
        "profile": False,
        "kg": False,
        "teaching_assets": False,
        "source_grounding": False,
        "fallback_allowed": False,
        "product_surface": None,
        "current_final_system": False,
    },
    "V1": {
        "name": "LLM + Learner Profile",
        "profile": True,
        "kg": False,
        "teaching_assets": False,
        "source_grounding": False,
        "fallback_allowed": False,
        "product_surface": None,
        "current_final_system": False,
    },
    "V2": {
        "name": "LLM + Learner Profile + KG",
        "profile": True,
        "kg": True,
        # Keep V2 source-free and asset-free so the V2->V3 delta isolates the
        # final source-grounded teaching system instead of mixing variables.
        "teaching_assets": False,
        "source_grounding": False,
        "fallback_allowed": False,
        "product_surface": None,
        "current_final_system": False,
    },
    "V3": {
        "name": "Full System (current lecture-v4 pipeline)",
        "profile": True,
        "kg": True,
        "teaching_assets": True,
        "source_grounding": True,
        "fallback_allowed": False,
        # Controlled-evaluation V3 is intentionally the same final system that
        # the product exposes as the learner-facing source-grounded lecture v4.
        "product_surface": "lecture-v4",
        "current_final_system": True,
    },
}


def get_system_config(version: str) -> dict:
    key = str(version or "").upper()
    if key not in SYSTEM_CONFIGS:
        raise ValueError(f"unknown controlled evaluation version: {version}")
    return {"version": key, "ablation_version": ABLATION_VERSION, **deepcopy(SYSTEM_CONFIGS[key])}


def capability_matrix() -> list[dict]:
    return [get_system_config(version) for version in ("V0", "V1", "V2", "V3")]
