from n2_seed_word_embeddings_chain import NODES, asset_specs, seed_assets
from teaching_asset_store import TeachingAssetStore


def test_word_embeddings_bundle_has_tiered_evidence_backed_assets(tmp_path):
    store = TeachingAssetStore(tmp_path / "assets.db")
    result = seed_assets(store)
    assert result["asset_count"] == len(NODES) * 3
    for node in NODES:
        foundation = store.list_assets(concept_id=node["id"], learner_tier="foundation", published_only=False)
        advanced = store.list_assets(concept_id=node["id"], learner_tier="advanced", published_only=False)
        assert foundation and advanced
        assert all(asset["evidence_refs"] for asset in foundation + advanced)
    assert all(asset["review_status"] == "approved" for asset in asset_specs())
