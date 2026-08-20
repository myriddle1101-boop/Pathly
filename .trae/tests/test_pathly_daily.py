from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import pathly_server
from pathly_backend import PathlyStore
from pathly_daily import (
    DailyLearningNotFoundError,
    DailyLearningService,
    DailyLearningStore,
    EvidencePreparer,
    CONTENT_CONTRACT_VERSION,
)


class FakeProfiles:
    def get_profile(self, user_id):
        return {"user_id": user_id, "profile_version": 3, "preferred_style": "examples"}


class FakeDocuments:
    def get_chunks(self, user_id, document_id):
        return []


class FakeDocumentService:
    def _chroma_collection(self, user_id):
        raise RuntimeError("private chroma unavailable")


def scheduled_plan():
    return {
        "schema_version": 3,
        "goal": {"text": "Learn neural networks"},
        "concept_path": [
            {"concept_id": "Neural Networks", "display_name": "Neural Networks"},
            {"concept_id": "Backpropagation", "display_name": "Backpropagation"},
        ],
        "feasibility": {
            "requested_days": 3,
            "effective_days": 3,
            "max_available_daily_minutes": 75,
            "deadline": "2026-08-02",
        },
        "days": [
            {"day": 1, "total_minutes": 60, "activities": [
                {"activity_id": "a1", "activity_type": "explanation", "concept_ids": ["Neural Networks"], "estimated_minutes": 60}
            ]},
            {"day": 2, "total_minutes": 70, "activities": [
                {"activity_id": "a2", "activity_type": "practice", "concept_ids": ["Backpropagation"], "estimated_minutes": 70}
            ]},
            {"day": 3, "total_minutes": 30, "activities": [
                {"activity_id": "a3", "activity_type": "review", "concept_ids": ["Backpropagation"], "estimated_minutes": 30}
            ]},
        ],
    }


def environment(tmp_path, *, model_generator=None):
    db = tmp_path / "daily.db"
    plans = PathlyStore(db)
    record = plans.save_plan(
        "learner-1",
        scheduled_plan(),
        "live",
        ["neo4j", "private_rag"],
        path_id="path-1",
        goal_text="Learn neural networks",
        profile_snapshot={"user_id": "learner-1", "profile_version": 3},
    )
    backend = SimpleNamespace(plans=plans, profiles=FakeProfiles())
    store = DailyLearningStore(db)

    def context_provider(**kwargs):
        return {
            "concept_id": kwargs["concept_id"],
            "kg_context": {"concept": {"description": "A connected learning concept."}},
            "kg_source": "neo4j",
            "recommended_resources": [{
                "id": "resource-1", "title": "Visual guide", "type": "article",
                "resource_difficulty": "introductory", "estimated_minutes": 12,
                "match_reason": "Matches the learner's example-first preference.",
            }],
            "public_chunks": [],
            "private_chunks": [{
                "id": "private-chunk-1", "text": "Private evidence for this concept.",
                "metadata": {"document_id": "doc-1", "page_start": 2, "page_end": 2},
                "private": True,
            }],
            "errors": [],
        }

    service = DailyLearningService(
        backend, store, FakeDocuments(), FakeDocumentService(),
        today_provider=lambda: date(2026, 7, 28),
        context_provider=context_provider,
        model_generator=model_generator,
    )
    return record, service


def test_activate_maps_day_numbers_to_dates_and_today_returns_earliest_due(tmp_path):
    record, service = environment(tmp_path)
    activated = service.activate(
        user_id="learner-1", plan_id=record["plan_id"],
        start_date="2026-07-27", timezone_name="Asia/Shanghai",
    )
    assert [item["scheduled_date"] for item in activated["day_dates"]] == [
        "2026-07-27", "2026-07-28", "2026-07-29"
    ]
    today = service.today(user_id="learner-1", path_id="path-1")
    assert today["current"]["day"] == 1
    assert today["is_overdue"] is True
    assert today["timezone"] == "Asia/Shanghai"


def test_reschedule_previews_deadline_impact_before_persisting(tmp_path):
    record, service = environment(tmp_path)
    service.activate(user_id="learner-1", plan_id=record["plan_id"], start_date="2026-07-31")
    preview = service.reschedule(
        user_id="learner-1", path_id="path-1", day=2, new_date="2026-08-03"
    )
    assert preview["requires_confirmation"] is True
    assert service.store.dates("path-1")[-1]["scheduled_date"] == "2026-08-02"
    confirmed = service.reschedule(
        user_id="learner-1", path_id="path-1", day=2, new_date="2026-08-03",
        confirm_deadline_impact=True,
    )
    assert confirmed["confirmed"] is True
    assert confirmed["day_dates"][-1]["scheduled_date"] == "2026-08-04"


def live_lesson(source):
    return {
        "title": "Personalized lesson",
        "objectives": ["Explain the concept"],
        "sections": [{
            "section_id": "section-1", "title": "Core idea",
            "explanation": "A personalized explanation.", "example": "A visual example.",
            "application": "Try the scheduled activity.", "key_points": ["Key point"],
        }],
        "summary": "Review the key point.",
    }


def test_content_uses_context_resources_private_citations_and_cache(tmp_path):
    record, service = environment(tmp_path, model_generator=live_lesson)
    first = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    second = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert first["generation_mode"] == "live"
    assert first["resources"][0]["reason"]
    assert first["citations"][0]["source_type"] == "private_document"
    assert first["source_hash"] == second["source_hash"]
    assert second["cache_status"] == "hit"
    service.backend.profiles = SimpleNamespace(get_profile=lambda _user_id: {"profile_version": 4})
    changed = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert changed["cache_status"] == "miss"
    assert changed["source_hash"] != first["source_hash"]


def test_content_falls_back_transparently_when_model_fails(tmp_path):
    def unavailable(_source):
        raise RuntimeError("model unavailable")

    record, service = environment(tmp_path, model_generator=unavailable)
    content = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=2)
    assert content["generation_mode"] == "fallback"
    assert content["fallback_reason"] == "RuntimeError"
    assert content["lesson"]["sections"]
    assert content["citations"][0]["source_type"] == "private_document"


def test_other_user_cannot_read_plan_or_content(tmp_path):
    record, service = environment(tmp_path, model_generator=live_lesson)
    with pytest.raises(DailyLearningNotFoundError):
        service.generate_content(user_id="other", plan_id=record["plan_id"], day=1)


def test_daily_learning_api_contract(monkeypatch, tmp_path):
    record, service = environment(tmp_path, model_generator=live_lesson)
    monkeypatch.setattr(pathly_server, "daily_learning_service", service, raising=False)
    client = TestClient(pathly_server.app)
    activated = client.post(
        f"/api/plans/{record['plan_id']}/activate",
        json={"user_id": "learner-1", "start_date": "2026-07-28", "timezone": "Asia/Shanghai"},
    )
    assert activated.status_code == 201
    today = client.get("/api/paths/path-1/today?user_id=learner-1")
    assert today.status_code == 200
    generated = client.post(
        f"/api/plans/{record['plan_id']}/days/1/content",
        json={"user_id": "learner-1"},
    )
    assert generated.status_code == 201
    assert generated.json()["data"]["lesson"]["sections"]
    resources = client.get(
        f"/api/plans/{record['plan_id']}/days/1/resources?user_id=learner-1"
    )
    assert resources.status_code == 200
    assert resources.json()["data"][0]["title"] == "Visual guide"



def test_v2_contract_maps_every_activity_and_preserves_minutes(tmp_path):
    record, service = environment(tmp_path, model_generator=live_lesson)
    content = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    plan_day = service.day(record, 1)
    assert content["contract_version"] == CONTENT_CONTRACT_VERSION
    assert {block["activity_id"] for block in content["study_blocks"]} == {activity["activity_id"] for activity in plan_day["activities"]}
    assert sum(block["estimated_minutes"] for block in content["study_blocks"] if block["required"]) == sum(activity["estimated_minutes"] for activity in plan_day["activities"] if not activity.get("optional"))
    assert content["generation_metadata"]["content_contract_version"] == CONTENT_CONTRACT_VERSION


def test_v2_fallback_blocks_are_student_executable(tmp_path):
    record, service = environment(tmp_path, model_generator=lambda _source: (_ for _ in ()).throw(RuntimeError("offline")))
    content = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    block = content["study_blocks"][0]
    assert content["generation_metadata"]["generator_version"] == "content-agent-v7"
    assert block["content"]["learning_flow"]
    assert block["content"]["mini_task"]["prompt"]
    assert block["content"]["mini_task"]["placeholder"]
    assert block["content"]["self_check"]


def test_study_block_completion_persists_learner_answer(tmp_path):
    record, service = environment(tmp_path, model_generator=lambda _source: (_ for _ in ()).throw(RuntimeError("offline")))
    content = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    block_id = content["study_blocks"][0]["block_id"]
    result = service.update_block(
        user_id="learner-1", plan_id=record["plan_id"], day=1, block_id=block_id,
        status="completed", actual_seconds=90, answer={"text": "This is my own explanation with an example."},
    )
    assert result["block_progress"]["answer"]["text"].startswith("This is my own")
    restored = service.get_session(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert restored["study_blocks"][0]["progress_state"]["answer"]["text"].startswith("This is my own")

def test_evidence_preparation_removes_author_email_and_reference_noise():
    contexts = [{
        "concept_id": "RAG",
        "private_chunks": [{
            "id": "dirty-1", "private": True,
            "text": "Alice Smith Bob Jones Carol White Department of Computer Science Example University alice@example.com\nRetrieval augmented generation connects retrieved evidence to a language model so that answers can use relevant external context.\nReferences\n[1] Example paper",
            "metadata": {"document_id": "doc-1", "page_start": 2},
        }],
        "public_chunks": [],
    }]
    prepared = EvidencePreparer.prepare(contexts)
    assert prepared
    clean = prepared[0]["clean_text"]
    assert "alice@example.com" not in clean
    assert "Example University" not in clean
    assert "[1]" not in clean
    assert "retrieved evidence" in clean


def test_block_progress_unlocks_sequentially_and_survives_reload(tmp_path):
    record, service = environment(tmp_path, model_generator=live_lesson)
    content = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    first = content["study_blocks"][0]
    assert first["progress_state"]["status"] == "available"
    result = service.update_block(user_id="learner-1", plan_id=record["plan_id"], day=1, block_id=first["block_id"], status="completed", actual_seconds=42)
    restored = service.get_session(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert result["block_progress"]["status"] == "completed"
    assert restored["study_blocks"][0]["progress_state"]["actual_seconds"] == 42
    assert restored["session_progress"]["fraction"] == 1


def test_low_quality_chunk_remains_provenance_but_not_teaching_evidence(tmp_path):
    record, service = environment(tmp_path, model_generator=live_lesson)
    content = service.generate_content(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert content["prepared_evidence"] == []
    assert content["citations"][0]["used_in_teaching"] is False
    assert content["retrieval"]["private_rag_chunks"] == 0

