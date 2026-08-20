import json

from infra.kg_review_workflow import CandidateKGWorkflow
from stage1_adaptive_chunking import attach_page_provenance


def _candidate(tmp_path):
    doc = tmp_path / "runs" / "neural" / "abc"
    doc.mkdir(parents=True)
    (doc / "knowledge_graph.json").write_text(json.dumps({
        "nodes": [{"id": "A", "name": "Concept A"}, {"id": "B", "name": "Concept B"}],
        "edges": [{"from": "A", "to": "B", "relation": "prerequisite"}],
    }), encoding="utf-8")
    (doc / "stage2a_topics_hybrid.json").write_text(json.dumps({"topics": [{"name": "Concept A"}, {"name": "Concept B"}]}), encoding="utf-8")
    (doc / "stage2b_prerequisites.json").write_text(json.dumps({"prerequisites": [{"from": "Concept A", "to": "Concept B"}]}), encoding="utf-8")
    (doc / "stage1_chunks.json").write_text(json.dumps([{"chunk_id": 1, "word_count": 8, "text": "Concept A prepares the learner for Concept B."}]), encoding="utf-8")
    (doc / "manifest.json").write_text(json.dumps({"status": "success", "document": {"file_name": "neural.pdf", "sha256": "abc"}}), encoding="utf-8")
    return doc


def test_candidate_requires_complete_approval_before_publish(tmp_path):
    workflow = CandidateKGWorkflow(tmp_path / "global")
    candidate = workflow.register(doc_dir=_candidate(tmp_path), file_name="neural.pdf", sha256="abc")
    rows = workflow.review_rows(candidate)
    assert workflow.review_summary(candidate)["publishable"] is False
    for row in rows:
        workflow.save_review(candidate_id=candidate["candidate_id"], item_type=row["item_type"], item_key=row["item_key"], decision="approved", reviewer="rater")
    assert workflow.review_summary(candidate)["publishable"] is True


def test_candidate_evaluation_reports_topic_and_prerequisite_metrics(tmp_path):
    workflow = CandidateKGWorkflow(tmp_path / "global")
    candidate = workflow.register(doc_dir=_candidate(tmp_path), file_name="neural.pdf", sha256="abc")
    result = workflow.evaluate(
        candidate=candidate,
        gold_topics={"topics": [{"name": "concept a"}, {"name": "concept b"}, {"name": "concept c"}]},
        gold_prerequisites={"prerequisites": [{"from": "concept a", "to": "concept b"}]},
        output_prefix="test",
    )
    assert result["topic_metrics"]["precision"] == 1.0
    assert result["topic_metrics"]["recall"] == 0.6667
    assert result["prerequisite_metrics"]["f1"] == 1.0
    assert result["artifacts"]["error_cases_csv"]


def test_source_evidence_and_resource_quality_are_visible(tmp_path):
    workflow = CandidateKGWorkflow(tmp_path / "global")
    candidate = workflow.register(doc_dir=_candidate(tmp_path), file_name="neural.pdf", sha256="abc")
    evidence = workflow.evidence_for_concept(candidate, "Concept A")
    assert evidence["evidence_status"] == "no_direct_candidate_evidence"
    quality = workflow.resource_quality(candidate)
    assert quality["chunk_count"] == 1
    assert quality["pdf_exists"] is False


def test_future_stage1_chunks_receive_page_provenance():
    pages = [
        {"page_number": 1, "text": "Gradient descent updates a model using the loss function."},
        {"page_number": 2, "text": "Backpropagation computes gradients for neural networks."},
    ]
    page_lists = attach_page_provenance(
        ["Gradient descent updates parameters using the loss function."], pages
    )
    assert page_lists == [[1]]
