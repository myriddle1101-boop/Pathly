from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from env_loader import load_project_env
from infra.config import GLOBAL_KG_JSON, NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from infra.neo4j_importer import import_graph
from infra.neo4j_topic_importer import build_topic_plan


FORBIDDEN_LEARNER_FIELDS = [
    "goal",
    "timeline_days",
    "prior_knowledge",
    "skill_tree",
    "learning_preferences",
    "interests",
    "mastery_vector",
    "completed_topics",
    "last_practice",
    "current_day",
]


RESOURCE_REQUIRED_FIELDS = ["id", "title", "filename", "path", "sha256", "doc_type", "source_type"]


def _load_expected(graph_path: Path, include_topics: bool = False) -> dict[str, Any]:
    expected = import_graph(graph_path, dry_run=True)
    if include_topics:
        topic_plan = build_topic_plan(graph_path)
        expected["topics"] = topic_plan["summary"]["topics_defined"]
        expected["topics_with_concepts"] = topic_plan["summary"]["topics_with_concepts"]
        expected["belongs_to_edges"] = topic_plan["summary"]["belongs_to_edges"]
        expected["topic_distribution"] = topic_plan["summary"]["topic_counts"]
    return expected


def _driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("neo4j Python driver is not installed. Run: pip install neo4j") from exc
    if not NEO4J_PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD is empty. Set it in .env or the current shell.")
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _live_counts(include_resources: bool = False, include_topics: bool = False) -> dict[str, Any]:
    driver = _driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            total_nodes = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            concept_count = session.run("MATCH (c:Concept) RETURN count(c) AS count").single()["count"]
            prerequisite_count = session.run("MATCH ()-[r:PREREQUISITE_OF]->() RETURN count(r) AS count").single()["count"]
            similarity_count = session.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS count").single()["count"]
            forbidden_result = session.run(
                """
                MATCH (n)
                WITH n, labels(n) AS labels, [field IN $fields WHERE n[field] IS NOT NULL] AS fields
                WHERE size(fields) > 0
                RETURN count(n) AS count,
                       collect({labels: labels, id: coalesce(properties(n).id, properties(n).user_id, ''), fields: fields})[..10] AS examples
                """,
                fields=FORBIDDEN_LEARNER_FIELDS,
            ).single()
            resource_count = 0
            has_resource_count = 0
            incomplete_resources: list[dict[str, Any]] = []
            topic_count = 0
            belongs_to_count = 0
            topic_distribution: list[dict[str, Any]] = []
            if include_resources:
                resource_count = session.run("MATCH (r:Resource) RETURN count(r) AS count").single()["count"]
                has_resource_count = session.run("MATCH ()-[r:HAS_RESOURCE]->() RETURN count(r) AS count").single()["count"]
                incomplete_resources = session.run(
                    """
                    MATCH (r:Resource)
                    WITH r, [field IN $fields WHERE r[field] IS NULL OR toString(r[field]) = ''] AS missing_fields
                    WHERE size(missing_fields) > 0
                    RETURN collect({id: coalesce(r.id, ''), missing_fields: missing_fields})[..10] AS examples
                    """,
                    fields=RESOURCE_REQUIRED_FIELDS,
                ).single()["examples"]
            if include_topics:
                topic_count = session.run("MATCH (t:Topic) RETURN count(t) AS count").single()["count"]
                belongs_to_count = session.run("MATCH ()-[r:BELONGS_TO]->() RETURN count(r) AS count").single()["count"]
                topic_distribution = session.run(
                    """
                    MATCH (c:Concept)-[:BELONGS_TO]->(t:Topic)
                    RETURN t.id AS id, t.name AS name, count(c) AS concept_count
                    ORDER BY concept_count DESC, name
                    """
                ).data()
    finally:
        driver.close()
    counts = {
        "total_nodes": int(total_nodes),
        "concepts": int(concept_count),
        "prerequisite_edges": int(prerequisite_count),
        "similarity_edges": int(similarity_count),
        "forbidden_learner_state_nodes": int(forbidden_result["count"]),
        "forbidden_learner_state_examples": forbidden_result["examples"],
    }
    if include_resources:
        counts.update(
            {
                "resources": int(resource_count),
                "has_resource_edges": int(has_resource_count),
                "incomplete_resources": incomplete_resources,
            }
        )
    if include_topics:
        counts.update(
            {
                "topics": int(topic_count),
                "belongs_to_edges": int(belongs_to_count),
                "topic_distribution": topic_distribution,
            }
        )
    return counts


def _distribution_to_map(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        name = row.get("name") or row.get("id") or ""
        if not name:
            continue
        summary[str(name)] = int(row.get("concept_count", 0))
    return summary


def verify_graph(
    graph_path: Path,
    live: bool = False,
    include_resources: bool = False,
    include_topics: bool = False,
    min_resources: int = 0,
    min_has_resource_edges: int = 0,
    min_topics: int = 0,
    min_belongs_to_edges: int = 0,
) -> dict[str, Any]:
    load_project_env()
    expected = _load_expected(graph_path, include_topics=include_topics)
    result: dict[str, Any] = {
        "graph_path": str(graph_path),
        "mode": "live" if live else "dry_run",
        "expected": {
            "concepts": expected["concepts"],
            "prerequisite_edges": expected["prerequisite_edges"],
            "similarity_edges": expected["similarity_edges"],
            "skipped_edges": expected["skipped_edges"],
            "forbidden_learner_state_nodes": 0,
            "min_resources": min_resources,
            "min_has_resource_edges": min_has_resource_edges,
            "min_topics": min_topics,
            "min_belongs_to_edges": min_belongs_to_edges,
        },
        "actual": None,
        "passed": True,
        "checks": [],
    }
    if include_topics:
        result["expected"].update(
            {
                "topics": expected["topics"],
                "topics_with_concepts": expected["topics_with_concepts"],
                "belongs_to_edges": expected["belongs_to_edges"],
                "topic_distribution": expected["topic_distribution"],
            }
        )
    if not live:
        result["checks"].append("dry_run_mapping_count_available")
        if include_topics:
            result["checks"].append("dry_run_topic_plan_available")
        return result

    actual = _live_counts(include_resources=include_resources, include_topics=include_topics)
    total_nodes = int(actual.get("total_nodes", actual.get("concepts", 0)))
    actual["total_nodes"] = total_nodes
    result["actual"] = actual
    result["checks"].append({"name": "total_nodes", "actual": total_nodes, "passed": total_nodes >= actual["concepts"]})
    for key in ["concepts", "prerequisite_edges", "similarity_edges"]:
        passed = actual[key] == expected[key]
        result["checks"].append({"name": key, "expected": expected[key], "actual": actual[key], "passed": passed})
        if not passed:
            result["passed"] = False
    forbidden_count = actual.get("forbidden_learner_state_nodes", 0)
    forbidden_passed = forbidden_count == 0
    result["checks"].append(
        {
            "name": "forbidden_learner_state_nodes",
            "expected": 0,
            "actual": forbidden_count,
            "passed": forbidden_passed,
            "examples": actual.get("forbidden_learner_state_examples", []),
        }
    )
    if not forbidden_passed:
        result["passed"] = False
    if include_resources:
        resource_checks = [
            ("resources", min_resources),
            ("has_resource_edges", min_has_resource_edges),
        ]
        for key, minimum in resource_checks:
            actual_value = actual.get(key, 0)
            passed = actual_value >= minimum
            result["checks"].append({"name": key, "minimum": minimum, "actual": actual_value, "passed": passed})
            if not passed:
                result["passed"] = False
        incomplete = actual.get("incomplete_resources", [])
        resources_complete = len(incomplete) == 0
        result["checks"].append(
            {
                "name": "resource_required_fields",
                "required_fields": RESOURCE_REQUIRED_FIELDS,
                "passed": resources_complete,
                "examples": incomplete,
            }
        )
        if not resources_complete:
            result["passed"] = False
    if include_topics:
        exact_topic_checks = [
            ("topics", expected["topics"]),
            ("belongs_to_edges", expected["belongs_to_edges"]),
        ]
        for key, expected_value in exact_topic_checks:
            actual_value = actual.get(key, 0)
            passed = actual_value == expected_value
            result["checks"].append({"name": key, "expected": expected_value, "actual": actual_value, "passed": passed})
            if not passed:
                result["passed"] = False

        actual_distribution = _distribution_to_map(actual.get("topic_distribution", []))
        distribution_passed = actual_distribution == expected["topic_distribution"]
        result["checks"].append(
            {
                "name": "topic_distribution",
                "expected": expected["topic_distribution"],
                "actual": actual_distribution,
                "passed": distribution_passed,
            }
        )
        if not distribution_passed:
            result["passed"] = False

        topic_checks = [
            ("topics", min_topics),
            ("belongs_to_edges", min_belongs_to_edges),
        ]
        for key, minimum in topic_checks:
            actual_value = actual.get(key, 0)
            passed = actual_value >= minimum
            result["checks"].append({"name": f"{key}_minimum", "minimum": minimum, "actual": actual_value, "passed": passed})
            if not passed:
                result["passed"] = False
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Neo4j Concept graph import counts.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to knowledge_graph.json")
    parser.add_argument("--live", action="store_true", help="Connect to Neo4j and compare live counts")
    parser.add_argument("--include-resources", action="store_true", help="Also validate Resource/HAS_RESOURCE coverage")
    parser.add_argument("--include-topics", action="store_true", help="Also validate Topic/BELONGS_TO coverage")
    parser.add_argument("--min-resources", type=int, default=0, help="Minimum expected Resource count")
    parser.add_argument("--min-has-resource-edges", type=int, default=0, help="Minimum expected HAS_RESOURCE count")
    parser.add_argument("--min-topics", type=int, default=0, help="Minimum expected Topic count")
    parser.add_argument("--min-belongs-to-edges", type=int, default=0, help="Minimum expected BELONGS_TO count")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify_graph(
        Path(args.graph).resolve(),
        live=args.live,
        include_resources=args.include_resources,
        include_topics=args.include_topics,
        min_resources=args.min_resources,
        min_has_resource_edges=args.min_has_resource_edges,
        min_topics=args.min_topics,
        min_belongs_to_edges=args.min_belongs_to_edges,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
