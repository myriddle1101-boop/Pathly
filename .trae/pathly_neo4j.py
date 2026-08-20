"""Neo4j production preflight and read-only health checks for Pathly."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _settings() -> tuple[str, str, str, str]:
    return (
        os.getenv("NEO4J_URI", "bolt://localhost:7687").strip(),
        os.getenv("NEO4J_USER", "neo4j").strip(),
        os.getenv("NEO4J_PASSWORD", "").strip(),
        os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j",
    )


def bolt_status(uri: str, timeout_seconds: float = 1.5) -> dict[str, Any]:
    parsed = urlparse(uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 7687
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {"reachable": True, "host": host, "port": port, "error": None}
    except OSError as exc:
        return {"reachable": False, "host": host, "port": port, "error": type(exc).__name__}


def query_status() -> dict[str, Any]:
    uri, user, password, database = _settings()
    backend = os.getenv("KG_BACKEND", "json").strip().lower()
    configured = bool(uri and user and password and database)
    bolt = bolt_status(uri) if uri else {"reachable": False, "host": None, "port": None, "error": "missing_uri"}
    result: dict[str, Any] = {
        "configured": configured,
        "configured_backend": backend,
        "bolt_reachable": bool(bolt["reachable"]),
        "query_verified": False,
        "actual_backend": "unavailable",
        "database": database,
        "concept_count": None,
        "reason": None,
    }
    if not configured:
        result["reason"] = "neo4j_not_configured"
        return result
    if not bolt["reachable"]:
        result["reason"] = "neo4j_bolt_unreachable"
        return result
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
        try:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                row = session.run("MATCH (c:Concept) RETURN count(c) AS count").single()
                count = int(row["count"] if row else 0)
        finally:
            driver.close()
        result.update(
            query_verified=True,
            actual_backend="neo4j",
            concept_count=count,
            reason=None,
        )
    except Exception as exc:
        result["reason"] = f"neo4j_query_failed:{type(exc).__name__}"
    return result


def _desktop_candidates() -> list[Path]:
    configured = os.getenv("PATHLY_NEO4J_DESKTOP_EXE", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path(r"D:\neo4j\Neo4j Desktop 2\Neo4j Desktop 2.exe"),
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Neo4j Desktop" / "Neo4j Desktop.exe",
        ]
    )
    return [path for path in candidates if str(path) and path.exists()]


def ensure_neo4j(*, start_desktop: bool = False, timeout_seconds: int = 45) -> dict[str, Any]:
    status = query_status()
    if status["query_verified"]:
        return status
    if start_desktop and not status["bolt_reachable"]:
        candidates = _desktop_candidates()
        if candidates:
            subprocess.Popen(
                [str(candidates[0])],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                time.sleep(2)
                status = query_status()
                if status["query_verified"]:
                    return status
    return status


def require_neo4j(*, start_desktop: bool = False, timeout_seconds: int = 45) -> dict[str, Any]:
    status = ensure_neo4j(start_desktop=start_desktop, timeout_seconds=timeout_seconds)
    if os.getenv("KG_BACKEND", "json").strip().lower() != "neo4j":
        raise RuntimeError("Formal Pathly startup requires KG_BACKEND=neo4j")
    if not status["query_verified"]:
        raise RuntimeError(f"Neo4j production preflight failed: {status['reason']}")
    return status
