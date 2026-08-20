import hashlib
import json
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
from infra.kg_repository import KGRepository, TopicMatch  # noqa: E402
from pathly_backend import CALIBRATED_KG, PathlyStore  # noqa: E402
from pathly_contract_store import PathlyContractStore  # noqa: E402
from pathly_contracts import UserDocument  # noqa: E402
from pathly_documents import DocumentNotFoundError, PrivateDocumentStore  # noqa: E402
from pathly_goal_interpretation import (  # noqa: E402
    GoalInterpretationService,
    GoalInterpretationStore,
    GoalInterpretationValidationError,
)


client = TestClient(pathly_server.app)


class StubRepository:
    def __init__(self):
        self.topics = {
            "Neural Networks": {"id": "Neural Networks"},
            "Transformers": {"id": "Transformers"},
        }

    def node_names(self):
        return list(self.topics)

    def get_topic(self, name):
        for topic, data in self.topics.items():
            if topic.casefold() == str(name).casefold():
                return data
        return None

    def search_topics(self, query, limit=3):
        if query == "Neural Nets System":
            return [TopicMatch("Neural Networks", 0.7, "fuzzy_match")]
        return []


@pytest.fixture()
def interpretation_env(tmp_path, monkeypatch):
    db_path = tmp_path / "interpretation.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    documents = PrivateDocumentStore(db_path)
    interpretations = GoalInterpretationStore(db_path)
    service = GoalInterpretationService(interpretations, documents)

    document = UserDocument(
        document_id="doc-a",
        user_id="user-a",
        display_name="private-course.pdf",
        file_type="pdf",
        storage_key="private/doc-a/original.pdf",
        sha256="abc",
        size_bytes=100,
        parse_status="ready",
        index_status="ready",
        page_count=2,
    )
    documents.insert_document(document, "2026-01-01T00:00:00+00:00")
    documents.replace_chunks(
        "user-a",
        "doc-a",
        [
            {
                "chunk_id": "doc-a:1",
                "chunk_index": 1,
                "page_start": 1,
                "page_end": 1,
                "text": "Neural Networks and Quantum Foo Engine are explained here.",
                "word_count": 9,
                "metadata": {},
            },
            {
                "chunk_id": "doc-a:2",
                "chunk_index": 2,
                "page_start": 2,
                "page_end": 2,
                "text": "Transformers are covered only on this page.",
                "word_count": 8,
                "metadata": {},
            },
        ],
    )
    repository = StubRepository()
    monkeypatch.setattr(service, "_repository", lambda: (repository, "json", None))
    return documents, interpretations, service


def test_page_scope_maps_canonical_and_keeps_unknown_private(interpretation_env):
    _, _, service = interpretation_env
    result = service.create(
        user_id="user-a",
        goal_text="Learn Neural Networks",
        source_mode="private_plus_kg",
        document_selections=[
            {
                "document_id": "doc-a",
                "role": "core",
                "included_pages": [1],
            }
        ],
    )
    assert result["status"] == "confirmation_required"
    assert result["documents"][0]["required"] is True
    assert result["documents"][0]["selected_chunk_count"] == 1
    canonical = {item["concept_id"] for item in result["canonical_concepts"]}
    assert "Neural Networks" in canonical
    assert "Transformers" not in canonical
    assert any(
        item["requested_term"] == "Quantum Foo Engine"
        for item in result["private_concepts"]
    )
    assert all(
        item["display_name"] == item["requested_term"]
        for item in result["private_concepts"]
    )
    assert result["coverage"]["all_goal_terms_in_documents"] is True

    private_ids = [
        item["private_concept_id"]
        for item in result["private_concepts"]
    ]
    confirmed = service.confirm(
        user_id="user-a",
        interpretation_id=result["interpretation_id"],
        accepted_private_concepts=private_ids,
    )
    assert confirmed["status"] == "confirmed"
    assert {
        item["private_concept_id"] for item in confirmed["private_concepts"]
    } == set(private_ids)


def test_private_only_reports_document_coverage_gap(interpretation_env):
    _, _, service = interpretation_env
    result = service.create(
        user_id="user-a",
        goal_text="Learn Transformers",
        source_mode="private_only",
        document_selections=[
            {
                "document_id": "doc-a",
                "included_pages": [1],
            }
        ],
    )
    assert result["coverage"]["all_goal_terms_in_documents"] is False
    assert any("do not explicitly cover" in warning for warning in result["coverage_warnings"])


def test_low_confidence_mapping_requires_explicit_decision(interpretation_env):
    _, _, service = interpretation_env
    result = service.create(
        user_id="user-a",
        goal_text="Neural Nets System",
        source_mode="kg_only",
    )
    assert result["status"] == "confirmation_required"
    assert result["confirmation_required"][0]["candidate"] == "Neural Networks"

    with pytest.raises(GoalInterpretationValidationError):
        service.confirm(
            user_id="user-a",
            interpretation_id=result["interpretation_id"],
        )
    confirmed = service.confirm(
        user_id="user-a",
        interpretation_id=result["interpretation_id"],
        confirmed_mappings={"Neural Nets System": "Neural Networks"},
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["canonical_concepts"][0]["reason"] == "user_confirmed"


def test_verified_xor_goal_expands_to_source_grounded_canonical_chain(interpretation_env):
    _, _, service = interpretation_env
    result = service.create(
        user_id="user-a",
        goal_text=(
            "I want to understand why XOR is not linearly separable and learn "
            "how neural networks, activation functions, and gradient descent solve it"
        ),
        source_mode="kg_only",
    )
    assert result["status"] == "draft"
    assert [item["concept_id"] for item in result["canonical_concepts"]] == [
        "Linear Separability",
        "XOR",
        "Neural Networks",
        "Activation Functions",
        "Gradient Descent",
    ]
    assert any(
        item["reason"].startswith("verified_public_goal_scope")
        for item in result["canonical_concepts"]
        if item["concept_id"] == "XOR"
    )


def test_scope_validation_and_user_isolation(interpretation_env):
    documents, interpretations, service = interpretation_env
    with pytest.raises(GoalInterpretationValidationError):
        service.create(
            user_id="user-a",
            goal_text="Learn Neural Networks",
            source_mode="private_plus_kg",
            document_selections=[
                {
                    "document_id": "doc-a",
                    "included_pages": [1],
                    "excluded_pages": [1],
                }
            ],
        )
    with pytest.raises(DocumentNotFoundError):
        service.create(
            user_id="user-b",
            goal_text="Learn Neural Networks",
            source_mode="private_plus_kg",
            document_selections=[{"document_id": "doc-a"}],
        )

    updated = service.update_document_scope(
        user_id="user-a",
        document_id="doc-a",
        scope={"role": "exam_scope", "included_pages": [2]},
    )
    assert updated["default_learning_scope"]["required"] is True
    assert updated["default_learning_scope"]["included_pages"] == [2]
    assert interpretations.get("user-b", "missing") is None


def test_json_kg_is_read_only_during_interpretation(tmp_path):
    db_path = tmp_path / "readonly.db"
    PathlyStore(db_path)
    PathlyContractStore(db_path)
    documents = PrivateDocumentStore(db_path)
    store = GoalInterpretationStore(db_path)
    service = GoalInterpretationService(store, documents)
    before = hashlib.sha256(CALIBRATED_KG.read_bytes()).hexdigest()
    repository = KGRepository.from_json(CALIBRATED_KG)
    service._repository = lambda: (repository, "json", None)

    result = service.create(
        user_id="readonly-user",
        goal_text="Learn Machine Learning",
        source_mode="kg_only",
    )
    after = hashlib.sha256(CALIBRATED_KG.read_bytes()).hexdigest()
    assert result["kg_source"] == "json"
    assert before == after


def test_goal_interpretation_api_persists_and_hides_other_user(
    interpretation_env,
    monkeypatch,
):
    _, store, service = interpretation_env
    monkeypatch.setattr(pathly_server, "goal_interpretation_store", store)
    monkeypatch.setattr(pathly_server, "goal_interpretation_service", service)

    created = client.post(
        "/api/goal-interpretations",
        json={
            "user_id": "user-a",
            "goal_text": "Learn Neural Networks",
            "source_mode": "private_plus_kg",
            "documents": [
                {
                    "document_id": "doc-a",
                    "role": "core",
                    "included_pages": [1],
                }
            ],
        },
    )
    assert created.status_code == 201
    interpretation_id = created.json()["data"]["interpretation_id"]
    assert client.get(
        f"/api/goal-interpretations/{interpretation_id}",
        params={"user_id": "user-a"},
    ).status_code == 200
    assert client.get(
        f"/api/goal-interpretations/{interpretation_id}",
        params={"user_id": "user-b"},
    ).status_code == 404



def test_private_concepts_can_be_explicitly_excluded_without_removing_selected_documents(interpretation_env):
    _, _, service = interpretation_env
    result = service.create(
        user_id="user-a",
        goal_text="Learn Neural Networks",
        source_mode="private_plus_kg",
        document_selections=[{"document_id": "doc-a", "role": "core", "required": True}],
    )
    private_ids = [item["private_concept_id"] for item in result["private_concepts"]]
    confirmed = service.confirm(
        user_id="user-a",
        interpretation_id=result["interpretation_id"],
        rejected_private_concepts=private_ids,
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["documents"][0]["required"] is True
    assert confirmed["private_concepts"] == []
    assert set(confirmed["user_decision"]["rejected_private_concepts"]) == set(private_ids)


def test_private_only_rejects_an_empty_confirmed_concept_scope(interpretation_env, monkeypatch):
    _, _, service = interpretation_env

    class EmptyRepository:
        def node_names(self):
            return []

        def get_topic(self, _name):
            return None

        def search_topics(self, _query, limit=3):
            return []

        def close(self):
            return None

    monkeypatch.setattr(service, "_repository", lambda: (EmptyRepository(), "json", None))
    result = service.create(
        user_id="user-a",
        goal_text="Quantum Foo Engine",
        source_mode="private_only",
        document_selections=[{"document_id": "doc-a", "role": "core", "required": True}],
    )
    private_ids = [item["private_concept_id"] for item in result["private_concepts"]]
    assert private_ids
    with pytest.raises(GoalInterpretationValidationError, match="Keep at least one concept"):
        service.confirm(
            user_id="user-a",
            interpretation_id=result["interpretation_id"],
            rejected_private_concepts=private_ids,
        )

def _public_concept_ids(interpretation):
    accepted = {
        item["concept_id"]
        for item in interpretation.get("canonical_concepts", [])
        if item.get("concept_id")
    }
    pending = {
        item["candidate"]
        for item in interpretation.get("confirmation_required", [])
        if item.get("candidate")
    }
    return accepted | pending


def test_private_materials_only_expand_never_reduce_public_goal_baseline(interpretation_env):
    _, _, service = interpretation_env
    goal = "Learn Neural Networks"
    public_baseline = service.create(
        user_id="user-a",
        goal_text=goal,
        source_mode="kg_only",
    )
    with_private_materials = service.create(
        user_id="user-a",
        goal_text=goal,
        source_mode="private_plus_kg",
        document_selections=[{"document_id": "doc-a", "role": "core", "required": True}],
    )

    baseline_ids = _public_concept_ids(public_baseline)
    augmented_ids = _public_concept_ids(with_private_materials)

    assert baseline_ids
    assert baseline_ids <= augmented_ids
    assert with_private_materials["documents"][0]["required"] is True
    assert "Transformers" in augmented_ids - baseline_ids
