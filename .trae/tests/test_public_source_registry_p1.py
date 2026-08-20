from fastapi.testclient import TestClient

import pathly_server
from public_source_registry import PUBLIC_SOURCE_VERSION, PublicConceptSourceRegistry, PublicThenReviewedResolver


def sample_row(name="Neural Networks"):
    return {
        "canonical_concept_id": "neo4j:neural-networks",
        "canonical_concept_name": name,
        "aliases": ["neural network", "MLP"],
        "resource_id": "resource-public-1",
        "document_id": "public:resource-public-1",
        "document_title": "Neural Networks.pdf",
        "page_sequence": [
            {"page_number": 13, "role": "introduction", "chunk_ids": ["chunk-13"]},
            {"page_number": 14, "role": "mechanism", "chunk_ids": ["chunk-14"]},
        ],
        "chunk_ids": ["chunk-13", "chunk-14"],
        "relevance_score": 1.0,
        "coverage_score": 1.0,
        "match_method": "neo4j_chroma_reviewed_pages",
        "match_reason": "Reviewed continuous pages.",
        "review_status": "verified",
        "coverage_status": "verified_pages_and_resource_chunks",
        "neo4j_node_status": "present",
        "neo4j_resource_status": "linked",
        "source_url": "https://example.edu/neural-networks.pdf",
        "license_status": "reviewed",
    }


def test_public_registry_resolves_alias_without_plan_or_user_identity(tmp_path):
    registry = PublicConceptSourceRegistry(tmp_path / "registry.db", tmp_path)
    registry.replace_all([sample_row()])
    source = registry.resolve(concept_id="unknown", concept_name="mlp")
    assert source["canonical_concept_name"] == "Neural Networks"
    assert source["source_scope"] == "public"
    assert source["source_version"] == PUBLIC_SOURCE_VERSION
    assert "plan_id" not in source
    assert "user_id" not in source
    assert "day" not in source


def test_public_registry_rebuild_projection_is_replaceable(tmp_path):
    registry = PublicConceptSourceRegistry(tmp_path / "registry.db", tmp_path)
    first = registry.replace_all([sample_row()])
    second = registry.replace_all([sample_row("Neural Networks")])
    assert len(first) == len(second) == 1
    assert first[0]["link_id"] == second[0]["link_id"]


def test_resolver_prefers_public_registry_over_legacy_reviewed_source(tmp_path):
    registry = PublicConceptSourceRegistry(tmp_path / "registry.db", tmp_path)
    registry.replace_all([sample_row()])

    class Reviewed:
        def resolve(self, **_):
            return {"resource_id": "legacy"}

    source = PublicThenReviewedResolver(registry, Reviewed()).resolve(
        concept_id="Neural Networks", concept_name="Neural Networks"
    )
    assert source["resource_id"] == "resource-public-1"


def test_public_verified_source_api_never_exposes_learner_identity(monkeypatch):
    monkeypatch.setattr(pathly_server.public_source_registry, "resolve", lambda **_: {
        **sample_row(),
        "link_id": "public-source-1",
        "source_version": PUBLIC_SOURCE_VERSION,
        "source_scope": "public",
    })
    response = TestClient(pathly_server.app).get(
        "/api/concepts/neural-networks/verified-sources?concept_name=Neural%20Networks"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "verified"
    assert data["sources"][0]["source_scope"] == "public"
    encoded = response.text
    assert "user_id" not in encoded and "plan_id" not in encoded


def test_p1_routes_are_exposed():
    routes = {getattr(route, "path", "") for route in pathly_server.app.routes}
    assert "/api/concepts/{concept_id}/verified-sources" in routes
    assert "/api/internal/source-links/rebuild" in routes
