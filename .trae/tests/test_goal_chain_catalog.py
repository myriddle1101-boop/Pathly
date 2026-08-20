from goal_chain_catalog import resolve_goal_chain


def test_short_verified_goal_alias_resolves_to_full_chain():
    match = resolve_goal_chain("rag")
    assert match is not None
    goal_id, spec = match
    assert goal_id == "rag"
    assert len(spec["canonical_path"]) == 4


def test_natural_language_goal_still_resolves():
    assert resolve_goal_chain("Understand how self-attention enables transformers to model context")[0] == "self_attention"
