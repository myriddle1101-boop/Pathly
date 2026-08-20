from kg_golden_audit import classify_concept


def test_missing_xor_node_requires_relationship_review_even_with_pdf():
    result = classify_concept(
        "XOR", node_exists=False, prerequisites=[], unlocks=[],
        source_verified=True, chroma_chunks=34, chroma_has_pages=False,
    )
    assert result["node_status"] == "needs_relationship_review"
    assert result["overall_status"] == "needs_relationship_review"


def test_missing_page_metadata_keeps_source_usable_not_verified():
    result = classify_concept(
        "Neural Networks", node_exists=True, prerequisites=[], unlocks=[],
        source_verified=True, chroma_chunks=13, chroma_has_pages=False,
    )
    assert result["source_status"] == "usable"


def test_gradient_descent_reversed_dependency_is_flagged():
    result = classify_concept(
        "Gradient Descent", node_exists=True, prerequisites=["Backpropagation"], unlocks=[],
        source_verified=True, chroma_chunks=13, chroma_has_pages=True,
    )
    assert result["relationship_status"] == "needs_relationship_review"
