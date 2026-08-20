import pytest

from full_lecture_contract import (
    FULL_LECTURE_CONTRACT_VERSION,
    FullLectureValidationError,
    from_annotated_session,
    validate_full_lecture,
)


def annotated_fixture():
    return {
        "contract_version": "annotated-session-v1",
        "annotated_session_id": "ann-1",
        "path_id": "path-1",
        "plan_id": "plan-1",
        "day": 2,
        "scheduled_minutes": 30,
        "source_hash": "abc",
        "session_overview": {"title": "Understanding vectors", "goal_for_today": "Use vectors in retrieval"},
        "reading_sequence": [{"reading_id": "r-1", "citation_id": "c-1", "source_type": "private_document"}],
        "concept_bridges": [{"title": "Vectors", "estimated_minutes": 30, "explanation": "Vectors represent values."}],
        "citations": [{"citation_id": "c-1", "title": "Uploaded PDF"}],
    }


def test_annotated_session_converts_to_valid_full_lecture():
    payload = from_annotated_session(annotated_fixture())
    assert payload["contract_version"] == FULL_LECTURE_CONTRACT_VERSION
    assert payload["generation_metadata"]["upstream_contract"] == "annotated-session-v1"
    assert payload["lecture_sections"][0]["source_refs"] == ["c-1"]
    assert sum(item["estimated_minutes"] for item in payload["lecture_sections"]) <= 30


def test_full_lecture_rejects_sections_over_schedule():
    payload = from_annotated_session(annotated_fixture())
    payload["lecture_sections"][0]["estimated_minutes"] = 31
    with pytest.raises(FullLectureValidationError, match="exceed scheduled minutes"):
        validate_full_lecture(payload)


def test_full_lecture_requires_teaching_fields():
    payload = from_annotated_session(annotated_fixture())
    del payload["lecture_sections"][0]["teaching"]["worked_example"]
    with pytest.raises(FullLectureValidationError, match="worked_example"):
        validate_full_lecture(payload)

