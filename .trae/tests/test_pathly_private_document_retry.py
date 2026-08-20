from io import BytesIO
from pathlib import Path
import sys


PATHLY_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
sys.path.insert(0, str(PATHLY_DIR))
sys.path.insert(0, str(KG_DIR))

from pathly_backend import PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402
from pathly_documents import PrivateDocumentService, PrivateDocumentStore  # noqa: E402
from test_pathly_private_documents import make_pdf  # noqa: E402


def test_failed_index_is_retryable_and_retry_finishes(tmp_path, monkeypatch):
    db_path = tmp_path / "retry.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    store = PrivateDocumentStore(db_path)
    service = PrivateDocumentService(store, tmp_path / "files", tmp_path / "chroma")
    document, _ = service.create_document(
        "retry-user",
        "retry.pdf",
        BytesIO(make_pdf("Retryable private document indexing.")),
    )
    original_index = service._index_chunks

    def fail_index(*args, **kwargs):
        raise RuntimeError("forced index failure")

    monkeypatch.setattr(service, "_index_chunks", fail_index)
    service.process_document(document["document_id"])
    failed = service.status("retry-user", document["document_id"])
    assert failed["document"]["parse_status"] == "failed"
    assert failed["job"]["stage"] == "failed"
    assert failed["job"]["retryable"] == 1

    monkeypatch.setattr(service, "_index_chunks", original_index)
    service.retry_document("retry-user", document["document_id"])
    service.process_document(document["document_id"])
    ready = service.status("retry-user", document["document_id"])
    assert ready["document"]["parse_status"] == "ready"
    assert ready["job"]["stage"] == "ready"
