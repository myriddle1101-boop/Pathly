from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.append(str(Path(__file__).resolve().parents[1]))

from env_loader import load_project_env
from infra.config import GLOBAL_KG_JSON
from infra.neo4j_verify import verify_graph


ENV_KEYS_TO_REPORT = [
    "KG_BACKEND",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
]


def _reload_config() -> Any:
    import infra.config as config

    return config


def _tool_path(command: str) -> str | None:
    path = shutil.which(command)
    return str(path) if path else None


def _driver_available() -> bool:
    return importlib.util.find_spec("neo4j") is not None


def _env_keys_present(path: Path) -> dict[str, bool]:
    present = {key: False for key in ENV_KEYS_TO_REPORT}
    if not path.exists() or not path.is_file():
        return present
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in present:
                present[key] = True
    except OSError:
        pass
    return present


def _env_file_status() -> list[dict[str, Any]]:
    kg_root = Path(__file__).resolve().parents[1]
    project_root = kg_root.parent
    paths = [
        {"scope": "project_root", "path": project_root / ".env"},
        {"scope": "kg_construction", "path": kg_root / ".env"},
    ]
    return [
        {
            "scope": item["scope"],
            "path": str(item["path"]),
            "exists": item["path"].exists(),
            "keys_present": _env_keys_present(item["path"]),
        }
        for item in paths
    ]


def _bolt_reachability(uri: str, timeout_seconds: float = 1.0) -> dict[str, Any]:
    parsed = urlparse(uri)
    host = parsed.hostname
    port = parsed.port or 7687
    if not host:
        return {
            "uri": uri,
            "host": None,
            "port": port,
            "reachable": False,
            "error": "missing_host",
        }
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {
                "uri": uri,
                "host": host,
                "port": port,
                "reachable": True,
                "error": None,
            }
    except OSError as exc:
        return {
            "uri": uri,
            "host": host,
            "port": port,
            "reachable": False,
            "error": str(exc),
        }


def _environment_status() -> dict[str, Any]:
    config = _reload_config()
    return {
        "env_files": _env_file_status(),
        "kg_backend": config.KG_BACKEND,
        "neo4j_uri": config.NEO4J_URI,
        "neo4j_user": config.NEO4J_USER,
        "neo4j_database": config.NEO4J_DATABASE,
        "neo4j_password_configured": bool(config.NEO4J_PASSWORD),
        "neo4j_bolt_reachability": _bolt_reachability(config.NEO4J_URI),
        "neo4j_python_driver_installed": _driver_available(),
        "neo4j_cli": _tool_path("neo4j"),
        "cypher_shell_cli": _tool_path("cypher-shell"),
    }


def run_diagnostics(graph_path: Path, live: bool = False) -> dict[str, Any]:
    load_project_env()
    result: dict[str, Any] = {
        "graph_path": str(graph_path),
        "environment": _environment_status(),
        "dry_run_verification": verify_graph(graph_path, live=False),
        "live_verification": {
            "attempted": live,
            "passed": None,
            "error": None,
            "result": None,
        },
        "passed": True,
    }
    if not live:
        return result

    try:
        live_result = verify_graph(graph_path, live=True)
        result["live_verification"]["passed"] = live_result["passed"]
        result["live_verification"]["result"] = live_result
        result["passed"] = bool(live_result["passed"])
    except Exception as exc:
        result["live_verification"]["passed"] = False
        result["live_verification"]["error"] = str(exc)
        result["passed"] = False
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Neo4j migration readiness without mutating data.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge_graph.json")
    parser.add_argument("--live", action="store_true", help="Also connect to Neo4j and compare live counts")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_diagnostics(Path(args.graph).resolve(), live=args.live)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
