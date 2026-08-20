from full_lecture_generator import generate_full_lecture, generate_full_lecture_from_daily, prepare_evidence, regenerate_full_lecture_section


def test_prepare_evidence_removes_metadata_noise_and_bounds_text():
    result = prepare_evidence("Author alice@example.com explains retrieval. " + "word " * 300)
    assert "alice@example.com" not in result["clean_text"]
    assert len(result["clean_text"]) <= 901
    assert "bounded_excerpt" in result["quality_flags"]


def test_generator_covers_sources_and_preserves_time_budget(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = {
        "contract_version": "annotated-session-v1", "annotated_session_id": "a1",
        "path_id": "p1", "plan_id": "pl1", "day": 1, "scheduled_minutes": 40,
        "session_overview": {"title": "Neural Networks", "goal_for_today": "Understand layers"},
        "reading_sequence": [
            {"reading_id": "r1", "citation_id": "c1", "source_type": "private_document",
             "linked_concept_ids": ["neural_networks"], "section_title": "Layers",
             "document_id": "private-doc-1", "document_title": "Neural notes.pdf", "page_start": 4, "page_end": 5,
             "estimated_minutes": 20, "clean_excerpt": "Layers transform representations.",
             "teaching_expansion": {"concept_intro": "A layer transforms an input representation.", "worked_interpretation": "A dense layer combines inputs.", "common_traps": ["A layer is not the whole model."], "why_it_matters": "Layers compose into models."},
             "pathly_annotation": {"plain_explanation": "Layers are composable transformations."}},
            {"reading_id": "r2", "citation_id": "c2", "source_type": "public_rag",
             "linked_concept_ids": ["activation"], "section_title": "Activation", "estimated_minutes": 20,
             "clean_excerpt": "Activation functions introduce nonlinearity.", "teaching_expansion": {}, "pathly_annotation": {}},
        ],
        "citations": [{"citation_id": "c1"}, {"citation_id": "c2"}],
    }
    lecture = generate_full_lecture(session)
    assert lecture["contract_version"] == "full-lecture-v3"
    assert len(lecture["lecture_sections"]) == 2
    assert sum(s["estimated_minutes"] for s in lecture["lecture_sections"]) == 40
    assert lecture["practice_set"]["items"]
    assert lecture["lecture_sections"][0]["document_id"] == "private-doc-1"
    assert lecture["lecture_sections"][0]["page_start"] == 4
    assert [page["page_start"] for page in lecture["lecture_sections"][0]["page_sequence"]] == [4, 5]
    assert len(lecture["lecture_sections"][0]["page_led_lesson"]["page_sequence_guide"]) == 2
    page_led = lecture["lecture_sections"][0]["page_led_lesson"]
    assert page_led["guided_reading"]["walkthrough"]
    assert page_led["knowledge_check"]["expected_elements"]
    assert sum(item["minutes"] for item in page_led["time_plan"]) == 20
    assert lecture["generation_metadata"]["generation_mode"] == "fallback"



def test_daily_session_fallback_keeps_full_lecture_reachable():
    lecture = generate_full_lecture_from_daily({
        "content_id": "d1", "path_id": "path", "plan_id": "plan", "day": 1, "scheduled_minutes": 20,
        "session_overview": {"title": "Gradient descent", "opening_hook": "Reduce a loss."},
        "required_resources": [{"resource_id": "r1", "document_id": "private-gradient-notes", "title": "Gradient notes.pdf",
                                "reading_scope": {"page_start": 3, "page_end": 4}}],
        "study_blocks": [{"block_id": "b1", "title": "Gradient descent", "estimated_minutes": 20,
                          "concept_ids": ["gradient_descent"], "content": {"resource_id": "r1", "explanation": "Update parameters using gradients."}}],
    })
    assert lecture["lecture_sections"][0]["title"] == "Gradient descent"
    assert lecture["lecture_sections"][0]["document_id"] == "private-gradient-notes"
    assert lecture["lecture_sections"][0]["page_start"] == 3
    assert lecture["lecture_sections"][0]["page_led_lesson"]["time_plan"]
    assert lecture["generation_metadata"]["cache_status"] == "daily_session_fallback"



def test_page_led_time_plan_preserves_very_short_section_budget():
    from full_lecture_generator import _time_plan
    assert _time_plan(1) == [{"phase": "Focused study", "minutes": 1}]


def test_live_quality_gate_rejects_meta_instructional_content():
    import pytest
    from full_lecture_generator import _validate_live_lesson
    thin_meta = {
        "page_role": "This page names Linear Separability.",
        "concept_explanation": {"overview": "Thin", "mechanism": "Thin", "assumptions_and_boundaries": "Thin", "concrete_example": "Thin"},
        "prerequisite_recap": {"title": "Recall", "content": "Locate the title and identify what goes in."},
        "guided_reading": {"opening_question": "What is it?", "observation_steps": [], "walkthrough": [{"source_text": "linear", "teaching_note": "This line is evidence."}]},
        "key_terms": [],
        "worked_example": {"scenario": "Example", "steps": ["one"], "solution": "A correct explanation."},
        "knowledge_check": {"prompt": "Repeat it", "expected_elements": []},
        "transition": "Continue",
    }
    with pytest.raises(ValueError):
        _validate_live_lesson("Linear Separability", thin_meta, 30)


def test_live_quality_gate_accepts_substantive_domain_teaching():
    from full_lecture_generator import _validate_live_lesson
    explanation = " ".join(["A linear classifier computes a weighted sum and compares it with a threshold."] * 45)
    lesson = {
        "page_role": "The page demonstrates why XOR cannot be divided by one straight decision boundary.",
        "concept_explanation": {"overview": explanation, "mechanism": explanation, "assumptions_and_boundaries": explanation, "concrete_example": explanation},
        "prerequisite_recap": {"title": "Linear decision boundaries", "content": explanation},
        "guided_reading": {"opening_question": "Why does every straight boundary misclassify one XOR point?", "observation_steps": ["The positive points occupy opposite corners."], "walkthrough": [{"source_text": "XOR is not linearly separable", "teaching_note": explanation}, {"source_text": "Original x space", "teaching_note": explanation}]},
        "key_terms": [{"term": "decision boundary", "meaning": explanation}],
        "worked_example": {"scenario": "Classify the four XOR inputs.", "steps": ["Plot the four inputs.", "Assign the XOR labels.", "Test every straight-line partition."], "solution": explanation},
        "knowledge_check": {"prompt": "Explain why one line fails on XOR.", "expected_elements": ["opposite corners", "single line"]},
        "transition": "A hidden nonlinear transformation can remap the four points before classification.",
    }
    _validate_live_lesson("Linear Separability", lesson, 30)



def test_generated_fallback_is_not_exposed_as_a_source(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    lecture = generate_full_lecture({
        "contract_version": "annotated-session-v1", "annotated_session_id": "fallback-only",
        "path_id": "p", "plan_id": "pl", "day": 1, "scheduled_minutes": 20,
        "session_overview": {"title": "AI Applications"},
        "reading_sequence": [{
            "reading_id": "generated", "source_type": "generated_fallback",
            "section_title": "AI Applications", "linked_concept_ids": ["ai_applications"],
            "estimated_minutes": 20,
            "clean_excerpt": "AI Applications is introduced here as a learning concept in your path. This fallback source is generated because no suitable source page could be matched.",
            "teaching_expansion": {"concept_intro": "AI applications use models to perform bounded tasks."},
            "pathly_annotation": {},
        }], "citations": [],
    })
    section = lecture["lecture_sections"][0]
    assert section["source_grounding"] == {"has_real_source": False, "source_type": "none"}
    assert section["source_excerpt"] == ""
    assert section["source_refs"] == []
    assert section["document_id"] is None


def test_regenerate_one_section_preserves_id_and_scheduled_topic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = {
        "contract_version": "annotated-session-v1", "annotated_session_id": "retry",
        "path_id": "p", "plan_id": "pl", "day": 1, "scheduled_minutes": 20,
        "session_overview": {"title": "Classification"},
        "reading_sequence": [{
            "reading_id": "r1", "source_type": "private_document", "section_title": "Broad AI",
            "linked_concept_ids": ["ai"], "estimated_minutes": 20,
            "clean_excerpt": "XOR is not linearly separable.",
            "document_id": "doc", "document_title": "notes.pdf", "page_start": 4,
            "teaching_expansion": {}, "pathly_annotation": {},
        }], "citations": [],
    }
    section = regenerate_full_lecture_section(session, "lecture-section-1")
    assert section["section_id"] == "lecture-section-1"
    assert section["title"].startswith("Broad AI")
    assert section["content_quality"]["status"] == "source_coverage_insufficient"




