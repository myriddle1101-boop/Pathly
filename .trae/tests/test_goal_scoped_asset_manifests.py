from teaching_asset_store import TeachingAssetStore

def _asset(asset_id):
 return {'asset_id':asset_id,'canonical_concept_id':'c','asset_type':'foundation_intuition','learner_tier':'foundation','content':{'x':'y'},'knowledge_version':'v','review_status':'approved','evidence_refs':[{'document_id':'d','page_number':1,'chunk_id':'p1'}]}

def test_scoped_publication_does_not_supersede_another_scope(tmp_path):
 store=TeachingAssetStore(tmp_path/'assets.db');store.upsert(_asset('a'));store.upsert(_asset('b'))
 store.publish_scoped_bundle(scope_id='goal:a',manifest_version='a-v1',asset_ids=['a'])
 store.publish_scoped_bundle(scope_id='goal:b',manifest_version='b-v1',asset_ids=['b'])
 assert store.current_scoped_manifest('goal:a')['asset_ids']==['a']
 assert store.current_scoped_manifest('goal:b')['asset_ids']==['b']
