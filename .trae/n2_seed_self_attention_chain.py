"""Seed the reviewed Self-Attention chain and non-published tiered assets."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from n2_seed_self_attention_source import DOCUMENT_ID, SOURCE_VERSION
from teaching_asset_store import TeachingAssetStore

ROOT = Path(__file__).resolve().parent
KG_ROOT = ROOT.parent / "KG_construction"
KNOWLEDGE_VERSION = "self-attention-chain-v1"
NODES = [
    {"id": "experience:token-representations", "name": "Token Representations", "page": 40, "definition": "A token representation is a vector that carries the current features of one token in a sequence.", "mechanism": "Attention starts from one representation per token and transforms those representations according to information selected from the sequence.", "boundary": "A token vector alone does not determine how much another token should influence it."},
    {"id": "experience:query-key-value", "name": "Queries, Keys, and Values", "page": 42, "definition": "Queries, keys, and values are learned projections used to decide what each token should retrieve and what information is returned.", "mechanism": "A query is compared with keys to form weights, then those weights combine the corresponding values.", "boundary": "Queries, keys, and values are roles created from representations; they are not three separate input sentences."},
    {"id": "experience:self-attention", "name": "Self-Attention", "page": 42, "definition": "Self-attention lets each token form a context-dependent representation by weighting values from tokens in the same sequence.", "mechanism": "For a token, query-key scores are normalized across the sequence and used as a weighted average over value vectors.", "boundary": "Self-attention has no inherent sequence order, so position information must be supplied separately."},
    {"id": "experience:contextual-representations", "name": "Contextual Representations", "page": 56, "definition": "A contextual representation is a token vector updated using information from relevant positions in its sequence.", "mechanism": "Matrix-form attention computes all query-key comparisons, normalizes each query's weights, and applies them to values in parallel.", "boundary": "A contextual vector reflects the available tokens and masking rules; it is not unrestricted access to every future token."},
]

def ref(page): return {"document_id": DOCUMENT_ID, "page_number": page, "chunk_id": f"sa-transformers-p{page}"}

def assets():
    output=[]
    for node in NODES:
        slug=node['id'].split(':',1)[1]; target=f"target:{slug}:mechanism"; misconception=f"misconception:{slug}:role"
        output += [
            {"asset_id":f"sa-{slug}-foundation-intuition","canonical_concept_id":node['id'],"asset_type":"foundation_intuition","learner_tier":"foundation","content":{"title":node['name'],"explanation":node['definition'],"bridge":node['mechanism'],"check":node['boundary']},"assessment_targets":[target],"misconception_ids":[misconception],"knowledge_version":KNOWLEDGE_VERSION,"review_status":"approved","evidence_refs":[ref(node['page'])]},
            {"asset_id":f"sa-{slug}-visual","canonical_concept_id":node['id'],"asset_type":"visual_or_coordinate_description","learner_tier":"shared","content":{"title":f"Trace {node['name']}","description":"Draw the current token, the positions it can use, the weighting operation, and the resulting updated vector.","boundary":node['boundary']},"assessment_targets":[target],"misconception_ids":[misconception],"knowledge_version":KNOWLEDGE_VERSION,"review_status":"approved","evidence_refs":[ref(node['page'])]},
            {"asset_id":f"sa-{slug}-advanced-worked","canonical_concept_id":node['id'],"asset_type":"advanced_worked_example","learner_tier":"advanced","content":{"title":f"Mechanism check: {node['name']}","problem":f"State the representation, learned transformation, weighting step, and limitation in {node['name']}.","steps":[node['definition'],node['mechanism'],node['boundary']],"transfer":"Alter masking or position information and state which contextual dependency changes."},"assessment_targets":[target],"misconception_ids":[misconception],"knowledge_version":KNOWLEDGE_VERSION,"review_status":"approved","evidence_refs":[ref(node['page'])]}
        ]
    return output

def seed_assets(store=None):
    store=store or TeachingAssetStore(); specs=assets()
    for asset in specs: store.upsert(asset)
    return {"knowledge_version":KNOWLEDGE_VERSION,"asset_count":len(specs),"published":False}

def seed_neo4j():
    sys.path.insert(0,str(KG_ROOT)); from env_loader import load_project_env; load_project_env(); from neo4j import GraphDatabase
    driver=GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'),auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD','')))
    try:
      with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as s:
       for n in NODES:
        page_id=f"{DOCUMENT_ID}:page:{n['page']}"; chunk=f"sa-transformers-p{n['page']}"; slug=n['id'].split(':',1)[1]
        s.run("MERGE (c:CanonicalConcept {id:$id}) SET c.name=$name,c.review_status='approved',c.knowledge_version=$v,c.source_version=$sv,c.scope='full_experience_candidate' MERGE (p:Page {id:$pid}) SET p.document_id=$d,p.page_number=$page,p.review_status='approved' MERGE (r:ChunkRef {id:$chunk}) SET r.document_id=$d,r.page_number=$page,r.chroma_id=$chunk,r.content_role='teaching_evidence',r.source_version=$sv,r.review_status='approved' MERGE (p)-[:HAS_CHUNK]->(r) MERGE (c)-[:SUPPORTED_BY]->(p)",id=n['id'],name=n['name'],v=KNOWLEDGE_VERSION,sv=SOURCE_VERSION,pid=page_id,d=DOCUMENT_ID,page=n['page'],chunk=chunk)
        for kind in ('definition','mechanism','boundary'):
         s.run("MERGE (claim:TeachingClaim {id:$cid}) SET claim.claim_type=$kind,claim.text=$text,claim.review_status='approved',claim.knowledge_version=$v WITH claim MATCH (c:CanonicalConcept {id:$id}) MATCH (p:Page {id:$pid}) MERGE (c)-[:HAS_TEACHING_CLAIM]->(claim) MERGE (claim)-[:SUPPORTED_BY]->(p)",cid=f"claim:{slug}:{kind}",kind=kind,text=n[kind],v=KNOWLEDGE_VERSION,id=n['id'],pid=page_id)
        s.run("MERGE (m:Misconception {id:$mid}) SET m.text=$text,m.review_status='approved' WITH m MATCH (c:CanonicalConcept {id:$id}) MERGE (c)-[:HAS_MISCONCEPTION]->(m) MERGE (t:AssessmentTarget {id:$tid}) SET t.text=$target,t.review_status='approved' WITH t MATCH (c:CanonicalConcept {id:$id}) MERGE (t)-[:ASSESSES]->(c)",mid=f"misconception:{slug}:role",text=f"A learner treats {n['name']} as a label rather than tracing its input, operation, and boundary.",id=n['id'],tid=f"target:{slug}:mechanism",target=f"Explain the mechanism and boundary of {n['name']}.")
       for a,b in zip(NODES,NODES[1:]): s.run("MATCH (a:CanonicalConcept {id:$a}) MATCH (b:CanonicalConcept {id:$b}) MERGE (a)-[:PREREQUISITE_OF {knowledge_version:$v}]->(b)",a=a['id'],b=b['id'],v=KNOWLEDGE_VERSION)
    finally: driver.close()
    return {"canonical_nodes":len(NODES),"relationships":len(NODES)-1,"knowledge_version":KNOWLEDGE_VERSION}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'artifacts'/'n2_self_attention_chain_seed.json');args=parser.parse_args(); result={"assets":seed_assets(),"neo4j":seed_neo4j()}; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__': main()
