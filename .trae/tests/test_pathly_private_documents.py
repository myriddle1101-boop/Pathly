from io import BytesIO
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


PATHLY_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PATHLY_DIR.parent
KG_DIR = PROJECT_DIR / "KG_construction"
sys.path.insert(0, str(PATHLY_DIR))
sys.path.insert(0, str(KG_DIR))

import pathly_server  # noqa: E402
import pathly_documents  # noqa: E402
from pathly_backend import PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402
from pathly_documents import (  # noqa: E402
    DocumentNotFoundError,
    DocumentValidationError,
    PrivateDocumentService,
    PrivateDocumentStore,
)


client = TestClient(pathly_server.app)


def make_pdf(text: str | None = None) -> bytes:
    stream = b""
    if text:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


@pytest.fixture()
def private_service(tmp_path):
    db_path = tmp_path / "pathly.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    store = PrivateDocumentStore(db_path)
    service = PrivateDocumentService(
        store,
        tmp_path / "private_files",
        tmp_path / "private_chroma",
    )
    return store, service


def test_private_pdf_ingestion_deduplicates_per_user_and_isolates_users(private_service):
    store, service = private_service
    content = make_pdf("Neural networks learn representations from examples.")
    first, duplicate = service.create_document("user-a", "lesson.pdf", BytesIO(content))
    assert duplicate is False
    assert "storage_key" not in first
    service.process_document(first["document_id"])
    status = service.status("user-a", first["document_id"])
    assert status["document"]["parse_status"] == "ready"
    assert status["document"]["index_status"] == "ready"
    assert status["document"]["chunk_count"] >= 1
    assert status["job"]["mode"] == "private_chroma_local_hash"
    assert store.get_chunks("user-a", first["document_id"])

    repeated, duplicate = service.create_document("user-a", "copy.pdf", BytesIO(content))
    assert duplicate is True
    assert repeated["document_id"] == first["document_id"]

    other, duplicate = service.create_document("user-b", "lesson.pdf", BytesIO(content))
    assert duplicate is False
    assert other["document_id"] != first["document_id"]
    service.process_document(other["document_id"])
    with pytest.raises(DocumentNotFoundError):
        service.status("user-b", first["document_id"])
    assert service._collection_name("user-a") != service._collection_name("user-b")


def test_blank_pdf_is_explicitly_marked_ocr_required(private_service):
    _, service = private_service
    document, _ = service.create_document("ocr-user", "scan.pdf", BytesIO(make_pdf()))
    service.process_document(document["document_id"])
    status = service.status("ocr-user", document["document_id"])
    assert status["document"]["parse_status"] == "ocr_required"
    assert status["document"]["index_status"] == "not_indexed"
    assert status["job"]["error_code"] == "ocr_required"


def test_delete_removes_private_file_chunks_and_index(private_service):
    store, service = private_service
    document, _ = service.create_document(
        "delete-user",
        "delete.pdf",
        BytesIO(make_pdf("This private document will be removed.")),
    )
    internal = store.get_internal_document(document["document_id"])
    source = service._safe_storage_path(internal["storage_key"])
    service.process_document(document["document_id"])
    assert source.exists()
    assert store.get_chunks("delete-user", document["document_id"])
    service.delete_document("delete-user", document["document_id"])
    assert not source.exists()
    assert store.get_document("delete-user", document["document_id"]) is None
    assert store.get_chunks("delete-user", document["document_id"]) == []
    collection = service._chroma_collection("delete-user")
    assert collection.get(where={"document_id": document["document_id"]})["ids"] == []


def test_invalid_extension_and_fake_pdf_are_rejected(private_service):
    _, service = private_service
    with pytest.raises(DocumentValidationError):
        service.create_document("user", "notes.txt", BytesIO(b"hello"))
    with pytest.raises(DocumentValidationError):
        service.create_document("user", "fake.pdf", BytesIO(b"not a pdf"))
    with pytest.raises(DocumentValidationError):
        service.create_document(
            "user", "valid.pdf", BytesIO(make_pdf("valid")), "text/plain"
        )


def test_document_api_does_not_leak_across_users(tmp_path, monkeypatch):
    db_path = tmp_path / "api.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    store = PrivateDocumentStore(db_path)
    service = PrivateDocumentService(store, tmp_path / "files", tmp_path / "chroma")
    monkeypatch.setattr(pathly_server, "document_store", store)
    monkeypatch.setattr(pathly_server, "document_service", service)

    pdf = make_pdf("A private machine learning course.")
    uploaded = client.post(
        "/api/documents",
        data={"user_id": "api-user-a"},
        files={"file": ("course.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 202
    data = uploaded.json()["data"]
    assert data["duplicate"] is False
    document_id = data["document_id"]
    status = client.get(
        f"/api/documents/{document_id}/status",
        params={"user_id": "api-user-a"},
    )
    assert status.status_code == 200
    assert status.json()["data"]["document"]["parse_status"] == "ready"

    other_user = client.get(
        f"/api/documents/{document_id}",
        params={"user_id": "api-user-b"},
    )
    assert other_user.status_code == 404
    assert client.get("/api/users/api-user-b/documents").json()["data"] == []

    duplicate = client.post(
        "/api/documents",
        data={"user_id": "api-user-a"},
        files={"file": ("again.pdf", pdf, "application/pdf")},
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["data"]["duplicate"] is True
    assert duplicate.json()["data"]["document_id"] == document_id

    deleted = client.delete(
        f"/api/documents/{document_id}",
        params={"user_id": "api-user-a"},
    )
    assert deleted.status_code == 200
    assert client.get("/api/users/api-user-a/documents").json()["data"] == []


def test_pdf_page_and_chunk_limits_fail_recoverably(private_service, monkeypatch):
    _, service = private_service
    page_limited, _ = service.create_document(
        "limit-user", "pages.pdf", BytesIO(make_pdf("one page")), "application/pdf"
    )
    monkeypatch.setattr(pathly_documents, "MAX_PDF_PAGES", 0)
    service.process_document(page_limited["document_id"])
    page_status = service.status("limit-user", page_limited["document_id"])
    assert page_status["document"]["parse_status"] == "failed"
    assert page_status["job"]["error_code"] == "DocumentValidationError"
    assert page_status["job"]["retryable"] == 1

    monkeypatch.setattr(pathly_documents, "MAX_PDF_PAGES", 500)
    monkeypatch.setattr(pathly_documents, "MAX_DOCUMENT_CHUNKS", 0)
    chunk_limited, _ = service.create_document(
        "limit-user", "chunks.pdf", BytesIO(make_pdf("one chunk")), "application/pdf"
    )
    service.process_document(chunk_limited["document_id"])
    chunk_status = service.status("limit-user", chunk_limited["document_id"])
    assert chunk_status["document"]["parse_status"] == "failed"
    assert chunk_status["job"]["error_code"] == "DocumentValidationError"
    assert chunk_status["job"]["retryable"] == 1


def test_upload_api_rejects_mime_mismatch(tmp_path, monkeypatch):
    db_path = tmp_path / "mime.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    store = PrivateDocumentStore(db_path)
    service = PrivateDocumentService(store, tmp_path / "files", tmp_path / "chroma")
    monkeypatch.setattr(pathly_server, "document_store", store)
    monkeypatch.setattr(pathly_server, "document_service", service)
    response = client.post(
        "/api/documents",
        data={"user_id": "mime-user"},
        files={"file": ("valid.pdf", make_pdf("valid"), "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_document"


def test_private_pdf_page_render_is_owned_bounded_and_cached(private_service):
    _, service = private_service
    document, _ = service.create_document(
        "render-user", "render.pdf", BytesIO(make_pdf("Page rendering keeps this source private.")), "application/pdf"
    )
    service.process_document(document["document_id"])

    image = service.render_pdf_page("render-user", document["document_id"], 1)
    assert image.exists()
    assert image.read_bytes().startswith(b"\x89PNG")
    assert service.render_pdf_page("render-user", document["document_id"], 1) == image

    with pytest.raises(DocumentNotFoundError):
        service.render_pdf_page("other-user", document["document_id"], 1)
    with pytest.raises(DocumentValidationError):
        service.render_pdf_page("render-user", document["document_id"], 2)
