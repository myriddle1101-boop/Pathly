from types import SimpleNamespace

from fastapi.testclient import TestClient

import pathly_server
from pathly_backend import PathlyStore
from pathly_daily import DailyLearningService, DailyLearningStore
from pathly_annotated_content import (
    ANNOTATED_AGENT_VERSION,
    ANNOTATED_CONTRACT_VERSION,
    AnnotatedContentService,
    AnnotatedContentStore,
)


class FakeProfiles:
    def get_profile(self, user_id):
        return {"user_id": user_id, "profile_version": 1, "learning_style": "source_first"}


class FakeDocuments:
    def get_chunks(self, user_id, document_id):
        return []


class FakeDocumentService:
    def _chroma_collection(self, user_id):
        raise RuntimeError("private chroma unavailable")


def scheduled_plan():
    return {
        "schema_version": 3,
        "goal": {"text": "Learn RAG from uploaded papers"},
        "concept_path": [
            {"concept_id": "RAG", "display_name": "Retrieval-Augmented Generation"},
            {"concept_id": "Knowledge Graph", "display_name": "Knowledge Graph"},
        ],
        "days": [
            {"day": 1, "total_minutes": 60, "activities": [
                {"activity_id": "a1", "activity_type": "required_reading", "concept_ids": ["RAG"], "estimated_minutes": 30},
                {"activity_id": "a2", "activity_type": "practice", "concept_ids": ["Knowledge Graph"], "estimated_minutes": 30},
            ]},
        ],
    }


def build_environment(tmp_path, *, private=True, public=True):
    db = tmp_path / "pathly.db"
    plans = PathlyStore(db)
    record = plans.save_plan(
        "learner-1",
        scheduled_plan(),
        "live",
        ["json", "private_rag"],
        path_id="path-1",
        goal_text="Learn RAG from uploaded papers",
        profile_snapshot={"user_id": "learner-1", "profile_version": 1},
    )
    daily_store = DailyLearningStore(db)

    def context_provider(**kwargs):
        concept_id = kwargs["concept_id"]
        private_chunks = []
        public_chunks = []
        if private:
            private_chunks.append({
                "id": f"private-{concept_id}",
                "text": f"This paper excerpt explains how {concept_id} is used in a learning system. It defines the concept mechanism and explains domain relationships.",
                "metadata": {"document_id": "doc-1", "display_name": "Uploaded RAG Paper.pdf", "page_start": 2, "page_end": 3, "section_title": "Core Method"},
                "private": True,
            })
        if public:
            public_chunks.append({
                "id": f"public-{concept_id}",
                "text": f"A public teaching resource explains {concept_id} with an example and a limitation for learners.",
                "metadata": {"resource_id": "public-1", "title": "Public RAG Guide", "section_title": "Overview"},
                "private": False,
            })
        return {
            "concept_id": concept_id,
            "kg_context": {"concept": {"description": f"{concept_id} description"}, "prerequisites": ["Prerequisite A"], "similar_concepts": ["Next B"]},
            "kg_source": "json",
            "recommended_resources": [],
            "private_chunks": private_chunks,
            "public_chunks": public_chunks,
            "errors": [],
        }

    backend = SimpleNamespace(plans=plans, profiles=FakeProfiles())
    daily = DailyLearningService(
        backend, daily_store, FakeDocuments(), FakeDocumentService(), context_provider=context_provider
    )
    annotated_store = AnnotatedContentStore(db)
    service = AnnotatedContentService(backend, annotated_store, daily)
    return record, service, annotated_store


def test_private_pdf_source_first_session_is_persisted_in_parallel_tables(tmp_path):
    record, service, store = build_environment(tmp_path, private=True, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1)

    assert session["contract_version"] == ANNOTATED_CONTRACT_VERSION
    assert session["content_agent_version"] == ANNOTATED_AGENT_VERSION
    assert session["source_mode"] == "private_pdf_first"
    assert session["reading_sequence"][0]["source_type"] == "private_document"
    assert session["reading_sequence"][0]["source_label"] == "Your uploaded PDF"
    assert session["reading_sequence"][0]["pathly_annotation"]["read_this_way"]
    assert session["guided_exercises"][0]["source_reading_ids"] == [session["reading_sequence"][0]["reading_id"]]

    with store.connect() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "annotated_daily_sessions" in tables
        assert "annotated_reading_units" in tables
        assert "annotated_source_citations" in tables
        assert conn.execute("SELECT COUNT(*) FROM annotated_daily_sessions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotated_reading_units").fetchone()[0] == len(session["reading_sequence"])
        assert conn.execute("SELECT COUNT(*) FROM daily_sessions").fetchone()[0] == 0


def test_no_pdf_uses_public_or_generated_source_with_clear_label(tmp_path):
    record, service, _store = build_environment(tmp_path, private=False, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert session["source_mode"] == "public_resource_first"
    assert {item["source_label"] for item in session["reading_sequence"]} == {"Public learning resource"}

    record2, service2, _store2 = build_environment(tmp_path / "second", private=False, public=False)
    fallback = service2.generate_session(user_id="learner-1", plan_id=record2["plan_id"], day=1)
    assert fallback["source_mode"] == "generated_fallback"
    assert {item["source_label"] for item in fallback["reading_sequence"]} == {"Pathly-generated fallback"}


def test_annotated_session_api_is_parallel_to_v1(monkeypatch, tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    monkeypatch.setattr(pathly_server, "annotated_content_service", service, raising=False)
    client = TestClient(pathly_server.app)

    response = client.post(
        f"/api/plans/{record['plan_id']}/days/1/annotated-session",
        json={"user_id": "learner-1"},
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["contract_version"] == ANNOTATED_CONTRACT_VERSION
    assert payload["source_mode"] == "private_pdf_first"
    assert payload["reading_sequence"]

    fetched = client.get(f"/api/plans/{record['plan_id']}/days/1/annotated-session?user_id=learner-1")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["source_hash"] == payload["source_hash"]



def test_annotated_reading_progress_and_exercise_attempt_are_persisted(tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1)
    reading_id = session["reading_sequence"][0]["reading_id"]
    exercise_id = session["guided_exercises"][0]["exercise_id"]

    progress = service.update_reading(
        user_id="learner-1",
        plan_id=record["plan_id"],
        day=1,
        reading_id=reading_id,
        status="completed",
        response={"note": "The source explains retrieval before generation."},
    )
    assert progress["reading_progress"]["status"] == "completed"
    refreshed = service.get_session(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert refreshed["annotated_progress"]["completed_readings"] == 1
    assert refreshed["reading_sequence"][0]["progress_state"]["response"]["note"]

    exercise = session["guided_exercises"][0]
    answer = {"answers": {q["question_id"]: q["correct_answer"] for q in exercise["questions"]}}
    result = service.submit_exercise(
        user_id="learner-1",
        plan_id=record["plan_id"],
        day=1,
        exercise_id=exercise_id,
        answer=answer,
    )
    assert result["grading"]["score"] == 1
    assert result["grading"]["passed"] is True
    assert result["attempt"]["answer"]["grading"]["correct"] == result["grading"]["total"]


def test_annotated_progress_api_endpoints(monkeypatch, tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    monkeypatch.setattr(pathly_server, "annotated_content_service", service, raising=False)
    client = TestClient(pathly_server.app)
    created = client.post(
        f"/api/plans/{record['plan_id']}/days/1/annotated-session",
        json={"user_id": "learner-1"},
    ).json()["data"]
    reading_id = created["reading_sequence"][0]["reading_id"]
    exercise_id = created["guided_exercises"][0]["exercise_id"]

    reading_response = client.post(
        f"/api/plans/{record['plan_id']}/days/1/annotated-session/readings/{reading_id}/complete",
        json={"user_id": "learner-1", "status": "completed", "response": {"note": "read"}},
    )
    assert reading_response.status_code == 200
    assert reading_response.json()["data"]["session"]["annotated_progress"]["completed_readings"] == 1

    exercise = created["guided_exercises"][0]
    answer = {"answers": {q["question_id"]: q["correct_answer"] for q in exercise["questions"]}}
    exercise_response = client.post(
        f"/api/plans/{record['plan_id']}/days/1/annotated-session/exercises/{exercise_id}/submit",
        json={"user_id": "learner-1", "answer": answer},
    )
    assert exercise_response.status_code == 200
    assert exercise_response.json()["data"]["grading"]["score"] == 1



def test_a3_reading_contains_teaching_expansion_and_walkthrough(tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1, force=True)
    reading = session["reading_sequence"][0]
    assert session["content_agent_version"] == ANNOTATED_AGENT_VERSION
    assert "a8" in ANNOTATED_AGENT_VERSION
    assert reading["teaching_expansion"]["concept_intro"]
    assert reading["teaching_expansion"]["mental_model"]
    assert reading["teaching_expansion"]["worked_interpretation"]
    assert reading["teaching_expansion"]["common_traps"]
    assert reading["source_walkthrough"]
    assert reading["source_walkthrough"][0]["source_line"]
    assert reading["source_walkthrough"][0]["what_it_means"]
    assert reading["pathly_annotation"]["read_for"]
    assert reading["learner_task"]["minimum_words"] >= 60
    exercise = session["guided_exercises"][0]
    assert exercise["exercise_type"] == "objective_check"
    assert exercise["questions"]
    assert exercise["scoring"]["type"] == "deterministic_objective"


def test_old_annotated_session_version_is_not_reused(tmp_path):
    import uuid

    record, service, store = build_environment(tmp_path, private=True, public=True)
    current = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1, force=True)
    old = {**current, "annotated_session_id": str(uuid.uuid4()), "source_hash": "old-a1-hash", "content_agent_version": "content-agent-v2-source-first-a1"}
    store.save_session(old)
    fresh = service.get_session(user_id="learner-1", plan_id=record["plan_id"], day=1)
    assert fresh["content_agent_version"] == ANNOTATED_AGENT_VERSION
    assert fresh["source_hash"] != "old-a1-hash"
    assert fresh["teaching_expansion"] if False else fresh["reading_sequence"][0]["teaching_expansion"]



def test_source_context_uses_current_reading_and_private_chunks(tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1, force=True)
    reading = session["reading_sequence"][0]

    def chunks(user_id, document_id):
        assert user_id == "learner-1"
        assert document_id == reading["document_id"]
        return [
            {"chunk_id": "c1", "document_id": document_id, "chunk_index": 1, "page_start": 1, "page_end": 1, "text": "Before context", "word_count": 2},
            {"chunk_id": "c2", "document_id": document_id, "chunk_index": 2, "page_start": reading["page_start"], "page_end": reading["page_end"], "text": reading["clean_excerpt"] + " More context after the selected excerpt.", "word_count": 20},
            {"chunk_id": "c3", "document_id": document_id, "chunk_index": 3, "page_start": 99, "page_end": 99, "text": "Distant context", "word_count": 2},
        ]
    service.daily.documents.get_chunks = chunks
    context = service.source_context(user_id="learner-1", plan_id=record["plan_id"], day=1, reading_id=reading["reading_id"])
    assert context["reading_id"] == reading["reading_id"]
    assert context["access"]["mode"] == "private_chunk_context"
    assert context["context_chunks"]
    assert any(chunk["selected"] for chunk in context["context_chunks"])
    assert context["annotation_targets"]
    assert context["access"]["full_pdf_url"] is None


def test_source_context_api_validates_reading_membership(monkeypatch, tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    monkeypatch.setattr(pathly_server, "annotated_content_service", service, raising=False)
    client = TestClient(pathly_server.app)
    created = client.post(
        f"/api/plans/{record['plan_id']}/days/1/annotated-session",
        json={"user_id": "learner-1", "force": True},
    ).json()["data"]
    reading_id = created["reading_sequence"][0]["reading_id"]
    ok = client.get(f"/api/plans/{record['plan_id']}/days/1/annotated-session/readings/{reading_id}/source-context?user_id=learner-1")
    assert ok.status_code == 200
    assert ok.json()["data"]["reading_id"] == reading_id
    missing = client.get(f"/api/plans/{record['plan_id']}/days/1/annotated-session/readings/not-this-reading/source-context?user_id=learner-1")
    assert missing.status_code == 404



def test_a5_objective_exercise_grading_detects_wrong_answers(tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1, force=True)
    exercise = session["guided_exercises"][0]
    assert exercise["exercise_type"] == "objective_check"
    assert {q["question_type"] for q in exercise["questions"]} == {"single_choice", "true_false", "multi_select"}
    wrong = {"answers": {q["question_id"]: "wrong" for q in exercise["questions"]}}
    result = service.submit_exercise(user_id="learner-1", plan_id=record["plan_id"], day=1, exercise_id=exercise["exercise_id"], answer=wrong)
    assert result["grading"]["score"] < 1
    assert result["grading"]["passed"] is False
    assert any(not item["correct"] for item in result["grading"]["results"])


def test_a5_hotfix_objective_questions_are_domain_focused(tmp_path):
    record, service, _store = build_environment(tmp_path, private=True, public=True)
    session = service.generate_session(user_id="learner-1", plan_id=record["plan_id"], day=1, force=True)
    banned = ["Pathly", "source claim", "learning path", "recommended reading strategy", "mastery"]
    text = " " .join([
        session["checkpoint"]["prompt"],
        session["session_overview"].get("why_these_sources", ""),
        *[q.get("prompt", "") for ex in session["guided_exercises"] for q in ex.get("questions", [])],
        *[opt.get("text", "") for ex in session["guided_exercises"] for q in ex.get("questions", []) for opt in q.get("options", [])],
        *[q.get("explanation", "") for ex in session["guided_exercises"] for q in ex.get("questions", [])],
        *[r.get("pathly_annotation", {}).get("plain_explanation", "") for r in session["reading_sequence"]],
        *[r.get("pathly_annotation", {}).get("read_for", "") for r in session["reading_sequence"]],
    ])
    for phrase in banned:
        assert phrase not in text
    exercise = session["guided_exercises"][0]
    prompts = " ".join(q["prompt"] for q in exercise["questions"])
    assert "Retrieval-Augmented Generation" in prompts or "Knowledge Graph" in prompts
    assert {"definition", "mechanism", "limitation"} == set(exercise["questions"][2]["correct_answer"])


def test_source_alignment_rejects_off_topic_pdf_page_and_uses_explicit_fallback(tmp_path):
    _record, service, _store = build_environment(tmp_path, private=False, public=False)
    plan_day = {"day": 1, "total_minutes": 30, "activities": [{"concept_ids": ["AI Applications"]}]}
    evidence = [{
        "evidence_id": "xor-page", "concept_id": "AI Applications", "source_type": "private_document",
        "document_id": "doc-xor", "section_title": "XOR is not linearly separable",
        "clean_text": "XOR is not linearly separable in the original input space.", "relevance_score": 0.91,
    }]
    readings, mode = service.build_readings(
        record={"profile_snapshot": {}, "goal_text": "Learn AI"}, plan_day=plan_day, contexts=[],
        evidence=evidence, labels={"AI Applications": "AI Applications"},
    )
    assert mode == "generated_fallback"
    assert readings[0]["source_type"] == "generated_fallback"
    assert readings[0]["source_alignment"]["status"] == "generated"
    assert "specific source page" in readings[0]["source_alignment"]["reason"]


def test_source_alignment_keeps_matching_private_pdf_page(tmp_path):
    _record, service, _store = build_environment(tmp_path, private=False, public=False)
    plan_day = {"day": 1, "total_minutes": 30, "activities": [{"concept_ids": ["Gradient Descent"]}]}
    evidence = [{
        "evidence_id": "gradient-page", "concept_id": "Gradient Descent", "source_type": "private_document",
        "document_id": "doc-gradient", "section_title": "Gradient Descent Optimization",
        "clean_text": "Gradient descent updates parameters in the direction that reduces the loss.", "relevance_score": 0.88,
        "page_start": 6, "page_end": 6,
    }]
    readings, mode = service.build_readings(
        record={"profile_snapshot": {}, "goal_text": "Learn optimization"}, plan_day=plan_day, contexts=[],
        evidence=evidence, labels={"Gradient Descent": "Gradient Descent"},
    )
    assert mode == "private_pdf_first"
    assert readings[0]["source_type"] == "private_document"
    assert readings[0]["section_title"] == "Gradient Descent"
    assert readings[0]["source_alignment"]["status"] == "aligned"
    assert readings[0]["page_start"] == 6


def test_page_topic_gate_rejects_bagging_page_for_datasets(tmp_path):
    _record, service, _store = build_environment(tmp_path, private=False, public=False)
    plan_day = {"day": 1, "total_minutes": 30, "activities": [{"concept_ids": ["Datasets"]}]}
    evidence = [{
        "evidence_id": "bagging-page", "concept_id": "Datasets", "source_type": "private_document",
        "document_id": "doc-bagging", "section_title": "Bagging",
        "clean_text": "Bagging uses bootstrap resampling of the original dataset to train an ensemble.",
        "relevance_score": 0.95, "page_start": 10, "page_end": 10,
    }]
    readings, mode = service.build_readings(
        record={"profile_snapshot": {}, "goal_text": "Learn datasets"}, plan_day=plan_day, contexts=[], evidence=evidence, labels={"Datasets": "Datasets"}
    )
    assert mode == "generated_fallback"
    assert readings[0]["source_type"] == "generated_fallback"
    assert "bagging" in readings[0]["source_alignment"]["reason"].lower()

def test_related_page_sequence_keeps_aligned_nearby_pages_and_orders_them():
    from pathly_annotated_content import AnnotatedContentService
    anchor = {"document_id": "doc-1", "page_start": 5, "page_end": 5, "section_title": "Gradient Descent", "clean_text": "Gradient descent updates parameters.", "source_alignment": {"status": "aligned", "score": 0.9}}
    candidates = [
        {**anchor, "evidence_id": "p5"},
        {"document_id": "doc-1", "page_start": 4, "page_end": 4, "section_title": "Gradient Descent", "clean_text": "A loss function measures error.", "source_alignment": {"status": "aligned", "score": 0.8}, "evidence_id": "p4"},
        {"document_id": "doc-1", "page_start": 6, "page_end": 6, "section_title": "Gradient Descent", "clean_text": "The learning rate controls step size.", "source_alignment": {"status": "aligned", "score": 0.82}, "evidence_id": "p6"},
        {"document_id": "doc-1", "page_start": 12, "page_end": 12, "section_title": "Bagging", "clean_text": "Bagging resamples datasets.", "source_alignment": {"status": "rejected", "score": 0.1}, "evidence_id": "p12"},
    ]
    sequence = AnnotatedContentService.related_page_sequence(anchor, candidates, "Gradient Descent")
    assert [item["page_start"] for item in sequence] == [4, 5, 6]
    assert [item["role"] for item in sequence] == ["context_before", "anchor", "context_after"]

