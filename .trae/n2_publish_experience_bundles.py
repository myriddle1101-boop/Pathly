"""Publish the three new goal-scoped asset bundles without touching golden v4."""
from __future__ import annotations
import json
from pathlib import Path
from goal_chain_catalog import GOAL_CHAINS
from n2_seed_word_embeddings_chain import asset_specs as word_assets
from n2_seed_self_attention_chain import assets as attention_assets
from n2_seed_rag_chain import assets as rag_assets
from teaching_asset_store import TeachingAssetStore

ROOT=Path(__file__).resolve().parent
BUILDERS={"word_embeddings":word_assets,"self_attention":attention_assets,"rag":rag_assets}
def publish():
    store=TeachingAssetStore(); results=[]
    for goal_id,builder in BUILDERS.items():
        ids=[item['asset_id'] for item in builder()]
        results.append(store.publish_scoped_bundle(scope_id=GOAL_CHAINS[goal_id]['asset_scope'],manifest_version=f"{goal_id}-assets-v1",asset_ids=ids))
    return {'goal_catalog_version':'full-experience-goal-catalog-v1','bundles':results,'legacy_global_manifest':store.current_manifest()}
def main():
    result=publish(); output=ROOT/'artifacts'/'n2_goal_scoped_asset_manifests.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
