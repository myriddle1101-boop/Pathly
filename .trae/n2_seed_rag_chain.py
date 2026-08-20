"""Seed the reviewed RAG chain and non-published tiered assets."""
from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
from n2_seed_rag_source import DOCUMENT_ID,SOURCE_VERSION
from teaching_asset_store import TeachingAssetStore
ROOT=Path(__file__).resolve().parent; KG_ROOT=ROOT.parent/'KG_construction'; KNOWLEDGE_VERSION='rag-chain-v1'
NODES=[
 {'id':'experience:document-collection','name':'Document Collection and Chunks','page':13,'definition':'A document collection is the external corpus from which a retrieval system can select relevant passages.','mechanism':'Retrieval augmentation makes external content available just in time instead of requiring a language model to store every fact in parameters.','boundary':'A collection is only useful when its documents are indexed and the needed evidence is actually retrievable.'},
 {'id':'experience:retrieval','name':'Retrieval','page':15,'definition':'Retrieval ranks or selects passages from a document collection for a query.','mechanism':'A retriever maps a query and candidate passages to a relevance signal, then returns a limited set of passages to the answer component.','boundary':'Retrieval quality is a bottleneck: generation cannot reliably recover evidence that was never selected.'},
 {'id':'experience:retrieved-evidence','name':'Retrieved Evidence','page':17,'definition':'Retrieved evidence is the bounded set of passages selected as context for answering a query.','mechanism':'Sparse, vector, or neural retrievers choose passages using a relevance method before the generator sees them.','boundary':'More passages do not automatically improve an answer; irrelevant context can exceed attention or context capacity.'},
 {'id':'experience:retrieval-augmented-generation','name':'Retrieval-Augmented Generation','page':21,'definition':'Retrieval-augmented generation answers a query by combining a generator with evidence retrieved from an external corpus.','mechanism':'The system retrieves passages relevant to the query and conditions answer generation on those passages rather than using only parametric memory.','boundary':'RAG can provide traceable evidence, but a citation or fluent answer still needs verification against the retrieved text.'},]
def ref(p):return {'document_id':DOCUMENT_ID,'page_number':p,'chunk_id':f'rag-agents-p{p}'}
def assets():
 o=[]
 for n in NODES:
  slug=n['id'].split(':',1)[1];t=f'target:{slug}:mechanism';m=f'misconception:{slug}:role'
  o += [
   {'asset_id':f'rag-{slug}-foundation-intuition','canonical_concept_id':n['id'],'asset_type':'foundation_intuition','learner_tier':'foundation','content':{'title':n['name'],'explanation':n['definition'],'bridge':n['mechanism'],'check':n['boundary']},'assessment_targets':[t],'misconception_ids':[m],'knowledge_version':KNOWLEDGE_VERSION,'review_status':'approved','evidence_refs':[ref(n['page'])]},
   {'asset_id':f'rag-{slug}-visual','canonical_concept_id':n['id'],'asset_type':'visual_or_coordinate_description','learner_tier':'shared','content':{'title':f'Trace {n["name"]}','description':'Draw the query, corpus, selected passages, and answer. Mark which component chooses evidence and which component writes the answer.','boundary':n['boundary']},'assessment_targets':[t],'misconception_ids':[m],'knowledge_version':KNOWLEDGE_VERSION,'review_status':'approved','evidence_refs':[ref(n['page'])]},
   {'asset_id':f'rag-{slug}-advanced-worked','canonical_concept_id':n['id'],'asset_type':'advanced_worked_example','learner_tier':'advanced','content':{'title':f'Mechanism check: {n["name"]}','problem':f'Trace a query through {n["name"]}, naming the selected evidence, the generation condition, and the failure boundary.','steps':[n['definition'],n['mechanism'],n['boundary']],'transfer':'Change retrieval recall or context size and identify which evidence-grounding guarantee weakens.'},'assessment_targets':[t],'misconception_ids':[m],'knowledge_version':KNOWLEDGE_VERSION,'review_status':'approved','evidence_refs':[ref(n['page'])]}]
 return o
def seed_assets(store=None):
 store=store or TeachingAssetStore(); specs=assets()
 for a in specs:store.upsert(a)
 return {'knowledge_version':KNOWLEDGE_VERSION,'asset_count':len(specs),'published':False}
def seed_neo4j():
 sys.path.insert(0,str(KG_ROOT));from env_loader import load_project_env;load_project_env();from neo4j import GraphDatabase
 d=GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'),auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD','')))
 try:
  with d.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as s:
   for n in NODES:
    pid=f"{DOCUMENT_ID}:page:{n['page']}";chunk=f"rag-agents-p{n['page']}";slug=n['id'].split(':',1)[1]
    s.run("MERGE (c:CanonicalConcept {id:$id}) SET c.name=$name,c.review_status='approved',c.knowledge_version=$v,c.source_version=$sv,c.scope='full_experience_candidate' MERGE (p:Page {id:$pid}) SET p.document_id=$d,p.page_number=$page,p.review_status='approved' MERGE (r:ChunkRef {id:$chunk}) SET r.document_id=$d,r.page_number=$page,r.chroma_id=$chunk,r.content_role='teaching_evidence',r.source_version=$sv,r.review_status='approved' MERGE (p)-[:HAS_CHUNK]->(r) MERGE (c)-[:SUPPORTED_BY]->(p)",id=n['id'],name=n['name'],v=KNOWLEDGE_VERSION,sv=SOURCE_VERSION,pid=pid,d=DOCUMENT_ID,page=n['page'],chunk=chunk)
    for k in ('definition','mechanism','boundary'):s.run("MERGE (claim:TeachingClaim {id:$cid}) SET claim.claim_type=$k,claim.text=$text,claim.review_status='approved',claim.knowledge_version=$v WITH claim MATCH (c:CanonicalConcept {id:$id}) MATCH (p:Page {id:$pid}) MERGE (c)-[:HAS_TEACHING_CLAIM]->(claim) MERGE (claim)-[:SUPPORTED_BY]->(p)",cid=f'claim:{slug}:{k}',k=k,text=n[k],v=KNOWLEDGE_VERSION,id=n['id'],pid=pid)
    s.run("MERGE (m:Misconception {id:$mid}) SET m.text=$text,m.review_status='approved' WITH m MATCH (c:CanonicalConcept {id:$id}) MERGE (c)-[:HAS_MISCONCEPTION]->(m) MERGE (t:AssessmentTarget {id:$tid}) SET t.text=$target,t.review_status='approved' WITH t MATCH (c:CanonicalConcept {id:$id}) MERGE (t)-[:ASSESSES]->(c)",mid=f'misconception:{slug}:role',text=f'A learner assumes {n["name"]} is just a label and does not trace evidence selection or the stated boundary.',id=n['id'],tid=f'target:{slug}:mechanism',target=f'Explain the mechanism and boundary of {n["name"]}.')
   for a,b in zip(NODES,NODES[1:]):s.run("MATCH (a:CanonicalConcept {id:$a}) MATCH (b:CanonicalConcept {id:$b}) MERGE (a)-[:PREREQUISITE_OF {knowledge_version:$v}]->(b)",a=a['id'],b=b['id'],v=KNOWLEDGE_VERSION)
 finally:d.close()
 return {'canonical_nodes':len(NODES),'relationships':len(NODES)-1,'knowledge_version':KNOWLEDGE_VERSION}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'artifacts'/'n2_rag_chain_seed.json');a=p.parse_args();r={'assets':seed_assets(),'neo4j':seed_neo4j()};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':main()
