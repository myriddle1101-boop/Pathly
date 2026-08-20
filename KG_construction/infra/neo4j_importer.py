from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from env_loader import load_project_env
from infra.config import GLOBAL_KG_JSON, NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from infra.kg_repository import _maybe_json


CONCEPT_FIELDS = [
    "description",
    "difficulty_level",
    "estimated_learning_time",
    "target_audience",
    "prerequisites_summary",
    "key_sub_concepts",
    "common_misconceptions",
    "practical_applications",
]


def _as_neo4j_value(value: Any) -> Any:
    parsed = _maybe_json(value)
    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, ensure_ascii=False)
    return parsed


def _load_graph(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("neo4j Python driver is not installed. Run: pip install neo4j") from exc
    if not NEO4J_PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD is empty. Set it in .env or the current shell.")
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _apply_schema(session) -> None:
    schema_path = Path(__file__).with_name("neo4j_schema.cypher")
    statements = [part.strip() for part in schema_path.read_text(encoding="utf-8").split(";")]
    for statement in statements:
        if statement:
            session.run(statement)


def _concept_params(node: dict[str, Any]) -> dict[str, Any]:
    concept_id = node["id"]
    params = {"id": concept_id, "name": concept_id}
    for field in CONCEPT_FIELDS:
        params[field] = _as_neo4j_value(node.get(field))
    return params


def _resource_params(resource_path: Path) -> dict[str, Any]:
    resolved = resource_path.resolve()
    if resolved.exists() and resolved.is_file():
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        resource_id = digest
    else:
        digest = ""
        resource_id = str(resolved)
    return {
        "id": resource_id,
        "title": resolved.stem,
        "filename": resolved.name,
        "path": str(resolved),
        "sha256": digest,
        "doc_type": resolved.suffix.lstrip(".").lower() or "unknown",
        "source_type": "pdf" if resolved.suffix.lower() == ".pdf" else "resource",
    }


def _resolve_auto_resource_path(graph_path: Path) -> Path | None:
    if graph_path.name != "knowledge_graph.json":
        return None
    pdfs = sorted(path for path in graph_path.parent.glob("*.pdf") if path.is_file())
    if len(pdfs) != 1:
        return None
    return pdfs[0]


def _initial_stats(graph_path: Path) -> dict[str, Any]:
    stats = {
        "graph_path": str(graph_path),
        "concepts": 0,
        "prerequisite_edges": 0,
        "similarity_edges": 0,
        "resources": 0,
        "has_resource_edges": 0,
        "skipped_edges": 0,
    }
    return stats


def _count_graph(data: dict[str, Any], graph_path: Path, resource_path: Path | None = None) -> dict[str, Any]:
    stats = _initial_stats(graph_path)
    stats["concepts"] = sum(1 for node in data.get("nodes", []) if node.get("id"))
    if resource_path:
        stats["resources"] = 1
        stats["has_resource_edges"] = stats["concepts"]
    for edge in data.get("edges", []):
        if not edge.get("from") or not edge.get("to"):
            stats["skipped_edges"] += 1
        elif edge.get("relation") == "prerequisite":
            stats["prerequisite_edges"] += 1
        elif edge.get("relation") == "similarity":
            stats["similarity_edges"] += 1
        else:
            stats["skipped_edges"] += 1
    return stats


def import_graph(
    graph_path: Path,
    dry_run: bool = False,
    resource_path: Path | None = None,
    auto_resource: bool = False,
) -> dict[str, Any]:
    load_project_env()
    resolved_resource_path = resource_path
    if resolved_resource_path is None and auto_resource:
        resolved_resource_path = _resolve_auto_resource_path(graph_path)
    data = _load_graph(graph_path)
    if dry_run:
        stats = _count_graph(data, graph_path, resource_path=resolved_resource_path)
        stats["resource_path"] = str(resolved_resource_path) if resolved_resource_path else None
        stats["dry_run"] = True
        return stats

    driver = _driver()
    stats = _initial_stats(graph_path)
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            _apply_schema(session)
            for node in data.get("nodes", []):
                if not node.get("id"):
                    continue
                session.run(
                    """
                    MERGE (c:Concept {id: $id})
                    SET c.name = $name,
                        c.description = $description,
                        c.difficulty_level = $difficulty_level,
                        c.estimated_learning_time = $estimated_learning_time,
                        c.target_audience = $target_audience,
                        c.prerequisites_summary = $prerequisites_summary,
                        c.key_sub_concepts = $key_sub_concepts,
                        c.common_misconceptions = $common_misconceptions,
                        c.practical_applications = $practical_applications
                    """,
                    **_concept_params(node),
                )
                stats["concepts"] += 1

            resource_id = None
            if resolved_resource_path:
                resource = _resource_params(resolved_resource_path)
                resource_id = resource["id"]
                session.run(
                    """
                    MERGE (r:Resource {id: $id})
                    SET r.title = $title,
                        r.filename = $filename,
                        r.path = $path,
                        r.sha256 = $sha256,
                        r.doc_type = $doc_type,
                        r.source_type = $source_type
                    """,
                    **resource,
                )
                stats["resources"] = 1

                for node in data.get("nodes", []):
                    concept_id = node.get("id")
                    if not concept_id:
                        continue
                    session.run(
                        """
                        MATCH (c:Concept {id: $concept_id})
                        MATCH (r:Resource {id: $resource_id})
                        MERGE (c)-[rel:HAS_RESOURCE]->(r)
                        SET rel.relevance = $relevance,
                            rel.source = $source
                        """,
                        concept_id=concept_id,
                        resource_id=resource_id,
                        relevance=None,
                        source="neo4j_importer_resource_path",
                    )
                    stats["has_resource_edges"] += 1

            for edge in data.get("edges", []):
                source = edge.get("from")
                target = edge.get("to")
                relation = edge.get("relation")
                if not source or not target:
                    stats["skipped_edges"] += 1
                    continue
                if relation == "prerequisite":
                    session.run(
                        """
                        MATCH (a:Concept {id: $source})
                        MATCH (b:Concept {id: $target})
                        MERGE (a)-[r:PREREQUISITE_OF]->(b)
                        SET r.reason = $reason,
                            r.confidence = $confidence,
                            r.source = $edge_source
                        """,
                        source=source,
                        target=target,
                        reason=edge.get("reason", ""),
                        confidence=edge.get("confidence"),
                        edge_source=edge.get("source", "knowledge_graph_json"),
                    )
                    stats["prerequisite_edges"] += 1
                elif relation == "similarity":
                    score = edge.get("score", edge.get("similarity", 0.0))
                    try:
                        score = float(score)
                    except (TypeError, ValueError):
                        score = 0.0
                    session.run(
                        """
                        MATCH (a:Concept {id: $source})
                        MATCH (b:Concept {id: $target})
                        MERGE (a)-[r:SIMILAR_TO]->(b)
                        SET r.score = $score,
                            r.method = $method,
                            r.source = $edge_source
                        """,
                        source=source,
                        target=target,
                        score=score,
                        method=edge.get("method", "sentence_transformer"),
                        edge_source=edge.get("source", "knowledge_graph_json"),
                    )
                    stats["similarity_edges"] += 1
                else:
                    stats["skipped_edges"] += 1
    finally:
        driver.close()
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import KG JSON into Neo4j Concept graph.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge_graph.json")
    parser.add_argument(
        "--resource-path",
        default=None,
        help="Optional source PDF/resource path. When provided, create one Resource and HAS_RESOURCE edges.",
    )
    parser.add_argument(
        "--auto-resource",
        action="store_true",
        help="For a run-level knowledge_graph.json, bind the only sibling PDF as Resource when exactly one exists.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count importable nodes and edges without connecting to Neo4j")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resource_path = Path(args.resource_path).resolve() if args.resource_path else None
    stats = import_graph(
        Path(args.graph).resolve(),
        dry_run=args.dry_run,
        resource_path=resource_path,
        auto_resource=args.auto_resource,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
