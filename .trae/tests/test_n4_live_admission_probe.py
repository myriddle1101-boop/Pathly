import json
from pathlib import Path

from fresh_experience_baseline import TARGET_GOALS
from n4_live_admission_probe import _grounding


ROOT = Path(__file__).resolve().parents[1]


def test_committed_n4_report_contains_four_strict_uncached_live_passes():
    report = json.loads((ROOT / "artifacts" / "n4_live_admission_report.json").read_text(encoding="utf-8"))
    assert report["fallback_is_success"] is False
    assert report["summary"] == {
        "eligible_for_full_experience": 4,
        "planning_only": 0,
        "blocked": 0,
    }
    assert {item["goal_id"] for item in report["results"]} == {item["id"] for item in TARGET_GOALS}
    for item in report["results"]:
        content = item["checks"]["content_generation"]
        grounding = item["checks"]["grounding"]
        section = item["run_artifact"]["core_content_output"]
        assert item["status"] == "eligible_for_full_experience"
        assert content["passed"] is True
        assert content["details"]["cache_status"] == "miss"
        assert content["details"]["fallback_accepted"] is False
        assert content["details"]["generation_mode"] in {"live", "live_augmented"}
        assert content["details"]["exercise_generation_mode"] == "live"
        assert grounding["passed"] is True
        assert grounding["details"]["source_refs"]
        assert section["teaching_asset_ids"]


def test_grounding_gate_rejects_learner_visible_ocr_corruption():
    section = {
        "source_links": [{"chunk_ids": ["chunk-1"], "page_sequence": [{"page_number": 1, "chunk_ids": ["chunk-1"]}]}],
        "source_pages": [{"resource_id": "resource-1", "document_id": "document-1", "page_number": 1}],
        "lecture_content": {
            "concept_introduction": {"explanation": "Broken 饾 formula"},
            "prerequisite_recap": {}, "page_walkthrough": [], "worked_example": {},
            "summary_connection": {},
            "objective_exercise": {"questions": [
                {"source_refs": ["page:1"]}, {"source_refs": ["page:1"]}, {"source_refs": ["page:1"]},
            ]},
        },
    }
    passed, _, errors = _grounding(section)
    assert passed is False
    assert "learner_content_contains_ocr_corruption" in errors
