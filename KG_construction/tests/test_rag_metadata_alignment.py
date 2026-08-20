import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from infra.neo4j_importer import _resource_params
from infra.rag_ingestion import build_rag_rows
from infra.rag_repository import RAGRepository


class FakeCollection:
    def __init__(self):
        self.payload = None

    def upsert(self, **kwargs):
        self.payload = kwargs


class RAGMetadataAlignmentTest(unittest.TestCase):
    def test_build_rag_rows_aligns_resource_id_with_sibling_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            graph_path = run_dir / "knowledge_graph.json"
            graph_path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
            pdf_path = run_dir / "doc.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")
            chunks_path = run_dir / "stage1_chunks.json"
            chunks_path.write_text(
                json.dumps([{"chunk_id": 1, "text": "Chunk text.", "doc_type": "slides", "word_count": 2}]),
                encoding="utf-8",
            )

            rows = build_rag_rows(chunks_path)
            resource = _resource_params(pdf_path)

            self.assertEqual(rows[0]["resource_id"], resource["id"])
            self.assertEqual(rows[0]["resource_filename"], "doc.pdf")

    def test_rag_repository_writes_resource_metadata_to_chroma(self):
        repository = object.__new__(RAGRepository)
        repository.collection = FakeCollection()
        repository._embed = lambda documents: [[0.1, 0.2] for _ in documents]

        inserted = repository.upsert_chunks(
            [
                {
                    "id": "doc-1",
                    "text": "Chunk text.",
                    "doc_name": "doc",
                    "chunk_id": 1,
                    "doc_type": "slides",
                    "resource_id": "resource-sha",
                    "resource_filename": "doc.pdf",
                    "word_count": 2,
                }
            ]
        )

        metadata = repository.collection.payload["metadatas"][0]
        self.assertEqual(inserted, 1)
        self.assertEqual(metadata["resource_id"], "resource-sha")
        self.assertEqual(metadata["resource_filename"], "doc.pdf")

    def test_rag_repository_filters_chunks_by_resource_id(self):
        repository = object.__new__(RAGRepository)
        calls = []

        def fake_query_chunks(query, top_k=5, filters=None):
            calls.append({"query": query, "top_k": top_k, "filters": filters})
            return [{"id": "chunk-1"}]

        repository.query_chunks = fake_query_chunks

        rows = repository.get_chunks_by_resource_and_topic(
            resource_id="resource-sha",
            topic_name="Neural Networks",
            top_k=3,
        )

        self.assertEqual(rows, [{"id": "chunk-1"}])
        self.assertEqual(
            calls,
            [{"query": "Neural Networks", "top_k": 3, "filters": {"resource_id": "resource-sha"}}],
        )


if __name__ == "__main__":
    unittest.main()
