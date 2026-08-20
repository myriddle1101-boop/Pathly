from ablation_config import ABLATION_VERSION, capability_matrix, get_system_config


def test_matrix_has_four_explicitly_distinct_treatments():
    rows = capability_matrix()
    assert [row["version"] for row in rows] == ["V0", "V1", "V2", "V3"]
    assert rows[0]["profile"] is False and rows[0]["kg"] is False
    assert rows[1]["profile"] is True and rows[1]["kg"] is False
    assert rows[2]["kg"] is True and rows[2]["source_grounding"] is False
    assert rows[2]["teaching_assets"] is False
    assert rows[3]["source_grounding"] is True
    assert rows[3]["teaching_assets"] is True
    assert rows[3]["product_surface"] == "lecture-v4"
    assert rows[3]["current_final_system"] is True
    assert rows[0]["current_final_system"] is False
    assert all(row["ablation_version"] == ABLATION_VERSION for row in rows)


def test_unknown_version_is_rejected():
    try:
        get_system_config("v4")
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("unknown ablation version must not silently fall through")
