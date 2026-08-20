from fresh_experience_baseline import GOLDEN_PATH, TARGET_GOALS, build_baseline


def test_baseline_describes_current_views_without_claiming_ablation():
    payload = build_baseline()
    matrix = payload["current_version_matrix"]
    assert [item["current_id"] for item in matrix] == ["v1", "v2", "v3", "v4"]
    assert not any(item["is_controlled_ablation"] for item in matrix)
    assert matrix[-1]["teaching_assets"] is True


def test_baseline_keeps_xor_scope_separate_from_unverified_domains():
    payload = build_baseline()
    probes = {item["id"]: item for item in payload["goal_probes"]}
    assert probes["xor"]["certified_canonical_path"] == GOLDEN_PATH
    assert probes["word_embeddings"]["baseline_status"] == "not_certified_for_full_experience"
    assert probes["self_attention"]["certified_canonical_path"] == []
    assert probes["rag"]["certified_canonical_path"] == []
    assert len(TARGET_GOALS) == 4
