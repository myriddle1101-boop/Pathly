"""Private learner-document ingestion for Pathly Stage O1."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
from typing import Any, BinaryIO
import uuid

from pathly_contract_store import PathlyContractStore
from pathly_contracts import UserDocument


MAX_PDF_BYTES = int(os.getenv("PATHLY_MAX_PDF_BYTES", str(25 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("PATHLY_MAX_PDF_PAGES", "500"))
MAX_DOCUMENT_CHUNKS = int(os.getenv("PATHLY_MAX_DOCUMENT_CHUNKS", "5000"))
MAX_PARSE_SECONDS = int(os.getenv("PATHLY_MAX_PARSE_SECONDS", "120"))
ALLOWED_PDF_MIME_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
HASH_EMBEDDING_DIMENSIONS = 96


class DocumentValidationError(ValueError):
    pass


class DocumentNotFoundError(KeyError):
    pass


class DocumentConflictError(RuntimeError):
    pass


class OCRRequiredError(RuntimeError):
    pass


def _safe_display_name(filename: str | None) -> str:
    name = Path(filename or "document.pdf").name.strip()
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return (name or "document.pdf")[:240]


def _user_key(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * HASH_EMBEDDING_DIMENSIONS
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    tokens = re.findall(r"[\w]+|[\u3400-\u9fff]", normalized, flags=re.UNICODE)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % HASH_EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        return [value / magnitude for value in vector]
    return vector


class PrivateDocumentStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        # Ensure the Stage O0 contract table exists before adding O1 tables.
        PathlyContractStore(self.db_path)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS document_ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    retryable INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_document_jobs_document
                    ON document_ingestion_jobs(document_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_start INTEGER,
                    page_end INTEGER,
                    text TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_document_chunks_owner
                    ON document_chunks(user_id, document_id, chunk_index);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _decode(value: str | None) -> dict[str, Any]:
        try:
            data = json.loads(value or "{}")
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def find_duplicate(self, user_id: str, sha256: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM user_documents
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        for row in rows:
            record = self._decode(row["document_json"])
            if record.get("sha256") == sha256:
                return self._public_record(row, record)
        return None

    def insert_document(self, document: UserDocument, created_at: str) -> dict[str, Any]:
        payload = document.to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_documents(
                    document_id, user_id, document_json, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    document.document_id,
                    document.user_id,
                    json.dumps(payload, ensure_ascii=False),
                    created_at,
                    created_at,
                ),
            )
        return self.get_document(document.user_id, document.document_id) or {}

    def update_document(self, user_id: str, document_id: str, **changes: Any) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_documents
                WHERE document_id = ? AND user_id = ? AND deleted_at IS NULL
                """,
                (document_id, user_id),
            ).fetchone()
            if not row:
                raise DocumentNotFoundError(document_id)
            payload = self._decode(row["document_json"])
            payload.update(changes)
            now = _utc_now()
            conn.execute(
                "UPDATE user_documents SET document_json = ?, updated_at = ? WHERE document_id = ?",
                (json.dumps(payload, ensure_ascii=False), now, document_id),
            )
        return self.get_document(user_id, document_id) or {}

    def get_document(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_documents
                WHERE document_id = ? AND user_id = ? AND deleted_at IS NULL
                """,
                (document_id, user_id),
            ).fetchone()
        if not row:
            return None
        return self._public_record(row, self._decode(row["document_json"]))

    def get_internal_document(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_documents WHERE document_id = ? AND deleted_at IS NULL",
                (document_id,),
            ).fetchone()
        if not row:
            return None
        payload = self._decode(row["document_json"])
        payload.update(
            {
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM user_documents
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._public_record(row, self._decode(row["document_json"])) for row in rows]

    @staticmethod
    def _public_record(row: sqlite3.Row, payload: dict[str, Any]) -> dict[str, Any]:
        public = {key: value for key, value in payload.items() if key != "storage_key"}
        public.update(
            {
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return public

    def create_job(self, user_id: str, document_id: str, mode: str = "local") -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_ingestion_jobs(
                    job_id, document_id, user_id, stage, progress, mode,
                    retryable, created_at
                ) VALUES (?, ?, ?, 'queued', 0, ?, 0, ?)
                """,
                (job_id, document_id, user_id, mode, now),
            )
        return self.get_job(user_id, document_id) or {}

    def update_job(self, job_id: str, **changes: Any) -> None:
        allowed = {
            "stage",
            "progress",
            "mode",
            "error_code",
            "error_message",
            "retryable",
            "started_at",
            "completed_at",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE document_ingestion_jobs SET {assignments} WHERE job_id = ?",
                (*values.values(), job_id),
            )

    def get_job(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM document_ingestion_jobs
                WHERE user_id = ? AND document_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, document_id),
            ).fetchone()
        return dict(row) if row else None

    def replace_chunks(
        self,
        user_id: str,
        document_id: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM document_chunks WHERE user_id = ? AND document_id = ?",
                (user_id, document_id),
            )
            conn.executemany(
                """
                INSERT INTO document_chunks(
                    chunk_id, document_id, user_id, chunk_index, page_start,
                    page_end, text, word_count, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk["chunk_id"],
                        document_id,
                        user_id,
                        chunk["chunk_index"],
                        chunk.get("page_start"),
                        chunk.get("page_end"),
                        chunk["text"],
                        chunk["word_count"],
                        json.dumps(chunk.get("metadata") or {}, ensure_ascii=False),
                        now,
                    )
                    for chunk in chunks
                ],
            )

    def get_chunks(self, user_id: str, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_chunks
                WHERE user_id = ? AND document_id = ?
                ORDER BY chunk_index
                """,
                (user_id, document_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_deleted(self, user_id: str, document_id: str) -> None:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM user_documents
                WHERE document_id = ? AND user_id = ? AND deleted_at IS NULL
                """,
                (document_id, user_id),
            ).fetchone()
            if not row:
                raise DocumentNotFoundError(document_id)
            evidence_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_concept_evidence'"
            ).fetchone()
            if evidence_table:
                conn.execute(
                    "DELETE FROM document_concept_evidence WHERE document_id = ? AND user_id = ?",
                    (document_id, user_id),
                )
            conn.execute(
                "DELETE FROM document_chunks WHERE document_id = ? AND user_id = ?",
                (document_id, user_id),
            )
            conn.execute(
                "DELETE FROM document_ingestion_jobs WHERE document_id = ? AND user_id = ?",
                (document_id, user_id),
            )
            conn.execute(
                "UPDATE user_documents SET deleted_at = ?, updated_at = ? WHERE document_id = ?",
                (now, now, document_id),
            )


class PrivateDocumentService:
    def __init__(
        self,
        store: PrivateDocumentStore,
        storage_root: str | Path,
        chroma_root: str | Path,
    ):
        self.store = store
        self.storage_root = Path(storage_root).resolve()
        self.chroma_root = Path(chroma_root).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.chroma_root.mkdir(parents=True, exist_ok=True)

    def create_document(
        self,
        user_id: str,
        filename: str | None,
        stream: BinaryIO,
        content_type: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        user_id = user_id.strip()
        if not user_id:
            raise DocumentValidationError("user_id is required")
        display_name = _safe_display_name(filename)
        if Path(display_name).suffix.lower() != ".pdf":
            raise DocumentValidationError("Only PDF files are supported in Stage O1")
        normalized_mime = (content_type or "").split(";", 1)[0].strip().lower()
        if normalized_mime and normalized_mime not in ALLOWED_PDF_MIME_TYPES:
            raise DocumentValidationError("The uploaded file MIME type is not supported")
        content = stream.read(MAX_PDF_BYTES + 1)
        if not content:
            raise DocumentValidationError("The uploaded PDF is empty")
        if len(content) > MAX_PDF_BYTES:
            raise DocumentValidationError(f"The PDF exceeds the {MAX_PDF_BYTES}-byte limit")
        if not content.startswith(b"%PDF-"):
            raise DocumentValidationError("The file content is not a valid PDF")
        digest = hashlib.sha256(content).hexdigest()
        duplicate = self.store.find_duplicate(user_id, digest)
        if duplicate:
            return duplicate, True

        document_id = str(uuid.uuid4())
        relative_key = f"{_user_key(user_id)}/{document_id}/original.pdf"
        target = self._safe_storage_path(relative_key)
        target.parent.mkdir(parents=True, exist_ok=False)
        target.write_bytes(content)
        document = UserDocument(
            document_id=document_id,
            user_id=user_id,
            display_name=display_name,
            file_type="pdf",
            storage_key=relative_key,
            sha256=digest,
            size_bytes=len(content),
        )
        try:
            record = self.store.insert_document(document, _utc_now())
            self.store.create_job(user_id, document_id)
        except Exception:
            shutil.rmtree(target.parent, ignore_errors=True)
            raise
        return record, False

    def process_document(self, document_id: str) -> None:
        document = self.store.get_internal_document(document_id)
        if not document:
            return
        user_id = document["user_id"]
        job = self.store.get_job(user_id, document_id)
        if not job:
            return
        job_id = job["job_id"]
        self.store.update_job(
            job_id,
            stage="parsing",
            progress=10,
            started_at=_utc_now(),
            error_code=None,
            error_message=None,
            retryable=0,
        )
        try:
            chunks, page_count, doc_type = self._parse_pdf(
                self._safe_storage_path(document["storage_key"]),
                document_id,
            )
            self.store.replace_chunks(user_id, document_id, chunks)
            self.store.update_document(
                user_id,
                document_id,
                parse_status="parsed",
                index_status="indexing",
                page_count=page_count,
                language=None,
                doc_type=doc_type,
                chunk_count=len(chunks),
            )
            self.store.update_job(job_id, stage="indexing", progress=70)
            self._index_chunks(user_id, document_id, chunks)
            self.store.update_document(
                user_id,
                document_id,
                parse_status="ready",
                index_status="ready",
                ingestion_mode="private_chroma_local_hash",
            )
            self.store.update_job(
                job_id,
                stage="ready",
                progress=100,
                mode="private_chroma_local_hash",
                completed_at=_utc_now(),
                retryable=0,
            )
        except OCRRequiredError as exc:
            self.store.update_document(
                user_id,
                document_id,
                parse_status="ocr_required",
                index_status="not_indexed",
            )
            self.store.update_job(
                job_id,
                stage="ocr_required",
                progress=100,
                error_code="ocr_required",
                error_message=str(exc),
                retryable=0,
                completed_at=_utc_now(),
            )
        except Exception as exc:
            self.store.update_document(
                user_id,
                document_id,
                parse_status="failed",
                index_status="failed",
            )
            self.store.update_job(
                job_id,
                stage="failed",
                progress=100,
                error_code=type(exc).__name__,
                error_message=str(exc)[:500],
                retryable=1,
                completed_at=_utc_now(),
            )

    def retry_document(self, user_id: str, document_id: str) -> dict[str, Any]:
        document = self.store.get_document(user_id, document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        job = self.store.get_job(user_id, document_id)
        if job and job["stage"] in {"queued", "parsing", "indexing"}:
            raise DocumentConflictError("Document ingestion is already running")
        self.store.update_document(
            user_id,
            document_id,
            parse_status="queued",
            index_status="pending",
        )
        return self.store.create_job(user_id, document_id, mode="retry")

    def status(self, user_id: str, document_id: str) -> dict[str, Any]:
        document = self.store.get_document(user_id, document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        return {"document": document, "job": self.store.get_job(user_id, document_id)}

    def delete_document(self, user_id: str, document_id: str) -> None:
        internal = self.store.get_internal_document(document_id)
        if not internal or internal["user_id"] != user_id:
            raise DocumentNotFoundError(document_id)
        self._delete_index(user_id, document_id)
        target = self._safe_storage_path(internal["storage_key"])
        document_dir = target.parent.resolve()
        document_dir.relative_to(self.storage_root)
        self.store.mark_deleted(user_id, document_id)
        if document_dir != self.storage_root and document_dir.exists():
            shutil.rmtree(document_dir)

    def render_pdf_page(self, user_id: str, document_id: str, page: int) -> Path:
        """Render one owned private PDF page to a cached PNG for in-app reading."""
        document = self.store.get_internal_document(document_id)
        if not document or document.get("user_id") != user_id:
            raise DocumentNotFoundError(document_id)
        page_count = int(document.get("page_count") or 0)
        if page < 1 or (page_count and page > page_count):
            raise DocumentValidationError("Requested PDF page is outside the document range")
        source = self._safe_storage_path(document["storage_key"])
        if not source.exists():
            raise DocumentNotFoundError(document_id)
        render_dir = source.parent / "page_renders"
        render_dir.mkdir(exist_ok=True)
        target = render_dir / f"page-{int(page):04d}.png"
        if target.exists() and target.stat().st_size > 0:
            return target
        prefix = target.with_suffix("")
        try:
            subprocess.run(
                ["pdftoppm", "-f", str(int(page)), "-l", str(int(page)), "-r", "144", "-png", "-singlefile", str(source), str(prefix)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise DocumentValidationError("This PDF page could not be rendered") from exc
        if not target.exists() or target.stat().st_size == 0:
            raise DocumentValidationError("This PDF page could not be rendered")
        return target

    def _safe_storage_path(self, relative_key: str) -> Path:
        candidate = (self.storage_root / relative_key).resolve()
        candidate.relative_to(self.storage_root)
        return candidate

    def _collection_name(self, user_id: str) -> str:
        return f"pathly_private_{_user_key(user_id)}"

    def _chroma_collection(self, user_id: str):
        import chromadb

        client = chromadb.PersistentClient(path=str(self.chroma_root))
        return client.get_or_create_collection(name=self._collection_name(user_id))

    def _index_chunks(
        self,
        user_id: str,
        document_id: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        collection = self._chroma_collection(user_id)
        if not chunks:
            raise ValueError("No readable chunks were produced")
        collection.upsert(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            embeddings=[_hash_embedding(chunk["text"]) for chunk in chunks],
            metadatas=[
                {
                    "owner_key": _user_key(user_id),
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "page_start": chunk.get("page_start") or 0,
                    "page_end": chunk.get("page_end") or 0,
                    "word_count": chunk["word_count"],
                }
                for chunk in chunks
            ],
        )

    def _delete_index(self, user_id: str, document_id: str) -> None:
        try:
            collection = self._chroma_collection(user_id)
            collection.delete(where={"document_id": document_id})
        except Exception:
            # Deletion must still remove private source data and SQLite text.
            # A later maintenance pass can remove an unavailable Chroma index.
            pass

    @staticmethod
    def _parse_pdf(
        path: Path,
        document_id: str,
    ) -> tuple[list[dict[str, Any]], int, str]:
        import pdfplumber
        from stage1_adaptive_chunking import (
            chunk_lecture_notes,
            chunk_paper_book,
            chunk_slides,
            clean_raw_text,
            estimate_doc_type,
        )

        pages: list[tuple[int, str]] = []
        started = time.monotonic()
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            if page_count > MAX_PDF_PAGES:
                raise DocumentValidationError(f"The PDF exceeds the {MAX_PDF_PAGES}-page limit")
            for page_number, page in enumerate(pdf.pages, 1):
                if time.monotonic() - started > MAX_PARSE_SECONDS:
                    raise DocumentValidationError("PDF parsing exceeded the configured time limit")
                text = clean_raw_text(page.extract_text() or "")
                if text:
                    pages.append((page_number, text))
        if not pages:
            raise OCRRequiredError("No selectable text was found; this PDF requires OCR")
        combined = "\n\n".join(text for _, text in pages)
        doc_type = estimate_doc_type(combined)
        chunker = {
            "slides": chunk_slides,
            "lecture_notes": chunk_lecture_notes,
            "paper_book": chunk_paper_book,
        }[doc_type]
        chunks: list[dict[str, Any]] = []
        for page_number, page_text in pages:
            if time.monotonic() - started > MAX_PARSE_SECONDS:
                raise DocumentValidationError("PDF parsing exceeded the configured time limit")
            first_line = next(
                (line.strip() for line in page_text.splitlines() if line.strip()),
                f"Page {page_number}",
            )
            section_path = first_line[:120]
            page_chunks = chunker(page_text) or [page_text]
            for text in page_chunks:
                text = text.strip()
                if not text:
                    continue
                index = len(chunks) + 1
                if index > MAX_DOCUMENT_CHUNKS:
                    raise DocumentValidationError(f"The PDF exceeds the {MAX_DOCUMENT_CHUNKS}-chunk limit")
                chunks.append(
                    {
                        "chunk_id": f"{document_id}:{index}",
                        "chunk_index": index,
                        "page_start": page_number,
                        "page_end": page_number,
                        "text": text,
                        "word_count": len(text.split()),
                        "metadata": {"doc_type": doc_type, "section_path": section_path},
                    }
                )
        if not chunks:
            raise OCRRequiredError("No usable text chunks were found; this PDF may require OCR")
        return chunks, page_count, doc_type


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


