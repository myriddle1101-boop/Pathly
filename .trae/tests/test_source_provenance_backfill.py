from pathlib import Path

from source_linking_index import links_from_lecture
from source_provenance_backfill import SourceProvenanceBackfill


class FakeRepository:
    def __init__(self, resources):
        self.resources = resources

    def get_concept_context(self, node):
        return {"concept": {"id": node}, "resources": self.resources}

    def close(self):
        pass


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows

    def get(self, where, include):
        rows = [row for row in self.rows if row["metadata"]["resource_id"] == where["resource_id"]]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["text"] for row in rows],
            "metadatas": [row["metadata"] for row in rows],
        }


def test_missing_daily_pages_backfill_through_kg_chroma_and_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / "neural.pdf"
    pdf.write_bytes(b"%PDF test fixture")
    calls = []

    def factory(**kwargs):
        calls.append(kwargs["backend"])
        if kwargs["backend"] == "neo4j":
            raise RuntimeError("Neo4j unavailable")
        return FakeRepository([{"id": "resource-neural", "title": "Neural Network Slides", "path": str(pdf)}])

    monkeypatch.setenv("NEO4J_PASSWORD", "configured")
    backfill = SourceProvenanceBackfill(
        tmp_path,
        tmp_path / "kg.json",
        kg_factory=factory,
        chroma_collection=FakeCollection([
            {
                "id": "chunk-neural",
                "text": "Neural networks combine weighted inputs, activation functions, and gradient updates.",
                "metadata": {"resource_id": "resource-neural", "concept_name": "Neural Networks"},
            }
        ]),
        page_loader=lambda _: [
            "Course administration and grading policy.",
            "Neural networks combine weighted inputs and activation functions.",
            "Neural networks learn weights through gradient updates.",
        ],
    )
    lecture = {"lecture_sections": [{
        "section_id": "neural",
        "concept_id": "Neural Networks",
        "concept_name": "Neural Networks",
        "title": "Neural Networks",
    }]}
    link = links_from_lecture(lecture, {}, backfill)[0]
    assert calls == ["neo4j", "json"]
    assert link["review_status"] == "usable"
    assert link["resource_id"] == "resource-neural"
    assert link["document_id"] == "public:resource-neural"
    assert [page["page_number"] for page in link["page_sequence"]] == [2, 3]
    assert link["match_method"] == "json_resource_chroma_pdf_backfill"


def test_final_unlinked_only_after_backfill_has_no_page_match(tmp_path):
    pdf = tmp_path / "unrelated.pdf"
    pdf.write_bytes(b"%PDF test fixture")
    backfill = SourceProvenanceBackfill(
        tmp_path,
        tmp_path / "kg.json",
        kg_factory=lambda **_: FakeRepository([{"id": "resource-x", "path": str(pdf)}]),
        chroma_collection=FakeCollection([
            {
                "id": "chunk-x",
                "text": "Neural networks and activation functions.",
                "metadata": {"resource_id": "resource-x"},
            }
        ]),
        page_loader=lambda _: ["A recipe for bread and soup.", "Travel notes and hotel details."],
    )
    lecture = {"lecture_sections": [{
        "section_id": "neural",
        "concept_id": "Neural Networks",
        "concept_name": "Neural Networks",
        "title": "Neural Networks",
    }]}
    link = links_from_lecture(lecture, {}, backfill)[0]
    assert link["review_status"] == "unlinked"
    assert link["page_sequence"] == []
