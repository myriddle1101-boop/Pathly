"""Seed the reviewed Word Embeddings canonical chain and non-published assets.

The bundle is deliberately not published through TeachingAssetStore's global
manifest: publishing it today would supersede the active XOR bundle.  N4 will
introduce goal-scoped manifests before any new chain is learner-visible.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from n2_seed_word_embeddings_source import DOCUMENT_ID, SOURCE_VERSION
from teaching_asset_store import TeachingAssetStore


ROOT = Path(__file__).resolve().parent
KG_ROOT = ROOT.parent / "KG_construction"
KNOWLEDGE_VERSION = "word-embeddings-chain-v1"

NODES = [
    {"id": "experience:text-representation", "name": "Text Representation", "page": 8,
     "definition": "A text representation turns a word or text span into values a computation can compare or transform.",
     "mechanism": "A representation determines what information a later similarity calculation can see; one-hot vectors preserve identity but not graded relatedness.",
     "boundary": "A representation is not meaning itself; it is a model-dependent encoding of signals useful for a task."},
    {"id": "experience:word-embeddings", "name": "Word Embeddings", "page": 10,
     "definition": "A word embedding is a dense vector assigned to a word so that words occurring in similar contexts tend to have similar vectors.",
     "mechanism": "Training adjusts vectors from corpus context so a center word scores its observed context words more highly than incompatible alternatives.",
     "boundary": "Closeness reflects patterns in the training data, not a complete or unbiased account of word meaning."},
    {"id": "experience:cosine-similarity", "name": "Cosine Similarity", "page": 17,
     "definition": "Cosine similarity compares the angle between two non-zero vectors; it is often used to rank embeddings by directional similarity.",
     "mechanism": "The normalized dot product is high when two vectors point in similar directions, so it can compare vectors without treating their raw length as the whole signal.",
     "boundary": "A high cosine score is a ranking signal, not proof that two words are interchangeable in every context."},
    {"id": "experience:semantic-similarity", "name": "Semantic Similarity", "page": 41,
     "definition": "Semantic similarity is the degree to which two expressions are related in meaning for a stated task or evaluation setting.",
     "mechanism": "Embedding distances are evaluated by asking whether their rankings correlate with human similarity judgments or help a downstream task.",
     "boundary": "Relatedness, synonymy, analogy, and contextual substitutability are different evaluation targets and should not be collapsed into one score."},
]

MISCONCEPTIONS = {
    "experience:text-representation": ("misconception:text-representation-identity", "A one-hot identity vector already encodes graded semantic similarity."),
    "experience:word-embeddings": ("misconception:embeddings-dictionary", "An embedding stores a fixed dictionary definition for a word."),
    "experience:cosine-similarity": ("misconception:cosine-synonymy", "A high cosine score proves two words are synonyms in all contexts."),
    "experience:semantic-similarity": ("misconception:similarity-objective", "One similarity score is the same as every possible notion of meaning similarity."),
}


def _ref(page: int) -> dict[str, Any]:
    return {"document_id": DOCUMENT_ID, "page_number": page, "chunk_id": f"we-wordvecs-p{page}"}


def asset_specs() -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for node in NODES:
        slug = node["id"].split(":", 1)[1]
        misconception_id, misconception = MISCONCEPTIONS[node["id"]]
        assets.extend([
            {"asset_id": f"we-{slug}-foundation-intuition", "canonical_concept_id": node["id"], "asset_type": "foundation_intuition", "learner_tier": "foundation", "knowledge_version": KNOWLEDGE_VERSION, "review_status": "approved", "assessment_targets": [f"target:{slug}:mechanism"], "misconception_ids": [misconception_id], "evidence_refs": [_ref(node["page"])], "content": {"title": node["name"], "explanation": node["definition"], "bridge": node["mechanism"], "check": f"Explain why this statement is incomplete: {misconception}"}},
            {"asset_id": f"we-{slug}-visual", "canonical_concept_id": node["id"], "asset_type": "visual_or_coordinate_description", "learner_tier": "shared", "knowledge_version": KNOWLEDGE_VERSION, "review_status": "approved", "assessment_targets": [f"target:{slug}:mechanism"], "misconception_ids": [misconception_id], "evidence_refs": [_ref(node["page"])], "content": {"title": f"A picture for {node['name']}", "description": f"Draw an input, the transformation described by {node['name']}, and the comparison or output it makes possible. Label what changes and what remains fixed.", "boundary": node["boundary"]}},
            {"asset_id": f"we-{slug}-advanced-worked", "canonical_concept_id": node["id"], "asset_type": "advanced_worked_example", "learner_tier": "advanced", "knowledge_version": KNOWLEDGE_VERSION, "review_status": "approved", "assessment_targets": [f"target:{slug}:mechanism"], "misconception_ids": [misconception_id], "evidence_refs": [_ref(node["page"])], "content": {"title": f"Mechanism check: {node['name']}", "problem": f"State the input, transformation, comparison criterion, and boundary for {node['name']}.", "steps": [node["definition"], node["mechanism"], node["boundary"]], "transfer": "Change one assumption and state which conclusion no longer follows."}},
        ])
    return assets


def seed_assets(store: TeachingAssetStore | None = None) -> dict[str, Any]:
    store = store or TeachingAssetStore()
    specs = asset_specs()
    for asset in specs:
        store.upsert(asset)
    return {"knowledge_version": KNOWLEDGE_VERSION, "asset_count": len(specs), "asset_ids": [item["asset_id"] for item in specs], "published": False}


def seed_neo4j() -> dict[str, Any]:
    sys.path.insert(0, str(KG_ROOT))
    from env_loader import load_project_env
    load_project_env()
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"), auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")))
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            for node in NODES:
                session.run("""
                    MERGE (c:CanonicalConcept {id:$id})
                    SET c.name=$name, c.review_status='approved', c.knowledge_version=$version,
                        c.source_version=$source_version, c.scope='full_experience_candidate'
                    MERGE (p:Page {id:$page_id})
                    SET p.document_id=$document_id, p.page_number=$page, p.review_status='approved'
                    MERGE (r:ChunkRef {id:$chunk_id})
                    SET r.document_id=$document_id, r.page_number=$page, r.chroma_id=$chunk_id,
                        r.content_role='teaching_evidence', r.source_version=$source_version, r.review_status='approved'
                    MERGE (p)-[:HAS_CHUNK]->(r)
                    MERGE (c)-[:SUPPORTED_BY]->(p)
                """, id=node["id"], name=node["name"], version=KNOWLEDGE_VERSION, source_version=SOURCE_VERSION, page_id=f"{DOCUMENT_ID}:page:{node['page']}", document_id=DOCUMENT_ID, page=node["page"], chunk_id=f"we-wordvecs-p{node['page']}")
                for claim_type in ("definition", "mechanism", "boundary"):
                    claim_id = f"claim:{node['id'].split(':',1)[1]}:{claim_type}"
                    session.run("""
                        MERGE (claim:TeachingClaim {id:$claim_id})
                        SET claim.claim_type=$claim_type, claim.text=$text, claim.review_status='approved', claim.knowledge_version=$version
                        WITH claim MATCH (c:CanonicalConcept {id:$concept_id}) MATCH (p:Page {id:$page_id})
                        MERGE (c)-[:HAS_TEACHING_CLAIM]->(claim)
                        MERGE (claim)-[:SUPPORTED_BY]->(p)
                    """, claim_id=claim_id, claim_type=claim_type, text=node[claim_type], version=KNOWLEDGE_VERSION, concept_id=node["id"], page_id=f"{DOCUMENT_ID}:page:{node['page']}")
                misconception_id, misconception = MISCONCEPTIONS[node["id"]]
                session.run("""
                    MERGE (m:Misconception {id:$misconception_id}) SET m.text=$misconception, m.review_status='approved'
                    WITH m MATCH (c:CanonicalConcept {id:$concept_id}) MERGE (c)-[:HAS_MISCONCEPTION]->(m)
                    MERGE (t:AssessmentTarget {id:$target_id}) SET t.text=$target, t.review_status='approved'
                    WITH t MATCH (c:CanonicalConcept {id:$concept_id}) MERGE (t)-[:ASSESSES]->(c)
                """, misconception_id=misconception_id, misconception=misconception, concept_id=node["id"], target_id=f"target:{node['id'].split(':',1)[1]}:mechanism", target=f"Explain the mechanism and boundary of {node['name']}.")
            for before, after in zip(NODES, NODES[1:]):
                session.run("MATCH (a:CanonicalConcept {id:$a}) MATCH (b:CanonicalConcept {id:$b}) MERGE (a)-[:PREREQUISITE_OF {knowledge_version:$version}]->(b)", a=before["id"], b=after["id"], version=KNOWLEDGE_VERSION)
    finally:
        driver.close()
    return {"canonical_nodes": len(NODES), "relationships": len(NODES) - 1, "knowledge_version": KNOWLEDGE_VERSION}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "n2_word_embeddings_chain_seed.json")
    args = parser.parse_args()
    result = {"assets": seed_assets(), "neo4j": seed_neo4j()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
