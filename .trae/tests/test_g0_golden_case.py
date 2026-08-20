from g0_golden_case import G0GoldenCaseService, G0_MINUTES_PER_DAY, build_g0_plan
from verified_golden_sources import GOLDEN_PATH


def test_g0_plan_is_stable_and_preserves_the_verified_prerequisite_chain():
    first = build_g0_plan("demo-user")
    second = build_g0_plan("demo-user")

    assert first == second
    assert first["ordered_topics"] == list(GOLDEN_PATH)
    assert [day["focus_topics"][0] for day in first["days"]] == list(GOLDEN_PATH)
    assert all(day["total_minutes"] == G0_MINUTES_PER_DAY for day in first["days"])
    assert first["concept_path"][0]["prerequisite_ids"] == []
    assert [item["prerequisite_ids"] for item in first["concept_path"][1:]] == [
        ["Linear Separability"], ["XOR"], ["Neural Networks"], ["Activation Functions"]
    ]


def _ready_lecture(concept: str):
    return {
        "lecture_sections": [{
            "concept_name": concept,
            "v4_status": "ready",
            "source_links": [{"review_status": "verified"}],
            "source_pages": [{"page_number": 1}, {"page_number": 2}],
            "lecture_content": {
                "concept_introduction": {"explanation": f"{concept} mechanism"},
                "worked_example": {"steps": ["one", "two", "three"]},
                "objective_exercise": {"questions": [{}, {}, {}]},
            },
        }]
    }


def test_g0_quality_report_requires_all_five_clean_ready_lessons():
    lectures = [_ready_lecture(concept) for concept in GOLDEN_PATH]
    assert G0GoldenCaseService.quality_report(lectures)["passed"] is True

    lectures[0]["lecture_sections"][0]["lecture_content"]["concept_introduction"]["explanation"] = (
        "Pathly generated this teaching method"
    )
    report = G0GoldenCaseService.quality_report(lectures)
    assert report["passed"] is False
    assert report["days"][0]["checks"]["no_meta_language"] is False


def test_g0_quality_report_rejects_corrupt_pdf_glyphs():
    lectures = [_ready_lecture(concept) for concept in GOLDEN_PATH]
    lectures[4]["lecture_sections"][0]["lecture_content"]["worked_example"]["solution"] = "broken \u00a6 symbol"
    report = G0GoldenCaseService.quality_report(lectures)
    assert report["passed"] is False
    assert report["days"][4]["checks"]["readable_symbols"] is False


def test_g0_shared_lecture_template_is_read_only_and_reusable_per_day(tmp_path):
    from source_grounded_v4_store import SourceGroundedLectureV4Store

    store = SourceGroundedLectureV4Store(tmp_path / "v4.sqlite")
    seed = {"generation_metadata": {"g0_version": "g0-neural-foundations-v1"}, "day": 1}
    store.save("seed-user", "seed-plan", 1, seed)

    reused = store.find_by_generation_metadata("g0_version", "g0-neural-foundations-v1", 1)
    assert reused == seed
    reused["day"] = 99
    assert store.get("seed-user", "seed-plan", 1)["day"] == 1
