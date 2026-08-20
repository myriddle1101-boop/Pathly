from pathly_server import KG_DIR
from verified_golden_sources import (
    GOLDEN_PATH,
    GOLDEN_PATH_VERSION,
    VerifiedGoldenSourceRegistry,
    verified_canonical_concept_name,
    verified_goal_concepts_for_goal,
)


def test_real_golden_path_has_five_pdf_verified_continuous_sources():
    audit = VerifiedGoldenSourceRegistry(KG_DIR).audit()
    assert [item["concept_name"] for item in audit] == GOLDEN_PATH
    assert all(item["status"] == "verified" for item in audit)
    assert [item["source"]["golden_path_position"] for item in audit] == [1, 2, 3, 4, 5]
    assert all(item["source"]["golden_path_version"] == GOLDEN_PATH_VERSION for item in audit)
    expected_pages = {
        "Linear Separability": [2, 3],
        "XOR": [2, 3, 4, 5, 6, 7],
        "Neural Networks": [13, 14],
        "Activation Functions": [15, 16, 17],
        "Gradient Descent": [18, 19, 20],
    }
    for item in audit:
        assert [page["page_number"] for page in item["source"]["page_sequence"]] == expected_pages[item["concept_name"]]


def test_registry_refuses_unverified_or_unrelated_topics():
    registry = VerifiedGoldenSourceRegistry(KG_DIR)
    assert registry.resolve(concept_id="cooking", concept_name="Bread Baking") is None
    assert registry.resolve(concept_id="ai-applications", concept_name="AI Applications") is None

def test_verified_registry_supports_normal_goal_flow_without_creating_a_plan():
    registry = VerifiedGoldenSourceRegistry(KG_DIR)
    assert registry.matches_goal("I want to understand neural networks and gradient descent")
    assert registry.matches_goal("Why XOR is not linearly separable")
    assert not registry.matches_goal("I want to study French poetry")
    coverage = registry.coverage_for_concepts(
        ["Linear Separability", "XOR", "Neural Networks", "Activation Functions", "Gradient Descent"]
    )
    assert coverage["covered_count"] == 5
    assert coverage["total_count"] == 5


def test_verified_goal_terms_expand_only_source_grounded_goal_variants():
    assert verified_goal_concepts_for_goal(
        "I want to understand why XOR is not linearly separable and learn how neural networks solve it"
    ) == GOLDEN_PATH
    assert verified_goal_concepts_for_goal(
        "Learn neural networks with activation functions and gradient descent"
    ) == GOLDEN_PATH
    assert verified_goal_concepts_for_goal("Learn neural networks") == []
    assert verified_canonical_concept_name("xor") == "XOR"
    assert verified_canonical_concept_name("Why XOR is not linearly separable") == "Linear Separability"
    assert verified_canonical_concept_name("neural net") == "Neural Networks"
    assert verified_canonical_concept_name("ReLU") == "Activation Functions"
    assert verified_canonical_concept_name("SGD") == "Gradient Descent"


def test_verified_registry_resolves_common_aliases_to_reusable_sources():
    registry = VerifiedGoldenSourceRegistry(KG_DIR)
    assert registry.resolve(concept_id="neural-net", concept_name="neural net")["review_status"] == "verified"
    assert registry.resolve(concept_id="sgd", concept_name="SGD")["review_status"] == "verified"
