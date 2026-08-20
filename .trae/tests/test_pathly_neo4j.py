from __future__ import annotations

import pathly_neo4j


def test_query_status_reports_configuration_without_claiming_query(monkeypatch):
    monkeypatch.setenv("KG_BACKEND", "neo4j")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    status = pathly_neo4j.query_status()
    assert status["configured"] is False
    assert status["query_verified"] is False
    assert status["actual_backend"] == "unavailable"


def test_require_neo4j_rejects_json_even_when_query_is_healthy(monkeypatch):
    monkeypatch.setenv("KG_BACKEND", "json")
    monkeypatch.setattr(
        pathly_neo4j,
        "ensure_neo4j",
        lambda **kwargs: {"query_verified": True, "actual_backend": "neo4j", "reason": None},
    )
    try:
        pathly_neo4j.require_neo4j()
    except RuntimeError as exc:
        assert "KG_BACKEND=neo4j" in str(exc)
    else:
        raise AssertionError("JSON backend must not pass the production gate")


def test_require_neo4j_accepts_verified_neo4j(monkeypatch):
    monkeypatch.setenv("KG_BACKEND", "neo4j")
    expected = {"query_verified": True, "actual_backend": "neo4j", "reason": None}
    monkeypatch.setattr(pathly_neo4j, "ensure_neo4j", lambda **kwargs: expected)
    assert pathly_neo4j.require_neo4j() is expected
