from full_lecture_store import FullLectureProgressStore


def test_section_progress_persists_and_can_be_reopened(tmp_path):
    store = FullLectureProgressStore(tmp_path / "lecture.db")
    saved = store.set("u1", "p1", 1, "section-1", True)
    assert saved["status"] == "completed"
    assert store.get("u1", "p1", 1)["section-1"]["status"] == "completed"
    reopened = store.set("u1", "p1", 1, "section-1", False)
    assert reopened["status"] == "available"
    assert store.get("u1", "p1", 1)["section-1"]["status"] == "available"

