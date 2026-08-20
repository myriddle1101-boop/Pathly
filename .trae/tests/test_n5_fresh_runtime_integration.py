from pathlib import Path

from experience_goal_source_resolver import ExperienceGoalSourceResolver
from experience_run_store import ExperienceRunStore, build_experience_run
from goal_chain_catalog import GOAL_CHAINS
from pathly_goal_interpretation import GoalInterpretationService
from pathly_onboarding import OnboardingService
from source_linking_index import links_from_lecture
import pathly_server


ROOT = Path(__file__).resolve().parents[1]


GOALS = {
    "word_embeddings": "Understand how word embeddings represent semantic similarity.",
    "self_attention": "Understand how self-attention enables transformers to model context.",
    "rag": "Understand how retrieval-augmented generation uses retrieved evidence to answer a query.",
}


def test_new_goal_terms_use_approved_catalog_chain_without_fixture_profile():
    for goal_id, goal in GOALS.items():
        expected = GOAL_CHAINS[goal_id]["canonical_path"]
        assert GoalInterpretationService._goal_terms(goal) == expected
        assert OnboardingService._target_terms(goal, None) == expected


def test_runtime_resolver_preserves_scoped_source_asset_and_page_identity():
    resolver = ExperienceGoalSourceResolver(ROOT)
    for spec in GOAL_CHAINS.values():
        for concept_id, name, page in zip(spec["canonical_path"], spec["display_names"], spec["concept_pages"]):
            link = resolver.resolve(concept_id=concept_id, concept_name=name)
            assert link is not None
            assert link["review_status"] == "verified"
            assert link["asset_scope"] == spec["asset_scope"]
            assert link["asset_manifest_version"]
            assert link["page_sequence"][0]["page_number"] == page
            assert resolver.page_evidence(link)[0]["page_number"] == page

            projected = links_from_lecture(
                {"lecture_sections": [{"concept_id": concept_id, "concept_name": name}]},
                verified_source_resolver=resolver,
            )[0]
            assert projected["experience_source_id"] == link["experience_source_id"]
            assert projected["asset_concept_id"] == concept_id
            assert projected["asset_manifest_version"] == link["asset_manifest_version"]


def test_v4_seed_uses_full_catalog_chain_for_normal_browser_goal():
    spec = GOAL_CHAINS["self_attention"]
    plan_record = {
        "plan_id": "plan-self-attention", "path_id": "path-self-attention",
        "goal_text": GOALS["self_attention"],
        "plan": {"goal_text": GOALS["self_attention"], "concept_path": []},
    }
    seed = pathly_server._v4_seed_lecture_from_daily(
        {"scheduled_minutes": 60, "study_blocks": []}, plan_record, 1
    )
    assert [item["concept_ids"][0] for item in seed["lecture_sections"]] == spec["canonical_path"]
    assert [item["concept_name"] for item in seed["lecture_sections"]] == spec["display_names"]
    assert seed["generation_metadata"]["verified_source_policy"] == "approved-goal-catalog-v1"


def test_scoped_source_metadata_survives_sqlite_index(tmp_path):
    from source_linking_index import ConceptSourceLinkIndex

    index = ConceptSourceLinkIndex(tmp_path / "links.db")
    link = {
        "link_id": "experience:rag:retrieval",
        "concept_id": "experience:retrieval",
        "concept_name": "Retrieval",
        "resource_id": "resource-rag",
        "document_id": "document-rag",
        "document_title": "RAG source",
        "page_sequence": [{"page_number": 15, "role": "retrieval", "chunk_ids": ["rag-p15"]}],
        "chunk_ids": ["rag-p15"],
        "source_scope": "public",
        "relevance_score": 1.0,
        "coverage_score": 1.0,
        "match_method": "approved_goal_chain_catalog",
        "review_status": "verified",
        "match_reason": "approved",
        "source_readiness": "approved_experience_source",
        "link_role": "primary",
        "canonical_concept_id": "experience:retrieval",
        "experience_source_id": "source:rag",
        "asset_concept_id": "experience:retrieval",
        "asset_scope": "goal:rag",
        "asset_manifest_version": "asset-v1",
        "catalog_version": "catalog-v1",
        "upstream_source_version": "rag-source-v1",
        "source_version": "source-link-s3-v1",
    }
    stored = index.replace_day("fresh-user", "plan-rag", 1, [link])[0]
    for field in (
        "experience_source_id", "asset_concept_id", "asset_scope",
        "asset_manifest_version", "catalog_version", "upstream_source_version",
    ):
        assert stored[field] == link[field]


def test_published_scoped_assets_form_a_node_specific_verified_contract():
    from source_grounded_v4_generator import _approved_asset_profile

    assets = [
        {"asset_type": "foundation_intuition", "content": {
            "explanation": "Retrieval selects passages for a query.",
            "bridge": "A relevance signal ranks candidate passages.",
            "check": "Missing evidence cannot be recovered by the generator.",
        }},
        {"asset_type": "advanced_worked_example", "content": {
            "problem": "Trace one query through a retriever.",
            "steps": ["encode query", "rank passages", "return evidence"],
        }},
    ]
    profile = _approved_asset_profile("Retrieval", assets)
    assert profile is not None
    claims = {item["kind"]: item["text"] for item in profile["claims"]}
    assert claims["definition"] == "Retrieval selects passages for a query."
    assert claims["mechanism"] == "A relevance signal ranks candidate passages."
    assert {item["kind"] for item in profile["assessment_targets"]} == {
        "mechanism", "misconception_discrimination", "application_or_boundary",
    }


def test_experience_run_store_records_auditable_owner_versions_and_evidence(tmp_path):
    store = ExperienceRunStore(tmp_path / "runs.db")
    plan = {
        "plan_id": "plan-1", "goal_text": GOALS["rag"], "profile_snapshot": {"profile_version": 2},
        "plan": {"goal_text": GOALS["rag"], "verified_goal_scope": {"source": "goal_chain_catalog"}},
    }
    lecture = {
        "generation_metadata": {"cache_status": "ready", "content_model": "gpt-test", "prompt_version": "prompt-1", "generator_version": "gen-1", "asset_manifest_version": "assets-1", "source_link_version": "sources-1", "temperature": 0.2},
        "lecture_sections": [{"section_id": "section-1", "source_pages": [{"resource_id": "resource-1", "document_id": "document-1", "page_number": 21, "link_id": "link-1"}]}],
    }
    payload = build_experience_run(user_id="anon-fresh", plan_record=plan, day=1, lecture=lecture, success=True)
    saved = store.save(user_id="anon-fresh", plan_id="plan-1", day=1, status="success", payload=payload)
    loaded = store.latest("anon-fresh", "plan-1", 1)
    assert loaded == saved
    assert loaded["profile_snapshot"]["profile_version"] == 2
    assert loaded["versions"]["model"] == "gpt-test"
    assert loaded["versions"]["temperature"] == 0.2
    assert loaded["source_evidence"][0]["page_number"] == 21
    assert loaded["success"] is True
