from private_source_linking import PrivateSourceLinkResolver
from source_linking_index import ConceptSourceLinkIndex, links_from_lecture


class FakeInterpretations:
    def accepted_evidence_for_documents(self, user_id, document_ids):
        if user_id != "owner" or "private-doc" not in document_ids:
            return []
        return [{
            "document_id": "private-doc",
            "requested_term": "Neural Networks",
            "canonical_concept_id": "neural-networks",
            "private_concept_id": None,
            "chunk_ids": ["chunk-8", "chunk-9", "chunk-10"],
            "mapping_confidence": 0.94,
            "mapping_status": "accepted",
        }]


class FakeDocuments:
    def get_document(self, user_id, document_id):
        if user_id != "owner" or document_id != "private-doc":
            return None
        return {"document_id": document_id, "original_filename": "My Neural Network Notes.pdf", "parse_status": "ready"}

    def get_chunks(self, user_id, document_id):
        if self.get_document(user_id, document_id) is None:
            return []
        return [
            {"chunk_id": "chunk-8", "page_start": 8, "page_end": 8},
            {"chunk_id": "chunk-9", "page_start": 9, "page_end": 9},
            {"chunk_id": "chunk-10", "page_start": 10, "page_end": 10},
        ]


class PublicVerified:
    def resolve(self, *, concept_id, concept_name):
        return {
            "resource_id": "public-book",
            "document_id": "public-book.pdf",
            "document_title": "Public Neural Networks.pdf",
            "source_scope": "public",
            "page_sequence": [{"page_number": page, "role": "mechanism", "chunk_ids": []} for page in (12, 13)],
            "chunk_ids": [],
            "relevance_score": 1.0,
            "coverage_score": 1.0,
            "match_method": "verified",
            "match_reason": "Verified public source.",
            "review_status": "verified",
            "source_readiness": "public_chroma",
        }


def lecture():
    return {"lecture_sections": [{"section_id": "nn", "concept_id": "neural-networks", "concept_name": "Neural Networks", "title": "Neural Networks"}]}


def test_private_mapping_builds_owner_scoped_contiguous_pages():
    resolver = PrivateSourceLinkResolver(FakeInterpretations(), FakeDocuments())
    candidates = resolver.resolve(user_id="owner", document_ids=["private-doc"], concept_id="neural-networks", concept_name="Neural Networks")
    assert [page["page_number"] for page in candidates[0]["page_sequence"]] == [8, 9, 10]
    assert candidates[0]["source_scope"] == "private"
    assert candidates[0]["source_readiness"] == "private_chroma"
    assert resolver.resolve(user_id="other", document_ids=["private-doc"], concept_id="neural-networks", concept_name="Neural Networks") == []


def test_verified_public_stays_primary_and_private_is_supplemental(tmp_path):
    resolver = PrivateSourceLinkResolver(FakeInterpretations(), FakeDocuments())
    links = links_from_lecture(lecture(), verified_source_resolver=PublicVerified(), private_source_resolver=resolver, user_id="owner", document_ids=["private-doc"])
    assert len(links) == 2
    assert links[0]["source_scope"] == "public"
    assert links[0]["link_role"] == "primary"
    assert links[1]["source_scope"] == "private"
    assert links[1]["link_role"] == "supplemental"
    index = ConceptSourceLinkIndex(tmp_path / "s3.db")
    saved = index.replace_day("owner", "plan", 1, links)
    assert {item["link_role"] for item in saved} == {"primary", "supplemental"}
    assert index.list_day("other", "plan", 1) == []


def test_private_source_becomes_primary_when_no_public_source_is_reliable():
    resolver = PrivateSourceLinkResolver(FakeInterpretations(), FakeDocuments())
    links = links_from_lecture(lecture(), private_source_resolver=resolver, user_id="owner", document_ids=["private-doc"])
    assert len(links) == 1
    assert links[0]["source_scope"] == "private"
    assert links[0]["link_role"] == "primary"
    assert links[0]["review_status"] == "usable"


def test_unrelated_concept_does_not_receive_private_pdf():
    resolver = PrivateSourceLinkResolver(FakeInterpretations(), FakeDocuments())
    assert resolver.resolve(user_id="owner", document_ids=["private-doc"], concept_id="gradient-descent", concept_name="Gradient Descent") == []


class EmptyPrivateResolver:
    def resolve(self, **kwargs):
        return []


def test_unconfirmed_daily_private_evidence_is_not_used_by_s3_server_mode():
    daily = {"prepared_evidence": [{
        "evidence_id": "unconfirmed", "concept_id": "neural-networks",
        "document_id": "private-doc", "source_type": "private_document",
        "page_start": 8, "clean_text": "Neural networks use weighted layers.",
    }]}
    links = links_from_lecture(
        lecture(), daily, private_source_resolver=EmptyPrivateResolver(),
        user_id="owner", document_ids=["private-doc"],
    )
    assert len(links) == 1
    assert links[0]["review_status"] == "unlinked"