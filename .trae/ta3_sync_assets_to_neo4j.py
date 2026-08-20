"""Index published Teaching Assets in Neo4j without storing their full prose."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KG_DIR = ROOT.parent / "KG_construction"


def sync() -> dict[str, int | str]:
    sys.path.insert(0, str(KG_DIR))
    from env_loader import load_project_env
    load_project_env()
    from neo4j import GraphDatabase
    from golden_teaching_semantics import GOLDEN_TEACHING_PROFILES
    from teaching_asset_store import TeachingAssetStore

    store = TeachingAssetStore()
    manifest = store.current_manifest() or {}
    assets = [store.get(asset_id) for asset_id in manifest.get("asset_ids") or []]
    assets = [asset for asset in assets if asset]
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
    )
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            for asset in assets:
                session.run(
                    """
                    MERGE (a:TeachingAsset {id:$id})
                    SET a.asset_type=$asset_type, a.learner_tier=$tier,
                        a.knowledge_version=$knowledge_version,
                        a.manifest_version=$manifest_version,
                        a.review_status='published', a.store_ref=$store_ref
                    WITH a
                    MATCH (c:CanonicalConcept {id:$concept_id})
                    MERGE (c)-[:HAS_TEACHING_ASSET {manifest_version:$manifest_version}]->(a)
                    """,
                    id=asset["asset_id"], asset_type=asset["asset_type"], tier=asset["learner_tier"],
                    knowledge_version=asset["knowledge_version"], manifest_version=manifest["manifest_version"],
                    store_ref=asset["asset_id"], concept_id=asset["canonical_concept_id"],
                )
                for ref in asset["evidence_refs"]:
                    page_id = f"{ref['document_id']}:page:{int(ref['page_number'])}"
                    session.run(
                        """
                        MATCH (a:TeachingAsset {id:$asset_id})
                        MERGE (p:Page {id:$page_id})
                        SET p.document_id=$document_id, p.page_number=$page_number, p.review_status='approved'
                        MERGE (a)-[:SUPPORTED_BY {manifest_version:$manifest_version, chunk_id:$chunk_id}]->(p)
                        """,
                        asset_id=asset["asset_id"], page_id=page_id, document_id=ref["document_id"],
                        page_number=int(ref["page_number"]), manifest_version=manifest["manifest_version"],
                        # Neo4j rejects null relationship properties; some curated
                        # page-level evidence intentionally has no Chroma chunk.
                        chunk_id=ref.get("chunk_id") or "",
                    )
                for target_id in asset.get("assessment_targets") or []:
                    session.run(
                        """
                        MATCH (a:TeachingAsset {id:$asset_id})
                        MATCH (t:AssessmentTarget {id:$target_id})
                        MERGE (a)-[:ASSESSES]->(t)
                        """,
                        asset_id=asset["asset_id"], target_id=target_id,
                    )
    finally:
        driver.close()
    return {"manifest_version": manifest.get("manifest_version", ""), "assets": len(assets)}


if __name__ == "__main__":
    print(sync())
