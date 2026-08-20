from golden_teaching_semantics import (
    GOLDEN_TEACHING_PROFILES,
    KQ1_SEMANTICS_VERSION,
    teaching_profile,
    validate_profiles,
)
from verified_golden_sources import GOLDEN_PATH


def test_kq1_profiles_are_complete_and_follow_the_canonical_five_node_chain():
    assert validate_profiles() == []
    assert list(GOLDEN_TEACHING_PROFILES) == GOLDEN_PATH
    for index, concept in enumerate(GOLDEN_PATH):
        profile = teaching_profile(concept)
        assert profile["semantics_version"] == KQ1_SEMANTICS_VERSION
        assert len(profile["claims"]) >= 5
        assert len(profile["misconceptions"]) >= 2
        assert {item["kind"] for item in profile["assessment_targets"]} == {
            "mechanism", "misconception_discrimination", "application_or_boundary"
        }
        assert profile["prerequisites"] == ([] if index == 0 else [GOLDEN_PATH[index - 1]])


def test_kq1_claims_are_evidence_bounded_and_not_generic_templates():
    for concept in GOLDEN_PATH:
        profile = teaching_profile(concept)
        assert all(claim["source_pages"] for claim in profile["claims"])
        assert all("input, operation, and output" not in claim["text"].lower() for claim in profile["claims"])
