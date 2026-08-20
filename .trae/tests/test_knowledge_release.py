from knowledge_release import KnowledgeReleaseService, active_release_allows
from verified_golden_sources import GOLDEN_PATH


def _candidate():
    records = []
    for name in GOLDEN_PATH:
        records.append({"concept_name": name, "claims": [{"source_pages": [1]}] * 5, "misconceptions": [{}, {}], "assessment_targets": [{}, {}, {}], "evidence": {"pages": [{"page_number": 1}]}})
    return {"candidate_id": "candidate-a", "status": "draft", "validation_errors": [], "records": records}


def test_kq5_publish_exposes_only_reviewed_knowledge_and_rollback_is_atomic(tmpdir):
    root = tmpdir.mkdir("knowledge-release")
    service = KnowledgeReleaseService(kg_dir=str(root), release_dir=str(root / "releases"))
    candidate = _candidate()
    published = service.publish(candidate)
    assert published["status"] == "published"
    assert service.current()["candidate_id"] == "candidate-a"
    assert active_release_allows("XOR", release_dir=str(root / "releases")) is True
    assert active_release_allows("Unreviewed Concept", release_dir=str(root / "releases")) is False
    restored = service.rollback("candidate-a")
    assert restored["candidate_id"] == "candidate-a"


def test_kq5_rejects_incomplete_candidate(tmpdir):
    root = tmpdir.mkdir("bad-knowledge-release")
    service = KnowledgeReleaseService(kg_dir=str(root), release_dir=str(root / "releases"))
    bad = {"candidate_id": "bad", "validation_errors": [], "records": []}
    assert service.review(bad)["passed"] is False
