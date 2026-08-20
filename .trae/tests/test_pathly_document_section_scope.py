from pathlib import Path
import sys

import pytest


PATHLY_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
sys.path.insert(0, str(PATHLY_DIR))
sys.path.insert(0, str(KG_DIR))

from pathly_backend import PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402
from pathly_contracts import UserDocument  # noqa: E402
from pathly_documents import PrivateDocumentStore  # noqa: E402
from pathly_goal_interpretation import (  # noqa: E402
    GoalInterpretationService,
    GoalInterpretationStore,
    GoalInterpretationValidationError,
)
from test_pathly_goal_interpretation import StubRepository  # noqa: E402


def test_section_scope_includes_and_excludes_matching_chunks(tmp_path):
    db_path = tmp_path / "sections.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    documents = PrivateDocumentStore(db_path)
    document = UserDocument(
        document_id="section-doc",
        user_id="section-user",
        display_name="sections.pdf",
        file_type="pdf",
        storage_key="private/section-doc/original.pdf",
        sha256="section",
        size_bytes=100,
        parse_status="ready",
        index_status="ready",
        page_count=2,
    )
    documents.insert_document(document, "2026-01-01T00:00:00+00:00")
    documents.replace_chunks(
        "section-user",
        "section-doc",
        [
            {
                "chunk_id": "section-doc:1",
                "chunk_index": 1,
                "page_start": 1,
                "page_end": 1,
                "text": "Neural Networks foundations.",
                "word_count": 3,
                "metadata": {"section_path": "Chapter 1 Foundations"},
            },
            {
                "chunk_id": "section-doc:2",
                "chunk_index": 2,
                "page_start": 2,
                "page_end": 2,
                "text": "Transformers applications.",
                "word_count": 2,
                "metadata": {"section_path": "Chapter 2 Applications"},
            },
        ],
    )
    service = GoalInterpretationService(
        GoalInterpretationStore(db_path),
        documents,
    )
    service._repository = lambda: (StubRepository(), "json", None)

    result = service.create(
        user_id="section-user",
        goal_text="Learn Neural Networks",
        source_mode="private_plus_kg",
        document_selections=[
            {
                "document_id": "section-doc",
                "included_sections": ["Foundations"],
                "excluded_sections": [],
            }
        ],
    )
    assert result["documents"][0]["selected_chunk_count"] == 1
    concepts = {item["concept_id"] for item in result["canonical_concepts"]}
    assert "Neural Networks" in concepts
    assert "Transformers" not in concepts

    with pytest.raises(GoalInterpretationValidationError):
        service.create(
            user_id="section-user",
            goal_text="Learn Neural Networks",
            source_mode="private_plus_kg",
            document_selections=[
                {
                    "document_id": "section-doc",
                    "included_sections": ["Foundations"],
                    "excluded_sections": ["foundations"],
                }
            ],
        )
