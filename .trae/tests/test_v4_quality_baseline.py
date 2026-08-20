from source_grounded_v4_generator import (
    V4_PROMPT_VERSION,
    _build_verified_source_content,
    _profile_treatment,
    _v4_generation_brief,
    _with_f9_exercise_support,
)
from v4_quality_baseline import (
    CONTROLLED_DUAL_USER_SCENARIO,
    NORMAL_PROFILE_FIXTURES,
    evaluate_objective_exercise,
    golden_baseline_manifest,
)


def _base():
    return {
        "concept_name": "Linear Separability",
        "source_links": [{"review_status": "verified"}],
    }


def _request():
    return {
        "concept": {"name": "Linear Separability"},
        "learner_profile": NORMAL_PROFILE_FIXTURES["foundation_learner"],
        "sources": [
            {"page_number": 2, "role": "introduction", "text": "XOR is not linearly separable."},
            {"page_number": 3, "role": "mechanism", "text": "A straight line cannot separate the XOR classes."},
        ],
    }


def test_kq0_manifest_fixes_five_nodes_and_two_normal_profiles():
    manifest = golden_baseline_manifest()
    assert len(manifest["golden_concepts"]) == 5
    assert set(manifest["normal_profiles"]) == {"foundation_learner", "advanced_learner"}


def test_dp0_dual_users_have_distinct_ids_and_decision_complete_answer_cards():
    foundation = NORMAL_PROFILE_FIXTURES["foundation_learner"]
    advanced = NORMAL_PROFILE_FIXTURES["advanced_learner"]
    assert foundation["user_id"] != advanced["user_id"]
    assert foundation["cognitive_traits"] == {
        "mathematical_ability": 2,
        "programming_ability": 2,
        "abstract_thinking": 2,
        "logical_reasoning": 2,
        "general_learning_foundation": 2,
    }
    assert advanced["cognitive_traits"] == {
        "mathematical_ability": 5,
        "programming_ability": 5,
        "abstract_thinking": 5,
        "logical_reasoning": 5,
        "general_learning_foundation": 4,
    }
    assert foundation["path_context"] == {
        "target_familiarity": "never",
        "current_confidence": 2,
        "current_anxiety": 4,
        "path_style_override": "use_default",
    }
    assert advanced["path_context"] == {
        "target_familiarity": "applied",
        "current_confidence": 5,
        "current_anxiety": 2,
        "path_style_override": "use_default",
    }


def test_dp0_controlled_scenario_does_not_confound_profile_with_time_or_sources():
    assert CONTROLLED_DUAL_USER_SCENARIO["golden_concepts"] == golden_baseline_manifest()["golden_concepts"]
    assert CONTROLLED_DUAL_USER_SCENARIO["daily_minutes"] == 60
    assert CONTROLLED_DUAL_USER_SCENARIO["requested_days"] == 60
    assert CONTROLLED_DUAL_USER_SCENARIO["same_deadline"] is True
    assert CONTROLLED_DUAL_USER_SCENARIO["same_source_version"] is True


def test_dp0_long_term_fixtures_do_not_store_confidence_or_pressure():
    for profile in NORMAL_PROFILE_FIXTURES.values():
        affective = profile["affective_defaults"]
        assert "confidence_baseline" not in affective
        assert "anxiety_baseline" not in affective
        assert "current_confidence" in profile["path_context"]
        assert "current_anxiety" in profile["path_context"]


def test_dp3_expert_prompt_is_versioned_and_decision_complete():
    profile = NORMAL_PROFILE_FIXTURES["foundation_learner"]
    treatment = _profile_treatment(profile)
    brief = _v4_generation_brief(
        concept="Linear Separability", treatment=treatment, approved_profile={"approved": True}
    )
    assert V4_PROMPT_VERSION in brief
    for requirement in [
        "durable mental model", "Knowledge and evidence contract",
        "Foundation:", "Advanced:", "Required lesson sequence",
        "three cognitive question types", "targeted feedback",
    ]:
        assert requirement in brief


def test_dp3_fallback_differs_across_at_least_six_teaching_dimensions_but_not_facts():
    foundation_request = _request()
    advanced_request = {**_request(), "learner_profile": NORMAL_PROFILE_FIXTURES["advanced_learner"]}
    foundation = _build_verified_source_content(_base(), foundation_request, {2, 3})
    advanced = _build_verified_source_content(_base(), advanced_request, {2, 3})
    differing_dimensions = [
        foundation["concept_introduction"]["hook"] != advanced["concept_introduction"]["hook"],
        foundation["concept_introduction"]["explanation"] != advanced["concept_introduction"]["explanation"],
        len(foundation["concept_introduction"]["mechanism"]) != len(advanced["concept_introduction"]["mechanism"]),
        foundation["prerequisite_recap"]["explanation"] != advanced["prerequisite_recap"]["explanation"],
        foundation["page_walkthrough"][0]["explanation"] != advanced["page_walkthrough"][0]["explanation"],
        len(foundation["worked_example"]["steps"]) != len(advanced["worked_example"]["steps"]),
        foundation["objective_exercise"]["questions"][0]["prompt"] != advanced["objective_exercise"]["questions"][0]["prompt"],
    ]
    assert sum(differing_dimensions) >= 6
    assert foundation["concept_introduction"]["boundaries"] == advanced["concept_introduction"]["boundaries"]
    assert [q["correct_reasoning"] for q in foundation["objective_exercise"]["questions"]] == [
        q["correct_reasoning"] for q in advanced["objective_exercise"]["questions"]
    ]


def test_kq3_approved_fallback_replaces_the_previous_verified_template_questions():
    content = _build_verified_source_content(_base(), _request(), {2, 3})
    content = _with_f9_exercise_support(content, "section", "linear-separability", _request()["sources"])
    result = evaluate_objective_exercise(content["objective_exercise"])
    assert result["passed"] is True
    questions = content["objective_exercise"]["questions"]
    assert [question["question_type"] for question in questions] == [
        "mechanism", "misconception_discrimination", "application_or_boundary"
    ]
    assert all(option.get("feedback") for question in questions for option in question["options"])


def test_kq4_quality_rule_rejects_questions_without_the_new_quality_contract():
    exercise = {
        "questions": [
            {"question_id": "q1", "prompt": "Why can a straight boundary not separate the positive XOR corners from both negative corners?", "explanation": "The positive XOR inputs occupy opposite corners, so one straight line cannot isolate both from the negative corners.", "options": [{"text": "The positive corners are diagonal and require a nonlinear representation.", "correct": True}, {"text": "The inputs contain no numerical values.", "correct": False}, {"text": "A linear classifier must use exactly one feature.", "correct": False}]},
            {"question_id": "q2", "prompt": "A hidden layer maps XOR inputs into features that are linearly separable. What changed?", "explanation": "The hidden layer changes the representation, allowing a later linear output layer to separate the newly arranged features.", "options": [{"text": "The labels were removed from the task.", "correct": False}, {"text": "The representation was transformed nonlinearly before the final decision.", "correct": True}, {"text": "The model stopped using the input values.", "correct": False}]},
            {"question_id": "q3", "prompt": "When is linear separability an insufficient explanation for a classification problem?", "explanation": "It is insufficient when the chosen representation cannot be split by one linear boundary, as with XOR in its original input space.", "options": [{"text": "When classes need a nonlinear feature transformation before a linear decision.", "correct": True}, {"text": "When the dataset has only two labels.", "correct": False}, {"text": "When a boundary is drawn on a graph.", "correct": False}]},
        ]
    }
    reasons = {item["reason"] for item in evaluate_objective_exercise(exercise)["failures"]}
    assert {"invalid_question_type", "missing_assessment_target", "missing_correct_reasoning", "missing_option_feedback"} <= reasons


def test_kq4_quality_rule_rejects_missing_question_categories_even_with_three_questions():
    content = _build_verified_source_content(_base(), _request(), {2, 3})
    content = _with_f9_exercise_support(content, "section", "linear-separability", _request()["sources"])
    content["objective_exercise"]["questions"][2]["question_type"] = "mechanism"
    reasons = {item["reason"] for item in evaluate_objective_exercise(content["objective_exercise"])["failures"]}
    assert "missing_required_question_categories" in reasons
