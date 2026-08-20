import pytest

pytest.importorskip("fastapi")


def test_goal_scoped_asset_manifest_is_accepted_by_runtime_policy():
    import pathly_server

    fingerprint = "same"
    current = {
        "generation_metadata": {
            "generator_version": pathly_server.S4_GENERATOR_VERSION,
            "source_link_version": pathly_server.SOURCE_LINK_VERSION,
            "source_link_status": "indexed",
            "scenario_fingerprint": fingerprint,
            "asset_manifest_version": "rag-assets-v1",
            "generation_state": "complete",
        }
    }
    assert pathly_server._v4_cache_is_current(current, fingerprint)


def test_unknown_asset_manifest_remains_stale():
    import pathly_server

    current = {"generation_metadata": {
        "generator_version": pathly_server.S4_GENERATOR_VERSION,
        "source_link_version": pathly_server.SOURCE_LINK_VERSION,
        "source_link_status": "indexed",
        "scenario_fingerprint": "same",
        "asset_manifest_version": "unreviewed-assets",
        "generation_state": "complete",
    }}
    assert not pathly_server._v4_cache_is_current(current, "same")


def test_published_self_attention_gold_manifest_is_accepted():
    import pathly_server

    current = {
        "lecture_sections": [{"section_id": "s1", "v4_status": "ready"}],
        "generation_metadata": {
            "generator_version": pathly_server.S4_GENERATOR_VERSION,
            "source_link_version": pathly_server.SOURCE_LINK_VERSION,
            "source_link_status": "indexed",
            "scenario_fingerprint": "generated-profile-fingerprint",
            "asset_manifest_version": "self-attention-gold-v1",
            "generation_state": "waiting_for_completion",
        },
    }
    assert pathly_server._v4_cache_is_current(current, "later-profile-fingerprint")
