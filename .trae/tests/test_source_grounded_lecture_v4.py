import copy
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from pathly_server import app
from source_linking_index import SOURCE_LINK_VERSION
from source_grounded_v4_store import (
    SourceGroundedLectureV4Store,
    V4_CONTRACT_VERSION,
    create_v4_baseline,
)


def sample_v3():
    return {
        "contract_version": "full-lecture-v3",
        "lecture_sections": [{"section_id": "lecture-section-1", "title": "XOR"}],
        "generation_metadata": {"generator_version": "v3"},
    }


def test_v4_baseline_is_a_detached_v3_snapshot():
    original = sample_v3()
    before = copy.deepcopy(original)
    v4 = create_v4_baseline(original, source_link_version=SOURCE_LINK_VERSION, golden_path=[{"concept_name": "XOR", "status": "verified"}])
    assert original == before
    assert v4["contract_version"] == V4_CONTRACT_VERSION
    assert v4["generation_metadata"]["isolated_from_v3"] is True
    assert v4["generation_metadata"]["source_link_version"] == SOURCE_LINK_VERSION
    assert v4["golden_path_sources"][0]["status"] == "verified"
    assert v4["source_links"] == []


def test_v4_store_keeps_payload_and_progress_separate(tmp_path):
    store = SourceGroundedLectureV4Store(tmp_path / "v4.db")
    payload = create_v4_baseline(sample_v3())
    store.save("user-a", "plan-a", 1, payload)
    store.set_progress("user-a", "plan-a", 1, "lecture-section-1", True)
    assert store.get("user-a", "plan-a", 1)["contract_version"] == V4_CONTRACT_VERSION
    assert store.progress("user-a", "plan-a", 1)["lecture-section-1"]["status"] == "completed"
    assert store.progress("user-b", "plan-a", 1) == {}


def test_v4_store_persists_exercise_answers_per_session_plan_and_question(tmp_path):
    store = SourceGroundedLectureV4Store(tmp_path / "v4-exercises.db")
    saved = store.set_exercise_answer("user-a", "plan-a", 1, "section-a", "q1", "a", True)
    assert saved["correct"] is True
    assert store.exercise_answers("user-a", "plan-a", 1)["section-a:q1"]["answer_id"] == "a"
    assert store.exercise_answers("user-b", "plan-a", 1) == {}


def test_v4_routes_are_parallel_to_v3():
    routes = {getattr(route, "path", "") for route in app.routes}
    assert "/api/plans/{plan_id}/days/{day}/full-lecture" in routes
    assert "/api/plans/{plan_id}/days/{day}/lecture-v4" in routes
    assert "/api/plans/{plan_id}/days/{day}/lecture-v4/generate" in routes
    assert "/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/complete" in routes
    assert "/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/retry" in routes
    assert "/api/plans/{plan_id}/days/{day}/lecture-v4/sections/{section_id}/exercises/{question_id}/answer" in routes


def test_verified_public_pdf_page_route_renders_with_declared_runtime(monkeypatch, tmp_path):
    import pathly_server

    source = tmp_path / "verified.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    def fake_render(args, **_kwargs):
        Path(f"{args[-1]}.png").write_bytes(b"\x89PNG\r\n\x1a\npublic-page")

    monkeypatch.setattr(pathly_server.verified_golden_sources, "pdf_path_for_resource", lambda _resource: source)
    monkeypatch.setattr(pathly_server.subprocess, "run", fake_render)
    monkeypatch.setattr(pathly_server, "DATA_DIR", tmp_path / "data")
    client = TestClient(app)
    assert client.post("/api/sessions/anonymous").status_code == 201
    response = client.get("/api/public-resources/verified-resource/pages/1/render")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_capabilities_expose_v4_isolation_without_hiding_v3():
    response = TestClient(app).get("/api/capabilities")
    assert response.status_code == 200
    capability = response.json()["data"]["source_grounded_lecture_v4"]
    assert capability["stage"] == "s4_source_grounded_lecture"
    assert capability["golden_path"] == ["Linear Separability", "XOR", "Neural Networks", "Activation Functions", "Gradient Descent"]
    assert capability["isolated_progress"] is True
    assert capability["changes_v1_v2_v3"] is False


def test_learner_facing_frontend_hides_legacy_views_and_quiz_navigation():
    script = open("pathly-app.js", encoding="utf-8").read()
    navigation = script.split("function dailyNavigation()", 1)[1].split("function dailyHeader()", 1)[0]
    assert 'return ""' in navigation
    assert "Daily Quiz" not in navigation
    assert "v4SectionProgress" in script
    assert "v4CurrentSectionId" in script
    assert "v4ScrollPosition" in script
    assert "Preparing your first learning section" in script
    assert "TODAY'S LESSON" in script
    assert "Repair this section" in script
    assert "SOURCE EXPLANATION" in script
    assert "WHAT THIS PAGE IS SHOWING" not in script
    assert "/api/public-resources/" in script
    assert "v4-page-annotation" in script
    assert "PAGE-BY-PAGE EXPLANATION" not in script
    assert "OBJECTIVE EXERCISE" in script
    assert "Answer all objective questions correctly" in script
    assert "SOURCE MATERIAL" in script
    assert "match_reason" not in script.split("function v4SourceStatusCard", 1)[1].split("function v4AnswerKey", 1)[0]
    assert 'meta.source_link_version!=="source-link-s3-v1"' not in script
    assert "v4GenerationState(lecture)" in script
    assert "Your lesson could not be generated" in script


def test_v4_document_deletion_invalidates_only_owner_snapshot(tmp_path):
    store = SourceGroundedLectureV4Store(tmp_path / "v4-cleanup.db")
    linked = create_v4_baseline(sample_v3(), [{"concept_id": "xor", "document_id": "private-doc"}])
    store.save("owner-a", "plan-a", 1, linked)
    store.save("owner-b", "plan-b", 1, linked)
    store.set_progress("owner-a", "plan-a", 1, "lecture-section-1", True)
    assert store.delete_by_document("owner-a", "private-doc") == 1
    assert store.get("owner-a", "plan-a", 1) is None
    assert store.progress("owner-a", "plan-a", 1) == {}
    assert store.get("owner-b", "plan-b", 1) is not None


def test_source_link_api_is_exposed_alongside_v4_routes():
    routes = {getattr(route, "path", "") for route in app.routes}
    assert "/api/plans/{plan_id}/days/{day}/lecture-v4/source-links" in routes
    assert "/api/lecture-v4/golden-path" in routes


def test_v4_seed_uses_verified_canonical_chain_for_normal_golden_goal():
    from pathly_server import _v4_seed_lecture_from_daily
    from verified_golden_sources import GOLDEN_PATH

    plan_record = {
        "plan_id": "plan-golden-normal",
        "path_id": "path-golden-normal",
        "goal_text": (
            "I want to understand why XOR is not linearly separable and learn how "
            "neural networks, activation functions, and gradient descent solve this problem."
        ),
        "plan": {
            "days": [{
                "day": 1,
                "total_minutes": 96,
                "activities": [{"concept_ids": ["Deep Learning"]}],
                "focus_topics": ["Deep Learning"],
            }],
            "concept_path": [{"concept_id": "Deep Learning", "display_name": "Deep Learning"}],
        },
    }
    daily = {"scheduled_minutes": 96, "study_blocks": [{"concept_ids": ["Deep Learning"]}]}

    seed = _v4_seed_lecture_from_daily(daily, plan_record, 1)

    assert [section["concept_name"] for section in seed["lecture_sections"]] == GOLDEN_PATH
    assert [section["concept_ids"][0] for section in seed["lecture_sections"]] == GOLDEN_PATH
    assert seed["generation_metadata"]["verified_source_policy"] == "golden-goal-canonical-v2"


def test_v4_route_uses_generator_alias_without_shadowing():
    import inspect
    import pathly_server

    source = inspect.getsource(pathly_server._v4_build_lecture)
    assert "build_source_grounded_lecture_v4" in source
    assert "run_in_threadpool(\n        generate_source_grounded_lecture_v4," not in source


def test_v4_retry_reuses_isolated_snapshot_instead_of_rebuilding_v3():
    import inspect
    import pathly_server

    source = inspect.getsource(pathly_server._v4_section_retry_worker)
    assert 'isolated["lecture_sections"] = [target]' in source
    assert "generate_full_lecture(" not in source
    assert "generate_full_lecture_from_daily(" not in source


def test_v4_retry_is_single_section_and_bounded():
    import inspect
    import pathly_server

    route = inspect.getsource(pathly_server.retry_source_grounded_lecture_v4_section)
    worker = inspect.getsource(pathly_server._v4_section_retry_worker)
    assert 'isolated["lecture_sections"] = [target]' in worker
    assert "retry_attempts" in route
    assert "max_retry_attempts" in route
    assert "Maximum section retry attempts reached" in route


def test_v4_get_treats_missing_cache_as_generatable_state():
    import inspect
    import pathly_server

    source = inspect.getsource(pathly_server.get_source_grounded_lecture_v4)
    assert "_v4_pending_payload" in source
    assert '"cache_missing"' in source
    assert "raise HTTPException(status_code=404, detail=\"Source-Grounded Lecture View v4 has not been generated\")" not in source


def test_interrupted_persisted_generation_becomes_retryable_failure():
    from pathly_server import _v4_recover_interrupted
    lecture = {
        "v4_status": "generating",
        "generation_metadata": {
            "generation_state": "generating",
            "started_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "attempt_count": 1,
        },
    }
    recovered = _v4_recover_interrupted(lecture, active=False)
    assert recovered["v4_status"] == "failed"
    assert recovered["can_generate"] is True
    assert recovered["generation_metadata"]["failure_code"] == "generation_interrupted"


def test_active_generation_is_not_marked_interrupted_by_poll_timeout():
    from pathly_server import _v4_recover_interrupted
    lecture = {
        "v4_status": "generating",
        "generation_metadata": {
            "generation_state": "generating",
            "started_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "attempt_count": 1,
        },
    }
    recovered = _v4_recover_interrupted(lecture, active=True)
    assert recovered["v4_status"] == "generating"
    assert recovered["generation_metadata"].get("failure_code") is None


def test_generation_retry_limit_is_persisted_and_enforced(monkeypatch):
    import pathly_server
    existing = {"generation_metadata": {"attempt_count": pathly_server.V4_MAX_RETRY_ATTEMPTS}}
    monkeypatch.setattr(pathly_server.source_grounded_v4_store, "get", lambda *_: existing)
    with pytest.raises(pathly_server.HTTPException) as exc:
        pathly_server._queue_v4_generation("u", {"plan_id": "p"}, 1, "fingerprint", True)
    assert exc.value.status_code == 409


def test_v4_read_endpoints_resolve_user_from_session_without_required_query_param():
    import inspect
    import pathly_server

    get_signature = inspect.signature(pathly_server.get_source_grounded_lecture_v4)
    links_signature = inspect.signature(pathly_server.get_source_grounded_lecture_v4_links)
    assert get_signature.parameters["user_id"].default is None
    assert links_signature.parameters["user_id"].default is None


def test_v4_generate_initializes_daily_runtime_before_building_lecture():
    import inspect
    import pathly_server

    source = open("pathly-app.js", encoding="utf-8").read()
    context = source.split("async function loadV4RouteContext(dayOverride=null){", 1)[1].split("async function loadTodayData", 1)[0]
    assert "/days/${selected.day}/start" in context
    assert "/days/${selected.day}/content" not in context


def test_v4_frontend_forces_retry_and_handles_pending_cache_state():
    script = open("pathly-app.js", encoding="utf-8").read()
    assert 'onclick="loadLectureV4(true)">Try again' in script
    assert 'if(phase==="complete")' in script
    assert 'if(phase==="queued"||phase==="generating")' in script
    assert "Trying again..." in script
    assert "cache_missing" in open("pathly_server.py", encoding="utf-8").read()


def test_v4_frontend_restores_section_local_publishing_and_manual_repair():
    script = open("pathly-app.js", encoding="utf-8").read()
    view_start = script.index("function v4UnavailableSection(section,index)")
    view_end = script.index("async function loadLectureV4", view_start)
    view = script[view_start:view_end]
    assert "Repair this section" in view
    assert "Repair attempt" in view
    assert "v4ReadySection" in view
    assert "sections complete" in view
    assert "Only the complete, approved lecture will be shown here." not in view
    assert "autoRepairLectureV4" not in script
    assert "Preparing your first learning section" in view

def test_v4_backend_allows_ready_sections_without_lecture_wide_gate():
    import inspect
    import pathly_server

    retry = inspect.getsource(pathly_server._v4_section_retry_worker)
    complete = inspect.getsource(pathly_server.complete_source_grounded_lecture_v4_section)
    assert "ready_count" in retry
    assert 'latest["v4_status"] = "generated" if ready_count else "unavailable"' in retry
    assert "Lecture has not passed its publication checks" not in complete


def test_v4_day_one_generates_one_section_then_queues_the_next_after_completion():
    import inspect
    import pathly_server

    builder = inspect.getsource(pathly_server._v4_build_lecture)
    queue = inspect.getsource(pathly_server._queue_next_v4_section)
    complete = inspect.getsource(pathly_server.complete_source_grounded_lecture_v4_section)
    assert "waiting_for_previous_section" in builder
    assert "section_id: str | None" in builder
    assert "_queue_next_v4_section" in complete
    assert "next_section_queued" in complete
    assert "waiting_for_previous_section" in queue
