from pathlib import Path
import sys

from fastapi.testclient import TestClient


PATHLY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PATHLY_DIR))

from pathly_server import app  # noqa: E402


client = TestClient(app)


def test_home_serves_pathly_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "Pathly" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_legacy_demo_assets_are_not_public():
    assert client.get("/app.js").status_code == 404
    assert client.get("/styles.css").status_code == 404


def test_health_uses_success_envelope_and_dependency_checks():
    response = client.get("/api/health", headers={"X-Request-ID": "milestone-1-test"})
    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["meta"]["request_id"] == "milestone-1-test"
    assert payload["data"]["service_ready"] is True
    assert {"service", "sqlite", "kg_json", "chromadb", "neo4j"} <= set(
        payload["data"]["dependencies"]
    )


def test_capabilities_do_not_expose_secrets_or_internal_paths():
    response = client.get("/api/capabilities")
    body = response.text.lower()
    assert response.status_code == 200
    assert "password" not in body
    assert "learner_profiles.db" not in body
    assert "chroma.sqlite3" not in body
    assert "demo_mode" not in response.json()["data"]


def test_health_distinguishes_neo4j_configuration_bolt_and_query(monkeypatch):
    monkeypatch.setattr(
        "pathly_server.neo4j_query_status",
        lambda: {
            "configured": True,
            "configured_backend": "neo4j",
            "bolt_reachable": True,
            "query_verified": True,
            "actual_backend": "neo4j",
            "database": "neo4j",
            "concept_count": 366,
            "reason": None,
        },
    )
    response = client.get("/api/health")
    assert response.status_code == 200
    neo4j = response.json()["data"]["dependencies"]["neo4j"]
    assert neo4j["configured_backend"] == "neo4j"
    assert neo4j["bolt_reachable"] is True
    assert neo4j["query_verified"] is True
    assert neo4j["actual_backend"] == "neo4j"


def test_missing_route_returns_json_error_without_breaking_service():
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers.get("x-request-id")
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "not_found"


def test_backend_and_log_files_are_not_public_assets():
    assert client.get("/pathly_server.py").status_code == 404
    assert client.get("/LOG.md").status_code == 404
