import copy

import pytest

from source_grounded_v4_generator import (
    S4_GENERATOR_VERSION,
    V4ModelResponseError,
    _decode_model_json,
    _example_contract,
    _validate_content,
    _interpret_source_pages,
    _teaching_plan,
    _verified_math_content,
    generate_source_grounded_lecture_v4,
)


def _v3():
    return {
        "contract_version": "full-lecture-v3",
        "lecture_overview": {"title": "Neural Networks"},
        "lecture_sections": [{
            "section_id": "section-neural-networks",
            "concept_id": "neural-networks",
            "concept_ids": ["neural-networks"],
            "concept_name": "Neural Networks",
            "title": "Neural Networks: from source to understanding",
            "estimated_minutes": 30,
        }],
        "generation_metadata": {"generator_version": "v3"},
    }


def _links():
    return [{
        "link_id": "link-1", "concept_id": "neural-networks",
        "concept_name": "Neural Networks", "document_id": "doc-1",
        "document_title": "Neural Networks Notes", "source_scope": "public",
        "review_status": "verified", "source_version": "source-link-s3-v1",
        "page_sequence": [
            {"page_number": 8, "role": "mechanism", "chunk_ids": ["chunk-8"]},
            {"page_number": 9, "role": "worked_example", "chunk_ids": ["chunk-9"]},
        ],
        "chunk_ids": ["chunk-8", "chunk-9"],
    }]


def _daily():
    paragraph = "A neural network transforms inputs through weighted connections and nonlinear activations. " * 12
    return {"prepared_evidence": [
        {"document_id": "doc-1", "chunk_id": "chunk-8", "page_start": 8, "page_end": 8, "clean_text": paragraph},
        {"document_id": "doc-1", "chunk_id": "chunk-9", "page_start": 9, "page_end": 9, "clean_text": paragraph},
    ]}


def _live_content(request):
    concept = request["concept"]["name"]
    detail = ("Neural networks combine weighted sums with nonlinear activation functions so layers can represent "
              "decision boundaries that a single linear model cannot express. ") * 35
    return {
        "concept_introduction": {"hook": "How can a model represent XOR?", "explanation": detail,
            "mechanism": ["Compute weighted inputs.", "Apply a nonlinear activation.", "Update weights from error."],
            "boundaries": "Without nonlinearity, stacked layers still collapse to a linear transformation."},
        "prerequisite_recap": {"title": "Weighted sums", "explanation": detail, "example": "Two inputs contribute according to their weights."},
        "page_walkthrough": [
            {"page_number": 8, "what_to_notice": "The weighted connection diagram", "explanation": detail, "connection_to_previous": "It extends a linear score."},
            {"page_number": 9, "what_to_notice": "The nonlinear boundary", "explanation": detail, "connection_to_previous": "The activation changes the representation."},
        ],
        "key_terms": [{"term": concept, "definition": detail}],
        "worked_example": {"problem": "Classify XOR.", "steps": ["Encode four inputs.", "Use hidden units.", "Combine their outputs."], "solution": detail, "why_it_works": detail},
        "objective_exercise": {"instructions": "Choose one answer.", "questions": [
            {"question_id": "q1", "type": "single_choice", "question_type": "mechanism", "assessment_target_id": "network-mechanism", "correct_reasoning": "Nonlinearity changes the representation.", "prompt": "How does a hidden activation help a neural network?",
             "options": [{"id": "a", "text": "It changes the representation before the output decision.", "correct": True, "feedback": "Correct: the hidden activation transforms features."}, {"id": "b", "text": "It only renames a class label.", "correct": False, "feedback": "A label name does not transform hidden features."}, {"id": "c", "text": "It removes all learned weights.", "correct": False, "feedback": "Weights remain part of the network computation."}],
             "explanation": "Nonlinearity lets the network create transformed features that a later output can use."},
            {"question_id": "q2", "type": "single_choice", "question_type": "misconception_discrimination", "assessment_target_id": "network-misconception", "correct_reasoning": "Capacity and optimisation are different.", "prompt": "Which statement separates network capacity from training?",
             "options": [{"id": "a", "text": "Adding layers automatically finds good weights.", "correct": False, "feedback": "Training still has to learn useful parameter values."}, {"id": "b", "text": "Architecture can represent patterns, while optimisation must find useful parameters.", "correct": True, "feedback": "Correct: representational capacity does not guarantee learned weights."}, {"id": "c", "text": "The input no longer affects the prediction.", "correct": False, "feedback": "Predictions still depend on transformed input features."}],
             "explanation": "A neural architecture supplies capacity; optimisation determines whether useful weights are learned."},
            {"question_id": "q3", "type": "single_choice", "question_type": "application_or_boundary", "assessment_target_id": "network-boundary", "correct_reasoning": "Linear compositions remain linear.", "prompt": "Why is a stack of only linear layers insufficient for XOR?",
             "options": [{"id": "a", "text": "XOR has two input values.", "correct": False, "feedback": "Two inputs alone do not create the representational limitation."}, {"id": "b", "text": "A diagram cannot show linear layers.", "correct": False, "feedback": "A diagram is unrelated to the network's capacity."}, {"id": "c", "text": "Composing linear layers remains linear without an activation.", "correct": True, "feedback": "Correct: nonlinearity is needed to change the class of representable boundaries."}],
             "explanation": "Without an activation, stacked linear transformations still behave as one linear transformation."}
        ]},
        "summary_connection": {"summary": detail, "next_concept_bridge": "Gradient descent tunes the weights."},
    }


def test_s4_generates_a_detached_source_grounded_lecture():
    original = _v3()
    before = copy.deepcopy(original)
    result = generate_source_grounded_lecture_v4(
        v3_lecture=original, source_links=_links(), daily=_daily(), user_id="user-a",
        profile={"learning_style": "hands_on"}, model_generator=_live_content,
    )
    assert original == before
    section = result["lecture_sections"][0]
    assert section["v4_status"] == "ready"
    assert [page["page_number"] for page in section["source_pages"]] == [8, 9]
    assert len(section["lecture_content"]["objective_exercise"]["questions"]) == 3
    assert result["generation_metadata"]["generator_version"] == S4_GENERATOR_VERSION
    assert result["generation_metadata"]["isolated_from_v3"] is True
    assert "publication_status" not in result["generation_metadata"]
    assert "quality_gate_passed" not in result["generation_metadata"]
    assert result["v4_status"] == "generated"


def test_s4_never_creates_a_template_when_source_is_missing():
    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=[], daily=_daily(), user_id="user-a", model_generator=_live_content,
    )
    # Learner-facing V4 omits an unsupported section rather than presenting a
    # generic template or making an otherwise usable day fail.
    assert result["lecture_sections"] == []
    assert result["generation_metadata"]["omitted_unavailable_section_count"] == 1
    assert "publication_status" not in result["generation_metadata"]
    assert "quality_gate_passed" not in result["generation_metadata"]
    assert result["v4_status"] == "unavailable"


def test_kq3_uses_approved_node_specific_fallback_when_verified_model_fails():
    def failed(_request):
        raise TimeoutError("model unavailable")

    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a", model_generator=failed,
    )
    section = result["lecture_sections"][0]
    assert section["v4_status"] == "ready"
    assert section["generation_mode"] == "approved_profile_fallback"
    assert section["fallback_reason"] == "TimeoutError"
    assert "nonlinear activations" in section["lecture_content"]["concept_introduction"]["explanation"]


def test_kq3_replaces_invalid_live_content_with_the_approved_fallback():
    content = _live_content({"concept": {"name": "Neural Networks"}})
    content["concept_introduction"]["explanation"] += " Pathly chooses this teaching method."
    content["objective_exercise"]["questions"][0]["options"][1]["correct"] = True
    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a", model_generator=lambda _request: content,
    )
    section = result["lecture_sections"][0]
    assert section["v4_status"] == "ready"
    assert section["generation_mode"] == "approved_profile_fallback"


def test_s4_requires_guidance_for_every_selected_page():
    content = _live_content({"concept": {"name": "Neural Networks"}})
    content["page_walkthrough"] = content["page_walkthrough"][:1]
    with pytest.raises(ValueError, match="every selected page"):
        _validate_content(content, "Neural Networks", 30, {8, 9})



def test_kq3_records_the_failed_live_validation_reason_on_the_fallback():
    content = _live_content({"concept": {"name": "Neural Networks"}})
    content["concept_introduction"]["explanation"] += " Pathly chooses this teaching method."
    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a", model_generator=lambda _request: content,
    )
    section = result["lecture_sections"][0]
    assert section["generation_mode"] == "approved_profile_fallback"
    assert section["fallback_reason"] == "meta-language is not allowed"


def test_s4_repair_pass_uses_original_sources_without_resending_previous_output():
    requests = []

    def repairable(request):
        requests.append(copy.deepcopy(request))
        content = _live_content(request)
        if len(requests) == 1:
            content["worked_example"]["steps"] = ["Only one incomplete step."]
        return content

    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a",
        model_generator=repairable,
    )
    section = result["lecture_sections"][0]
    assert section["v4_status"] == "ready"
    assert section["repair_pass_used"] is True
    assert len(requests) == 2
    assert requests[1]["quality_rewriter"]["validation_error"] == "worked example is incomplete"
    assert requests[1]["quality_rewriter"]["repair_targets"] == ["worked_example"]
    assert requests[1]["sources"] == requests[0]["sources"]


def test_f6_stages_separate_source_facts_from_teaching_plan():
    pages = [
        {"page_number": 3, "role": "mechanism", "text": "A neural network computes a weighted sum. ReLU(x) = max(0, x)."},
        {"page_number": 4, "role": "example", "text": "XOR needs a nonlinear hidden representation before a linear output can separate it."},
    ]
    interpretation = _interpret_source_pages(pages)
    plan = _teaching_plan(
        concept_id="neural-networks", concept_name="Neural Networks", minutes=30,
        profile={"cognitive_traits": {"abstract_thinking": 1, "logical_reasoning": 1}, "affective_defaults": {"confidence_baseline": 1, "pace_preference": "flexible"}},
        interpretation=interpretation,
    )
    assert [item["page_number"] for item in interpretation["pages"]] == [3, 4]
    assert "teaching" not in interpretation
    assert plan["source_page_numbers"] == [3, 4]
    assert plan["explanation_order"] == "concrete_first"
    assert plan["checkpoint_density"] == "high"
    assert plan["segment_size"] == "short"
    assert plan["example_contract"]["anchor_example"]["roles"] == ["introduction", "intuition", "mechanism", "worked_example"]


def test_example_contract_replaces_a_repeated_counterexample_with_a_boundary_case():
    content = _live_content({"concept": {"name": "Neural Networks"}})
    content["opening_example"] = {"scenario": "Classify XOR with a hidden layer."}
    content["counterexample"] = {"scenario": "Classify XOR with a hidden layer."}
    repaired = _example_contract(
        content,
        base={"concept_name": "Neural Networks"},
        request={"approved_teaching_profile": {"claims": [
            {"kind": "boundary", "text": "A network with only linear layers remains a linear transformation."},
            {"kind": "counterexample", "text": "A stack of linear layers cannot separate the alternating XOR corners."},
        ]}},
    )
    assert repaired["counterexample"]["scenario"] == "A stack of linear layers cannot separate the alternating XOR corners"
    assert repaired["example_plan"]["contract_version"] == "anchor-counterexample-v1"
    assert "Counterexample:" in repaired["concept_introduction"]["boundaries"]


def test_f6_model_request_has_isolated_writer_inputs():
    requests = []

    def capture(request):
        requests.append(request)
        return _live_content(request)

    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a",
        profile={"learning_style": "hands_on"}, model_generator=capture,
        content_model="day-one-test-model",
    )
    assert result["lecture_sections"][0]["v4_status"] == "ready"
    request = requests[0]
    assert "source_interpretation" in request
    assert "teaching_plan" in request
    assert "lecture_writer" in request
    assert "exercise_writer" in request
    assert request["content_model"] == "day-one-test-model"
    assert request["exercise_model"] == "day-one-test-model"
    assert result["generation_metadata"]["content_model"] == "day-one-test-model"
    assert "quality_rewriter" not in request


def test_f7_keeps_page_led_teaching_fields_for_live_and_verified_content():
    live = _live_content({"concept": {"name": "Neural Networks"}})
    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a",
        model_generator=lambda _request: live,
    )
    content = result["lecture_sections"][0]["lecture_content"]
    assert content["intuition"]
    assert content["common_mistake"]
    assert [item["page_number"] for item in content["page_walkthrough"]] == [8, 9]


def test_f8_supplies_verified_structured_math_without_ocr_guessing():
    xor = _verified_math_content("XOR")
    assert xor["display_math"]
    assert xor["matrix"]["rows"][1:] == [["0", "0", "0"], ["0", "1", "1"], ["1", "0", "1"], ["1", "1", "0"]]
    gradient = _verified_math_content("Gradient Descent")
    assert "theta" in gradient["inline_math"][0]
    assert _verified_math_content("Unverified OCR topic") == {"inline_math": [], "display_math": [], "matrix": None, "derivation_steps": []}


def test_f9_binds_every_objective_question_to_its_section_concept_and_pages():
    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a",
        model_generator=_live_content,
    )
    section = result["lecture_sections"][0]
    question = section["lecture_content"]["objective_exercise"]["questions"][0]
    assert question["section_id"] == section["section_id"]
    assert question["concept_id"] == section["concept_id"]
    assert question["page_references"] == [8, 9]
    assert question["supporting_explanation_ids"]


def test_kq3_verified_source_tries_live_generation_before_using_approved_profile_fallback():
    requests = []

    def unavailable(request):
        requests.append(request)
        raise TimeoutError("model unavailable")

    links = _links()
    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=links, daily=_daily(), user_id="user-a",
        profile={"interest_tags": ["healthcare"], "preferred_examples": ["worked examples"]},
        model_generator=unavailable,
    )
    section = result["lecture_sections"][0]
    assert len(requests) == 2
    assert section["generation_mode"] == "approved_profile_fallback"
    assert section["lecture_content"]["personalization"]["interest_usage"] == "scenario_only"


def test_kq3_live_request_includes_approved_facts_and_profile_boundaries_for_verified_sources():
    requests = []

    def capture(request):
        requests.append(request)
        return _live_content(request)

    result = generate_source_grounded_lecture_v4(
        v3_lecture=_v3(), source_links=_links(), daily=_daily(), user_id="user-a",
        profile={"interest_tags": ["computer_vision"], "preferred_examples": ["visual explanations"], "preferred_style": "example_first"},
        model_generator=capture,
    )
    assert result["lecture_sections"][0]["v4_status"] == "ready"
    request = requests[0]
    assert request["approved_teaching_profile"]["canonical_id"] == "golden:neural-networks"
    assert request["teaching_plan"]["example_context"] == "an image classification decision"
    assert "must not change approved facts" in request["teaching_plan"]["personalization_boundary"]


def test_s4_decodes_wrapped_json_and_labels_malformed_responses():
    assert _decode_model_json('```json\n{"ok": true}\n```') == {"ok": True}
    assert _decode_model_json('Result: {"ok": true}') == {"ok": True}
    with pytest.raises(V4ModelResponseError, match="model_response_not_json"):
        _decode_model_json("not json")
    with pytest.raises(V4ModelResponseError, match="model_response_invalid_json"):
        _decode_model_json('{"broken": }')
