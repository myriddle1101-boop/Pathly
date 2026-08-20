from pathlib import Path

from experience_goal_source_resolver import ExperienceGoalSourceResolver


def test_self_attention_gold_manifest_has_two_tiers_and_assets():
    manifest = Path(r"D:\ic\master project\gold source\self_attention\gold-source-manifest.json")
    assert manifest.exists()
    text = manifest.read_text(encoding="utf-8")
    assert "gold-foundation-v1" in text
    assert "gold-advanced-v1" in text
    assert text.count('"asset_id"') == 16


def test_self_attention_resolver_selects_tier_specific_source_pages():
    resolver = ExperienceGoalSourceResolver()
    foundation = resolver.resolve(
        concept_id="experience:query-key-value",
        concept_name="Queries, Keys, and Values",
        learner_tier="foundation",
    )
    advanced = resolver.resolve(
        concept_id="experience:query-key-value",
        concept_name="Queries, Keys, and Values",
        learner_tier="advanced",
    )
    assert foundation["learner_tier"] == "foundation"
    assert advanced["learner_tier"] == "advanced"
    assert foundation["document_id"] != advanced["document_id"]
    assert foundation["page_sequence"][0]["page_number"] == 42
    assert advanced["page_sequence"][0]["page_number"] == 4
