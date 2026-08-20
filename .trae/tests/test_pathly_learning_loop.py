from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import pathly_server

from pathly_backend import PathlyStore
from pathly_daily import DailyLearningService, DailyLearningStore
from pathly_learning_loop import (
    LearningLoopService,
    LearningLoopStore,
    LearningLoopValidationError,
)


class Profiles:
    def get_profile(self, user_id):
        return {"user_id": user_id, "profile_version": 1}


class Documents:
    def get_chunks(self, user_id, document_id):
        return []


class DocumentService:
    def _chroma_collection(self, user_id):
        raise RuntimeError("not configured")


def lesson(_source):
    return {
        "title": "Day lesson",
        "objectives": ["Explain Topic"],
        "sections": [
            {
                "section_id": "s1",
                "title": "Topic",
                "explanation": "Topic connects inputs to outputs.",
                "example": "Use Topic in a small example.",
                "application": "Apply Topic.",
                "key_points": ["Topic is part of the learning path."],
            }
        ],
        "summary": "Review Topic.",
    }


def environment(tmp_path):
    db = tmp_path / "loop.db"
    plans = PathlyStore(db)
    plan = {
        "goal": {"text": "Learn Topic"},
        "concept_path": [{"concept_id": "Topic", "display_name": "Topic"}],
        "feasibility": {"deadline": "2026-08-05"},
        "days": [
            {
                "day": day,
                "total_minutes": 30,
                "activities": [
                    {
                        "activity_id": f"a{day}",
                        "activity_type": "explanation" if day == 1 else "review",
                        "concept_ids": ["Topic"],
                        "estimated_minutes": 30,
                    }
                ],
            }
            for day in range(1, 4)
        ],
    }
    record = plans.save_plan(
        "u1",
        plan,
        "live",
        ["json"],
        path_id="path-1",
        goal_text="Learn Topic",
        profile_snapshot={"user_id": "u1", "profile_version": 1},
    )
    backend = SimpleNamespace(plans=plans, profiles=Profiles())
    daily_store = DailyLearningStore(db)

    def context_provider(**kwargs):
        return {
            "concept_id": kwargs["concept_id"],
            "kg_context": {"concept": {"description": "Topic description"}},
            "kg_source": "json",
            "recommended_resources": [],
            "public_chunks": [
                {
                    "id": "chunk-1",
                    "text": "Topic evidence.",
                    "metadata": {"resource_id": "r1"},
                }
            ],
            "private_chunks": [],
            "errors": [],
        }

    daily = DailyLearningService(
        backend,
        daily_store,
        Documents(),
        DocumentService(),
        today_provider=lambda: date(2026, 7, 28),
        context_provider=context_provider,
        model_generator=lesson,
    )
    daily.activate(user_id="u1", plan_id=record["plan_id"], start_date="2026-07-28")
    daily.generate_content(user_id="u1", plan_id=record["plan_id"], day=1)
    loop = LearningLoopService(
        backend, daily, daily_store, LearningLoopStore(db)
    )
    return record, loop


def complete_required_blocks(loop, record, day=1):
    session = loop.daily.get_session(user_id="u1", plan_id=record["plan_id"], day=day)
    for block in session["study_blocks"]:
        if block.get("required", True):
            loop.daily.update_block(user_id="u1", plan_id=record["plan_id"], day=day, block_id=block["block_id"], status="completed", actual_seconds=10)


def correct_answers(quiz, *, confidence=5):
    answers = []
    for question in quiz["questions"]:
        answer = (
            "Topic applied to a small example"
            if question["type"] == "short_application"
            else question["correct_answer"]
        )
        answers.append(
            {
                "question_id": question["question_id"],
                "answer": answer,
                "confidence": confidence,
                "time_seconds": 5,
            }
        )
    return answers


def test_day_unlock_is_sequential_and_completion_unlocks_timeline_entry(tmp_path):
    record, loop = environment(tmp_path)
    progress = loop.progress(user_id="u1", path_id="path-1")
    assert [item["status"] for item in progress["days"]] == [
        "unlocked",
        "locked",
        "locked",
    ]
    with pytest.raises(LearningLoopValidationError):
        loop.start_day(user_id="u1", plan_id=record["plan_id"], day=2)

    complete_required_blocks(loop, record)
    quiz = loop.quiz(user_id="u1", plan_id=record["plan_id"], day=1)
    result = loop.submit_quiz(
        user_id="u1",
        plan_id=record["plan_id"],
        day=1,
        answers=correct_answers(quiz),
        duration_seconds=120,
    )
    statuses = [item["status"] for item in result["path_progress"]["days"]]
    assert statuses == ["completed", "unlocked", "locked"]
    assert result["path_progress"]["next_day"]["day"] == 2


def test_feedback_and_chat_create_repeated_confusion_signal(tmp_path, monkeypatch):
    record, loop = environment(tmp_path)
    loop.feedback(
        user_id="u1",
        plan_id=record["plan_id"],
        day=1,
        feedback_type="not_understood",
        concept_ids=["Topic"],
    )
    monkeypatch.setattr(
        loop,
        "_openai_answer",
        lambda *args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    response = loop.chat(
        user_id="u1",
        plan_id=record["plan_id"],
        day=1,
        message="I still do not understand Topic",
        intent="simplify",
    )
    assert response["mode"] == "fallback"
    assert response["citations"]
    summary = loop.confusion_summary(user_id="u1", path_id="path-1")
    assert summary[0]["concept_id"] == "Topic"
    assert summary[0]["count"] == 2


def test_quiz_is_stable_records_confidence_and_maps_weak_concept(tmp_path):
    record, loop = environment(tmp_path)
    complete_required_blocks(loop, record)
    first = loop.quiz(user_id="u1", plan_id=record["plan_id"], day=1)
    second = loop.quiz(user_id="u1", plan_id=record["plan_id"], day=1)
    assert second["quiz_id"] == first["quiz_id"]
    assert second["cache_status"] == "hit"
    wrong = [
        {
            "question_id": q["question_id"],
            "answer": "wrong",
            "confidence": 2,
            "time_seconds": 3,
        }
        for q in first["questions"]
    ]
    result = loop.submit_quiz(
        user_id="u1",
        plan_id=record["plan_id"],
        day=1,
        answers=wrong,
        duration_seconds=30,
    )
    assert result["score"] < 70
    assert result["confidence"] == 2
    assert result["weak_concepts"] == ["Topic"]


def test_adaptation_reject_preserves_plan_and_accept_creates_next_version(tmp_path):
    record, loop = environment(tmp_path)
    complete_required_blocks(loop, record)
    quiz = loop.quiz(user_id="u1", plan_id=record["plan_id"], day=1)
    wrong = [
        {
            "question_id": q["question_id"],
            "answer": "wrong",
            "confidence": 1,
        }
        for q in quiz["questions"]
    ]
    loop.submit_quiz(
        user_id="u1",
        plan_id=record["plan_id"],
        day=1,
        answers=wrong,
        duration_seconds=30,
    )
    rejected = loop.create_proposal(user_id="u1", path_id="path-1")
    decision = loop.decide_proposal(
        user_id="u1", proposal_id=rejected["proposal_id"], decision="reject"
    )
    assert decision["status"] == "rejected"
    assert len(loop.backend.plans.list_plans("u1")) == 1

    accepted = loop.create_proposal(user_id="u1", path_id="path-1")
    result = loop.decide_proposal(
        user_id="u1",
        proposal_id=accepted["proposal_id"],
        decision="modify",
        modifications={"review_minutes": 10},
    )
    assert result["status"] == "accepted"
    assert result["new_plan_version"] == record["version"] + 1
    assert len(loop.backend.plans.list_plans("u1")) == 2
    assert any(
        activity.get("adaptation")
        for day in result["plan"]["plan"]["days"]
        for activity in day["activities"]
    )

def test_learning_loop_api_unlocks_next_timeline_day(monkeypatch, tmp_path):
    record, loop = environment(tmp_path)
    monkeypatch.setattr(pathly_server, "learning_loop_service", loop, raising=False)
    monkeypatch.setattr(pathly_server, "daily_learning_service", loop.daily, raising=False)
    client = TestClient(pathly_server.app)

    locked = client.post(
        f"/api/plans/{record['plan_id']}/days/2/start",
        json={"user_id": "u1"},
    )
    assert locked.status_code == 409

    blocked_quiz = client.get(f"/api/plans/{record['plan_id']}/days/1/quiz?user_id=u1")
    assert blocked_quiz.status_code == 409
    session = loop.daily.get_session(user_id="u1", plan_id=record["plan_id"], day=1)
    for block in session["study_blocks"]:
        completed = client.post(f"/api/plans/{record['plan_id']}/days/1/blocks/{block['block_id']}/complete", json={"user_id":"u1","actual_seconds":10})
        assert completed.status_code == 200
    quiz = client.get(f"/api/plans/{record['plan_id']}/days/1/quiz?user_id=u1")
    assert quiz.status_code == 200
    public_quiz = quiz.json()["data"]
    assert "correct_answer" not in public_quiz["questions"][0]

    private_quiz = loop.quiz(user_id="u1", plan_id=record["plan_id"], day=1)
    submitted = client.post(
        f"/api/plans/{record['plan_id']}/days/1/quiz-attempts",
        json={
            "user_id": "u1",
            "answers": correct_answers(private_quiz),
            "duration_seconds": 120,
        },
    )
    assert submitted.status_code == 201
    progress = submitted.json()["data"]["path_progress"]
    assert [item["status"] for item in progress["days"]] == [
        "completed",
        "unlocked",
        "locked",
    ]
    assert progress["next_day"]["day"] == 2

    started = client.post(
        f"/api/plans/{record['plan_id']}/days/2/start",
        json={"user_id": "u1"},
    )
    assert started.status_code == 200
    assert started.json()["data"]["path"]["days"][1]["status"] == "in_progress"

