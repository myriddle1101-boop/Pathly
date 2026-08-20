from n2_seed_self_attention_chain import NODES, assets, seed_assets
from teaching_asset_store import TeachingAssetStore

def test_self_attention_assets_are_tiered_and_evidence_linked(tmp_path):
    store=TeachingAssetStore(tmp_path/'assets.db'); result=seed_assets(store)
    assert result['asset_count']==len(NODES)*3
    assert all(item['evidence_refs'] for item in assets())
    assert all(store.list_assets(concept_id=node['id'],learner_tier='foundation',published_only=False) for node in NODES)
