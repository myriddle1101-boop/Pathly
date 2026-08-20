from experience_source_store import ExperienceSourceStore


def test_page_level_source_requires_approved_source_and_nonempty_pages(tmp_path):
    store = ExperienceSourceStore(tmp_path / "sources.db")
    source = {"source_id": "s", "goal_id": "g", "canonical_concept_id": "c", "resource_id": "r", "document_id": "d", "document_title": "title", "source_url": "https://example.test", "license_status": "recorded", "review_status": "approved", "source_version": "v1"}
    saved = store.upsert(source, [{"chunk_id": "p1", "page_number": 1, "content_role": "definition", "text": "A sufficient page-level piece of evidence for a reviewed concept."}])
    assert saved["pages"][0]["page_number"] == 1
