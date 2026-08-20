from __future__ import annotations

from pathlib import Path

from infra.config import GLOBAL_KG_JSON, KG_BACKEND
from infra.kg_repository import KGRepository


def create_kg_repository(graph_path: str | Path | None = None, backend: str | None = None):
    selected_backend = (backend or KG_BACKEND or "json").strip().lower()
    if selected_backend == "json":
        return KGRepository.from_json(graph_path or GLOBAL_KG_JSON)
    if selected_backend == "neo4j":
        from infra.neo4j_repository import Neo4jKGRepository

        return Neo4jKGRepository()
    raise ValueError(f"Unsupported KG_BACKEND: {selected_backend}")

