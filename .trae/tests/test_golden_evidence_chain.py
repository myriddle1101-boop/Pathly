from golden_evidence_chain import KQ2_EVIDENCE_VERSION, REQUIRED_CHROMA_METADATA, _match_pages_to_chunks


def test_kq2_maps_each_verified_page_to_an_indexed_chunk_even_when_chunks_span_pages():
    pages = [{"page_number": 2, "text": "XOR alternating corners cannot be separated by one line."}, {"page_number": 3, "text": "A nonlinear hidden representation changes the features."}]
    chunks = [{"id": "chunk-a", "text": "XOR alternating corners cannot be separated by one line. A nonlinear hidden representation changes the features."}]
    assert _match_pages_to_chunks(pages, chunks) == {2: ["chunk-a"], 3: ["chunk-a"]}


def test_kq2_declares_all_required_public_chroma_provenance_fields():
    assert KQ2_EVIDENCE_VERSION.startswith("kq2-")
    assert set(REQUIRED_CHROMA_METADATA) == {
        "canonical_concept_id", "resource_id", "document_id", "page_numbers",
        "chunk_id", "content_role", "source_version", "review_status",
    }
