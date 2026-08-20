from io import BytesIO
from pathlib import Path
import sys


PATHLY_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
sys.path.insert(0, str(PATHLY_DIR))
sys.path.insert(0, str(KG_DIR))

from infra.kg_repository import KGRepository  # noqa: E402
from pathly_backend import CALIBRATED_KG, PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402
from pathly_documents import PrivateDocumentService, PrivateDocumentStore  # noqa: E402
from pathly_goal_interpretation import GoalInterpretationService, GoalInterpretationStore  # noqa: E402
from test_pathly_private_documents import make_pdf  # noqa: E402


def test_ready_private_pdf_flows_into_json_kg_mapping_and_delete_cleans_evidence(tmp_path):
    db_path = tmp_path / "integration.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    documents = PrivateDocumentStore(db_path)
    ingestion = PrivateDocumentService(
        documents,
        tmp_path / "files",
        tmp_path / "chroma",
    )
    interpretations = GoalInterpretationStore(db_path)
    service = GoalInterpretationService(interpretations, documents)
    repository = KGRepository.from_json(CALIBRATED_KG)
    service._repository = lambda: (repository, "json", None)

    document, duplicate = ingestion.create_document(
        "integration-user",
        "machine-learning.pdf",
        BytesIO(make_pdf("Machine Learning uses data to improve predictions.")),
    )
    assert duplicate is False
    ingestion.process_document(document["document_id"])
    assert ingestion.status(
        "integration-user",
        document["document_id"],
    )["document"]["parse_status"] == "ready"

    result = service.create(
        user_id="integration-user",
        goal_text="Learn Machine Learning",
        source_mode="private_plus_kg",
        document_selections=[
            {
                "document_id": document["document_id"],
                "role": "core",
                "included_pages": [1],
            }
        ],
    )
    mapping = next(
        item
        for item in result["canonical_concepts"]
        if item["concept_id"] == "Machine Learning"
    )
    assert mapping["chunk_ids"]
    assert result["coverage"]["all_goal_terms_in_documents"] is True
    assert interpretations.evidence(
        "integration-user",
        result["interpretation_id"],
    )

    ingestion.delete_document("integration-user", document["document_id"])
    assert interpretations.evidence(
        "integration-user",
        result["interpretation_id"],
    ) == []
