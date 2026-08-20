"""Curate page-level CS224N evidence for the RAG candidate chain."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from experience_source_store import ExperienceSourceStore

ROOT=Path(__file__).resolve().parent; KG_ROOT=ROOT.parent/'KG_construction'
PDF_PATH=KG_ROOT/'web_data'/'runs'/'cs224n-2026-lecture10-rag-agents'/'2e97edb678d2'/'cs224n-2026-lecture10-rag-agents.pdf'
STORE_PATH=ROOT/'pathly_experience_sources.db'; SOURCE_ID='source:rag:cs224n-2026-rag-agents'; RESOURCE_ID='2e97edb678d244fb493e5f9d1ef113151f3096a72896020a94d29e1e62bde31f'; DOCUMENT_ID=RESOURCE_ID; SOURCE_VERSION='rag-source-v1'
PAGES={13:'retrieval_augmentation',15:'retriever_reader_protocol',17:'retrieval_method_boundary',21:'generation_with_retrieved_passages'}

def seed(*,ingest_chroma=False):
 import pdfplumber
 with pdfplumber.open(PDF_PATH) as pdf:
  pages=[{'chunk_id':f'rag-agents-p{p}','page_number':p,'content_role':role,'text':' '.join((pdf.pages[p-1].extract_text() or '').split())} for p,role in PAGES.items()]
 if any(len(p['text'].split())<12 for p in pages): raise ValueError('insufficient extracted text in selected RAG evidence page')
 source={'source_id':SOURCE_ID,'goal_id':'rag','canonical_concept_id':'experience:retrieval-augmented-generation','resource_id':RESOURCE_ID,'document_id':DOCUMENT_ID,'document_title':'CS224N Lecture 10: RAG and Language Agents','source_url':'https://web.stanford.edu/class/cs224n/slides_w26/cs224n-2026-lecture10-rag-agents.pdf','license_status':'public_course_material; redistribution_terms_not_asserted','review_status':'approved','source_version':SOURCE_VERSION}
 stored=ExperienceSourceStore(STORE_PATH).upsert(source,pages); inserted=0
 if ingest_chroma:
  sys.path.insert(0,str(KG_ROOT)); from infra.rag_repository import RAGRepository
  rows=[{'id':x['chunk_id'],'text':x['text'],'doc_name':source['document_title'],'chunk_id':x['page_number'],'doc_type':'slides','resource_id':RESOURCE_ID,'resource_filename':PDF_PATH.name,'document_id':DOCUMENT_ID,'page_number':x['page_number'],'content_role':x['content_role'],'source_version':SOURCE_VERSION,'review_status':'approved','concept_id':source['canonical_concept_id'],'concept_name':'Retrieval-Augmented Generation','topic_id':'Retrieval-Augmented Generation (RAG)','topic_name':'Retrieval-Augmented Generation (RAG)','word_count':len(x['text'].split())} for x in pages]
  inserted=RAGRepository(collection_name='kg_chunks',force_device='cpu').upsert_chunks(rows)
 return {'source_id':stored['source_id'],'pages':[x['page_number'] for x in stored['pages']],'chroma_inserted':inserted,'source_version':SOURCE_VERSION}
def main():
 p=argparse.ArgumentParser();p.add_argument('--ingest-chroma',action='store_true');print(json.dumps(seed(ingest_chroma=p.parse_args().ingest_chroma),ensure_ascii=False))
if __name__=='__main__':main()
