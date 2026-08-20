from source_linking_index import SOURCE_LINK_VERSION, ConceptSourceLinkIndex, links_from_lecture


def sample_lecture(concept_id="xor", name="XOR"):
    return {"lecture_sections": [{"section_id": concept_id, "concept_id": concept_id, "concept_name": name, "title": f"{name}: from source to understanding"}]}


def test_projects_ordered_pages_and_explainable_status():
    lecture = {"lecture_sections": [{
        "section_id": "xor", "concept_id": "xor", "concept_name": "XOR",
        "title": "Why XOR is not linearly separable", "document_id": "deep-learning-pdf",
        "resource_id": "deep-learning-book", "source_type": "public_rag",
        "page_sequence": [
            {"page_start": 9, "role": "mechanism", "chunk_ids": ["c9"]},
            {"page_start": 8, "role": "introduction", "chunk_ids": ["c8"]},
            {"page_start": 10, "role": "worked_example", "chunk_ids": ["c10"]},
        ],
        "source_alignment": {"score": 0.92, "reason": "XOR is named on the page."},
    }, {"section_id": "broad", "concept_id": "ai", "title": "AI Applications"}]}
    links = links_from_lecture(lecture)
    assert [page["page_number"] for page in links[0]["page_sequence"]] == [8, 9, 10]
    assert links[0]["review_status"] == "usable"
    assert links[0]["match_reason"] == "XOR is named on the page."
    assert links[0]["source_version"] == SOURCE_LINK_VERSION
    assert links[1]["review_status"] == "unlinked"
    assert links[1]["page_sequence"] == []


def test_daily_private_evidence_builds_contiguous_source_sequence():
    daily = {
        "required_resources": [{"resource_id": "private-r1", "document_id": "doc-private", "title": "Neural Networks Notes"}],
        "prepared_evidence": [
            {"evidence_id": "e8", "concept_id": "neural-networks", "document_id": "doc-private", "resource_id": "private-r1", "source_type": "private_document", "page_start": 8, "clean_text": "Neural networks combine weighted inputs."},
            {"evidence_id": "e9", "concept_id": "neural-networks", "document_id": "doc-private", "resource_id": "private-r1", "source_type": "private_document", "page_start": 9, "clean_text": "Neural networks use activation functions."},
            {"evidence_id": "e10", "concept_id": "neural-networks", "document_id": "doc-private", "resource_id": "private-r1", "source_type": "private_document", "page_start": 10, "clean_text": "Neural networks learn through gradient updates."},
        ],
    }
    link = links_from_lecture(sample_lecture("neural-networks", "Neural Networks"), daily)[0]
    assert link["review_status"] == "usable"
    assert link["source_scope"] == "private"
    assert link["document_title"] == "Neural Networks Notes"
    assert [page["page_number"] for page in link["page_sequence"]] == [8, 9, 10]


def test_unrelated_evidence_is_rejected_instead_of_showing_wrong_pdf():
    daily = {"prepared_evidence": [{"evidence_id": "food", "concept_id": "cooking", "document_id": "cookbook", "source_type": "private_document", "page_start": 4, "clean_text": "Bake bread with flour and yeast."}]}
    link = links_from_lecture(sample_lecture("neural-networks", "Neural Networks"), daily)[0]
    assert link["review_status"] == "unlinked"
    assert link["page_sequence"] == []


def test_disconnected_pages_keep_only_strongest_contiguous_run():
    daily = {"prepared_evidence": [
        {"evidence_id": "e8", "concept_id": "xor", "document_id": "doc", "page_start": 8, "clean_text": "XOR cannot be separated by one line."},
        {"evidence_id": "e9", "concept_id": "xor", "document_id": "doc", "page_start": 9, "clean_text": "XOR requires a nonlinear boundary."},
        {"evidence_id": "e20", "concept_id": "xor", "document_id": "doc", "page_start": 20, "clean_text": "XOR example appendix."},
    ]}
    link = links_from_lecture(sample_lecture(), daily)[0]
    assert [page["page_number"] for page in link["page_sequence"]] == [8, 9]


def test_index_is_owner_scoped_replaceable_and_document_deletable(tmp_path):
    index = ConceptSourceLinkIndex(tmp_path / "source-links.db")
    links = links_from_lecture({"lecture_sections": [{"concept_id": "xor", "title": "XOR", "document_id": "doc-1", "page_start": 4, "page_end": 5}]})
    saved_a = index.replace_day("user-a", "plan-1", 1, links)
    saved_b = index.replace_day("user-b", "plan-1", 1, links)
    assert len(saved_a) == len(saved_b) == 1
    assert saved_a[0]["link_id"] != saved_b[0]["link_id"]
    assert index.list_day("user-c", "plan-1", 1) == []
    assert index.delete_document("user-a", "doc-1") == 1
    assert index.list_day("user-a", "plan-1", 1) == []
    assert len(index.list_day("user-b", "plan-1", 1)) == 1
    assert index.delete_all() == 1
def test_replace_day_deduplicates_the_same_concept_source_link(tmp_path):
    index = ConceptSourceLinkIndex(tmp_path / "links.db")
    duplicate = {
        "link_id": "same-source-link",
        "concept_id": "neural-networks",
        "concept_name": "Neural Networks",
        "document_id": "document-1",
        "document_title": "Neural Networks Notes",
        "page_sequence": [{"page_number": 8, "role": "introduction", "chunk_ids": ["chunk-1"]}],
        "chunk_ids": ["chunk-1"],
        "source_scope": "private",
        "relevance_score": 0.82,
        "coverage_score": 0.68,
        "match_method": "private_concept_mapping",
        "review_status": "usable",
        "match_reason": "The page directly discusses neural networks.",
    }
    stronger = {**duplicate, "relevance_score": 0.91, "coverage_score": 0.8, "review_status": "verified"}

    saved = index.replace_day("user-1", "plan-1", 1, [duplicate, stronger])

    assert len(saved) == 1
    assert saved[0]["review_status"] == "verified"
    assert saved[0]["relevance_score"] == 0.91

class VerifiedResolver:
    def resolve(self, *, concept_id, concept_name):
        if concept_name != "XOR":
            return None
        return {
            "resource_id": "verified-resource",
            "document_id": "public:verified-resource",
            "document_title": "06_mlp.pdf",
            "source_scope": "public",
            "page_sequence": [{"page_number": page, "role": "mechanism", "chunk_ids": []} for page in range(2, 8)],
            "chunk_ids": [],
            "relevance_score": 1.0,
            "coverage_score": 1.0,
            "match_method": "s2_verified_golden_source",
            "match_reason": "Verified continuous XOR source sequence.",
            "review_status": "verified",
            "source_readiness": "offline_kg_resource",
            "golden_path_position": 2,
            "golden_path_version": "source-grounded-golden-s2-v1",
        }


def test_verified_resolver_overrides_a_weaker_daily_candidate_and_persists_metadata(tmp_path):
    daily = {"prepared_evidence": [{"evidence_id": "weak", "concept_id": "xor", "document_id": "wrong", "page_start": 99, "clean_text": "XOR appendix."}]}
    link = links_from_lecture(sample_lecture(), daily, verified_source_resolver=VerifiedResolver())[0]
    assert link["review_status"] == "verified"
    assert link["document_title"] == "06_mlp.pdf"
    assert [page["page_number"] for page in link["page_sequence"]] == [2, 3, 4, 5, 6, 7]
    assert link["source_readiness"] == "offline_kg_resource"
    index = ConceptSourceLinkIndex(tmp_path / "verified-links.db")
    saved = index.replace_day("owner", "plan", 1, [link])[0]
    assert saved["review_status"] == "verified"
    assert saved["golden_path_position"] == 2
    assert saved["golden_path_version"] == "source-grounded-golden-s2-v1"
