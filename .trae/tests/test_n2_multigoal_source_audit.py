from n2_multigoal_source_audit import build_audit


def test_existing_candidate_sources_are_not_misreported_as_page_grounded():
    report = build_audit()
    assert report["summary"]["candidate_goals"] == 3
    assert report["summary"]["candidate_sources"] >= 4
    assert report["summary"]["page_grounding_ready_sources"] == 0
    assert all(not item["eligible_source_coverage"] for item in report["goals"])
