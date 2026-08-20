from experience_admission import GoalAdmissionValidator, baseline_admission
from fresh_experience_baseline import TARGET_GOALS


def _passed(name):
    return {"name": name, "passed": True, "reason": "ok", "details": {}}


def test_eligibility_requires_every_check_to_pass():
    result = GoalAdmissionValidator().validate(
        goal="g", mapping=_passed("goal_mapping"), kg_path=_passed("kg_path"),
        resource_coverage=_passed("resource_coverage"), content_generation=_passed("content_generation"),
        grounding=_passed("grounding"),
    )
    assert result["status"] == "eligible_for_full_experience"


def test_missing_generation_or_grounding_is_planning_only_not_eligible():
    result = baseline_admission(TARGET_GOALS[0])
    assert result["status"] == "planning_only"
    assert {item["code"] for item in result["failure_reasons"]} == {"generation_failure", "grounding_failure"}


def test_unmapped_goal_is_blocked_with_a_precise_reason():
    result = GoalAdmissionValidator().validate(
        goal="unknown", mapping={"name":"goal_mapping","passed":False,"reason":"no mapping","details":{}},
        kg_path={"name":"kg_path","passed":False,"reason":"no path","details":{}},
        resource_coverage=_passed("resource_coverage"), content_generation=_passed("content_generation"), grounding=_passed("grounding"),
    )
    assert result["status"] == "blocked"
    assert result["failure_reasons"][0]["code"] == "unmapped_goal"


def test_published_goal_scoped_chain_is_planning_only_until_live_probe():
    result = baseline_admission(TARGET_GOALS[1])
    assert result["status"] == "planning_only"
    assert result["checks"]["goal_mapping"]["passed"] is True
    assert result["checks"]["resource_coverage"]["passed"] is True
