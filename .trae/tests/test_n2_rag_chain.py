from n2_seed_rag_chain import NODES,assets,seed_assets
from teaching_asset_store import TeachingAssetStore
def test_rag_assets_are_tiered_and_evidence_linked(tmp_path):
 s=TeachingAssetStore(tmp_path/'assets.db');r=seed_assets(s)
 assert r['asset_count']==len(NODES)*3
 assert all(a['evidence_refs'] for a in assets())
 assert all(s.list_assets(concept_id=n['id'],learner_tier='advanced',published_only=False) for n in NODES)
