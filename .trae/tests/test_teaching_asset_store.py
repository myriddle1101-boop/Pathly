from teaching_asset_store import TeachingAssetStore, TeachingAssetValidationError


def _asset(status="approved", asset_id="a1"):
    return {
        "asset_id": asset_id,
        "canonical_concept_id": "golden:activation-functions",
        "asset_type": "foundation_worked_example",
        "learner_tier": "foundation",
        "content": {"setup": "Compare two linear layers with and without ReLU.", "steps": ["Compute the first output.", "Apply the second operation."]},
        "assessment_targets": ["activation-mechanism"],
        "misconception_ids": ["depth-replaces-activation"],
        "knowledge_version": "ta-v1",
        "review_status": status,
        "evidence_refs": [{"document_id": "public:doc", "page_number": 17, "chunk_id": "chunk-17"}],
    }


def test_asset_requires_evidence_for_approved(tmp_path):
    store = TeachingAssetStore(tmp_path / "assets.db")
    asset = _asset()
    asset["evidence_refs"] = []
    try:
        store.upsert(asset)
    except TeachingAssetValidationError as exc:
        assert "evidence" in str(exc)
    else:
        raise AssertionError("approved asset without evidence should be rejected")


def test_publish_bundle_and_tiered_lookup(tmp_path):
    store = TeachingAssetStore(tmp_path / "assets.db")
    store.upsert(_asset())
    result = store.publish_bundle(manifest_version="ta-v1", asset_ids=["a1"])
    assert result["status"] == "published"
    assert store.current_manifest()["manifest_version"] == "ta-v1"
    assets = store.list_assets(concept_id="golden:activation-functions", learner_tier="foundation")
    assert len(assets) == 1
    assert assets[0]["evidence_refs"][0]["page_number"] == 17


def test_unapproved_asset_cannot_publish(tmp_path):
    store = TeachingAssetStore(tmp_path / "assets.db")
    store.upsert(_asset(status="draft"))
    try:
        store.publish_bundle(manifest_version="ta-v1", asset_ids=["a1"])
    except TeachingAssetValidationError as exc:
        assert "approved" in str(exc)
    else:
        raise AssertionError("draft asset should not publish")
