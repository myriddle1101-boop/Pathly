from copy import deepcopy

from pathly_server import _v4_scenario_fingerprint
from source_grounded_v4_generator import _profile_treatment


def _plan():
    return {
        "goal_text": "I want to understand neural networks and gradient descent",
        "concept_path": [
            {"concept_id": "linear-separability", "name": "Linear Separability"},
            {"concept_id": "xor", "name": "XOR"},
            {"concept_id": "neural-networks", "name": "Neural Networks"},
        ],
        "profile_snapshot": {
            "learning_style": "hands_on",
            "preferred_examples": ["code"],
            "pace_preference": "steady",
            "interest_tags": ["machine_learning"],
            "mathematical_ability": 3,
            "programming_ability": 3,
            "confidence_baseline": 4,
        },
    }


def test_identical_normal_flow_inputs_share_the_same_v4_fingerprint():
    plan = _plan()
    assert _v4_scenario_fingerprint(plan) == _v4_scenario_fingerprint(deepcopy(plan))


def test_profile_changes_separate_verified_content_cache_inputs():
    confident_hands_on = _plan()
    lower_confidence_theory = deepcopy(confident_hands_on)
    lower_confidence_theory["profile_snapshot"].update(
        {
            "learning_style": "theory",
            "preferred_examples": ["research"],
        }
    )
    lower_confidence_theory["path_context"] = {"current_affective_state": {"confidence": 1, "anxiety": 4}}
    assert _v4_scenario_fingerprint(confident_hands_on) != _v4_scenario_fingerprint(
        lower_confidence_theory
    )


def test_interest_tags_are_part_of_content_cache_identity():
    first = _plan()
    second = deepcopy(first)
    second["profile_snapshot"]["interest_tags"] = ["healthcare"]
    assert _v4_scenario_fingerprint(first) != _v4_scenario_fingerprint(second)


def test_profile_version_and_all_teaching_dimensions_are_cache_inputs():
    base = _plan()
    base["profile_snapshot"] = {
        "profile_version": 2,
        "cognitive_traits": {
            "mathematical_ability": 3, "programming_ability": 3,
            "abstract_thinking": 3, "logical_reasoning": 3,
        },
        "affective_defaults": {
            "learning_style": "mixed",
            "preferred_examples": ["code"], "interest_tags": ["education"],
            "pace_preference": "steady",
        },
    }
    for container, key, value in [
        ("profile", "profile_version", 3),
        ("cognitive", "mathematical_ability", 1),
        ("cognitive", "programming_ability", 1),
        ("cognitive", "abstract_thinking", 1),
        ("cognitive", "logical_reasoning", 1),
        ("affective", "learning_style", "theory"),
        ("affective", "preferred_examples", ["research"]),
        ("affective", "interest_tags", ["finance"]),
        ("affective", "pace_preference", "flexible"),
    ]:
        changed = deepcopy(base)
        target = changed["profile_snapshot"] if container == "profile" else changed["profile_snapshot"][f"{container}_traits" if container == "cognitive" else "affective_defaults"]
        target[key] = value
        assert _v4_scenario_fingerprint(base) != _v4_scenario_fingerprint(changed), key

    contextual = deepcopy(base)
    contextual["path_context"] = {"current_affective_state": {"confidence": 1, "anxiety": 5}}
    assert _v4_scenario_fingerprint(base) != _v4_scenario_fingerprint(contextual)


def test_verified_v4_profile_treatment_changes_scaffolding_not_facts():
    low = _profile_treatment({
        "cognitive_traits": {"mathematical_ability": 1, "programming_ability": 1, "abstract_thinking": 1, "logical_reasoning": 1},
        "affective_defaults": {"confidence_baseline": 1, "learning_style": "example", "preferred_examples": ["code"], "interest_tags": ["healthcare"], "pace_preference": "flexible"},
    })
    high = _profile_treatment({
        "cognitive_traits": {"mathematical_ability": 5, "programming_ability": 5, "abstract_thinking": 5, "logical_reasoning": 5},
        "affective_defaults": {"confidence_baseline": 5, "learning_style": "theory", "preferred_examples": ["research"], "interest_tags": ["finance"], "pace_preference": "intensive"},
    })
    assert low["recap_depth"] == "expanded"
    assert low["formula_support"] == "step_by_step"
    assert low["code_scaffold"] == "complete_starter"
    assert low["explanation_order"] == "concrete_first"
    assert low["checkpoint_density"] == "high"
    assert low["segment_size"] == "short"
    assert low["example_context"] == "a medical screening decision"
    assert high["example_context"] == "a credit-risk decision"


def test_product_api_does_not_expose_a_prebuilt_good_case_plan():
    import pathly_server

    routes = {route.path for route in pathly_server.app.routes}
    assert "/api/golden-cases/g0" not in routes
    assert "/api/golden-cases/g0/status" not in routes
