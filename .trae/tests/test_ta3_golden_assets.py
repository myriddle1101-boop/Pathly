from ta3_seed_golden_assets import NODES, seed
from teaching_asset_store import TeachingAssetStore


def test_golden_asset_bundle_covers_both_tiers(tmp_path, monkeypatch):
    monkeypatch.setenv("PATHLY_TEACHING_ASSET_DB", str(tmp_path / "assets.db"))
    result = seed()
    assert result["asset_count"] == 45
    store = TeachingAssetStore(tmp_path / "assets.db")
    assert store.current_manifest()["manifest_version"] == "ta-golden-v2"
    for slug in NODES:
        foundation = store.list_assets(concept_id=f"golden:{slug}", learner_tier="foundation")
        advanced = store.list_assets(concept_id=f"golden:{slug}", learner_tier="advanced")
        assert {item["asset_type"] for item in foundation} >= {"foundation_intuition", "foundation_worked_example", "visual_or_coordinate_description"}
        assert {item["asset_type"] for item in advanced} >= {"advanced_derivation", "advanced_worked_example", "transfer_challenge", "visual_or_coordinate_description"}
        assert {item["asset_type"] for item in foundation + advanced} >= {"formula_explanation", "code_exercise", "contextual_example_variant"}
        assert all(item["evidence_refs"] for item in foundation + advanced)
