from pathly_server import _normalise_controlled_concept_path, _normalise_controlled_plan_timing


def test_controlled_timing_is_derived_from_total_and_daily_minutes():
    plan = _normalise_controlled_plan_timing(
        {
            "estimated_total_minutes": 120,
            "estimated_days": 99,
            "recommended_daily_minutes": 40,
            "session_minutes": 20,
        }
    )

    assert plan["estimated_days"] == 3
    assert plan["session_minutes"] == 40
    assert plan["day_1_minutes"] == 40


def test_controlled_timing_recomputes_deadline_feasibility():
    plan = _normalise_controlled_plan_timing(
        {"estimated_total_minutes": 121, "recommended_daily_minutes": 40},
        deadline_days=3,
    )

    assert plan["estimated_days"] == 4
    assert plan["feasibility"]["status"] == "infeasible"


def test_v3_planner_object_path_is_normalised_for_section_assembly():
    assert _normalise_controlled_concept_path(
        [{"order": 1, "concept": "Token Representations"}, {"concept_name": "Self-Attention"}],
        ["fallback"],
    ) == ["Token Representations", "Self-Attention"]
