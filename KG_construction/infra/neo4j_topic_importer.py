from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from env_loader import load_project_env
from infra.config import GLOBAL_KG_JSON, NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from infra.kg_repository import _maybe_json
from infra.neo4j_importer import _apply_schema


TOPIC_DEFINITIONS = [
    {
        "id": "topic_machine_learning_foundations",
        "name": "Machine Learning Foundations",
        "description": "Core machine learning concepts, learning paradigms, model behavior, and introductory foundations.",
        "keywords": [
            "machine learning",
            "learning model",
            "supervised",
            "unsupervised",
            "reinforcement learning",
            "classification",
            "regression",
            "feature",
            "dataset",
            "training",
            "probability",
            "data",
        ],
    },
    {
        "id": "topic_deep_learning",
        "name": "Deep Learning",
        "description": "Neural networks, deep architectures, representation learning, and training methods.",
        "keywords": [
            "deep learning",
            "neural",
            "backpropagation",
            "activation",
            "gradient",
            "transformer",
            "embedding",
            "attention",
            "cnn",
            "rnn",
            "softmax",
        ],
    },
    {
        "id": "topic_natural_language_processing",
        "name": "Natural Language Processing",
        "description": "Language modeling, text processing, embeddings, and NLP applications.",
        "keywords": [
            "natural language",
            "language",
            "nlp",
            "text",
            "token",
            "word",
            "sentence",
            "semantic",
            "translation",
            "bert",
            "linguistic",
            "dialog",
        ],
    },
    {
        "id": "topic_computer_vision",
        "name": "Computer Vision",
        "description": "Image analysis, convolution, visual recognition, and vision-oriented machine learning.",
        "keywords": [
            "image",
            "vision",
            "convolution",
            "kernel",
            "pooling",
            "visual",
            "object detection",
            "segmentation",
        ],
    },
    {
        "id": "topic_optimization",
        "name": "Optimization",
        "description": "Optimization methods, loss minimization, gradients, and model training dynamics.",
        "keywords": [
            "optimization",
            "gradient descent",
            "loss",
            "descent",
            "regularization",
            "objective",
            "minimize",
            "hyperparameter",
            "optimization techniques",
        ],
    },
    {
        "id": "topic_evaluation_and_generalization",
        "name": "Evaluation and Generalization",
        "description": "Model evaluation, metrics, validation, generalization, and reliability checks.",
        "keywords": [
            "evaluation",
            "metric",
            "accuracy",
            "precision",
            "recall",
            "validation",
            "generalization",
            "test",
            "benchmark",
            "grading",
        ],
    },
    {
        "id": "topic_ai_ethics_and_privacy",
        "name": "AI Ethics and Privacy",
        "description": "Fairness, privacy, security, accountability, and societal risks in AI systems.",
        "keywords": [
            "ethic",
            "fairness",
            "bias",
            "privacy",
            "security",
            "accountability",
            "responsible",
            "harm",
            "risk",
            "surveillance",
            "adversarial",
        ],
    },
    {
        "id": "topic_ai_applications",
        "name": "AI Applications",
        "description": "Applied AI systems, practical use cases, deployment contexts, and domain-specific applications.",
        "keywords": [
            "application",
            "deployment",
            "robot",
            "autonomous",
            "recommendation",
            "healthcare",
            "finance",
            "game",
            "agent",
            "assistant",
        ],
    },
]

TOPICS_BY_ID = {topic["id"]: topic for topic in TOPIC_DEFINITIONS}

DEFAULT_TOPIC = {
    "id": "topic_machine_learning_foundations",
    "name": "Machine Learning Foundations",
}

EXACT_TOPIC_OVERRIDES = {
    "abstraction boundaries": "topic_machine_learning_foundations",
    "activation functions": "topic_deep_learning",
    "activation functions in neural network architectures": "topic_deep_learning",
    "adversarial machine learning": "topic_ai_ethics_and_privacy",
    "ai applications": "topic_ai_applications",
    "ai ethics": "topic_ai_ethics_and_privacy",
    "ai tools": "topic_ai_applications",
    "artificial intelligence": "topic_machine_learning_foundations",
    "assistant conversations": "topic_ai_applications",
    "atari games": "topic_ai_applications",
    "bias in ai": "topic_ai_ethics_and_privacy",
    "bias in machine learning": "topic_ai_ethics_and_privacy",
    "chinese ai contributions": "topic_ai_applications",
    "crime and media": "topic_ai_ethics_and_privacy",
    "creativity in ai": "topic_ai_applications",
    "ethics in ai": "topic_ai_ethics_and_privacy",
    "definition and properties of lu decomposition": "topic_machine_learning_foundations",
    "design engineering": "topic_ai_applications",
    "history of ai": "topic_machine_learning_foundations",
    "homework assignments": "topic_machine_learning_foundations",
    "image analysis": "topic_computer_vision",
    "intelligence in crime": "topic_ai_ethics_and_privacy",
    "lu activation function variations and their impact": "topic_deep_learning",
    "natural language processing": "topic_natural_language_processing",
    "policing technologies": "topic_ai_ethics_and_privacy",
    "privacy in machine learning": "topic_ai_ethics_and_privacy",
    "practical learning": "topic_machine_learning_foundations",
    "python basics": "topic_machine_learning_foundations",
    "python environment": "topic_machine_learning_foundations",
    "question answering": "topic_natural_language_processing",
    "reasoning in ai": "topic_ai_applications",
    "retrieval models": "topic_natural_language_processing",
    "security models": "topic_ai_ethics_and_privacy",
    "softmax and probability in neural networks": "topic_deep_learning",
    "speech recognition": "topic_natural_language_processing",
    "surveillance technologies": "topic_ai_ethics_and_privacy",
    "technological dystopia": "topic_ai_ethics_and_privacy",
    "workforce impact": "topic_ai_ethics_and_privacy",
}

PHRASE_RULES = [
    {
        "topic_id": "topic_deep_learning",
        "patterns": [
            "activation function",
            "neural network",
            "backpropagation",
            "gradient flow",
            "gradient issues",
            "attention mechanism",
            "attention variant",
            "transformer",
            "softmax",
        ],
    },
    {
        "topic_id": "topic_natural_language_processing",
        "patterns": [
            "language model",
            "machine translation",
            "tokenization",
            "sequence model",
            "word vector",
            "dialog system",
            "language processing",
            "question answering",
            "cross-lingual",
        ],
    },
    {
        "topic_id": "topic_computer_vision",
        "patterns": [
            "image analysis",
            "computer vision",
            "convolutional kernel",
            "visual recognition",
            "segmentation",
        ],
    },
    {
        "topic_id": "topic_ai_ethics_and_privacy",
        "patterns": [
            "fairness",
            "privacy",
            "cybersecurity",
            "surveillance",
            "policing",
            "crime",
            "adversarial",
            "bias",
            "ethical",
            "ethics",
        ],
    },
    {
        "topic_id": "topic_ai_applications",
        "patterns": [
            "ai application",
            "robotics",
            "automation",
            "agent reasoning",
            "cartpole",
            "hopper dynamics",
            "assistant",
            "deployment",
        ],
    },
    {
        "topic_id": "topic_machine_learning_foundations",
        "patterns": [
            "python",
            "course project",
            "lecture structure",
            "project proposal",
            "machine learning",
            "probability theory",
        ],
    },
]



def _load_graph(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))



def _driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("neo4j Python driver is not installed. Run: pip install neo4j") from exc
    if not NEO4J_PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD is empty. Set it in .env or the current shell.")
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))



def _as_text(value: Any) -> str:
    parsed = _maybe_json(value)
    if isinstance(parsed, list):
        return " ".join(_as_text(item) for item in parsed)
    if isinstance(parsed, dict):
        return " ".join(_as_text(item) for item in parsed.values())
    return "" if parsed is None else str(parsed)



def _normalize_text(value: str) -> str:
    lowered = value.lower().replace("_", " ")
    return re.sub(r"\s+", " ", lowered).strip()



def _concept_name(node: dict[str, Any]) -> str:
    return _normalize_text(str(node.get("id", "")))



def _concept_text(node: dict[str, Any]) -> str:
    fields = [
        node.get("id"),
        node.get("description"),
        node.get("sub_topics"),
        node.get("key_sub_concepts"),
        node.get("prerequisites_summary"),
        node.get("practical_applications"),
    ]
    return _normalize_text(" ".join(_as_text(field) for field in fields))



def _contains_phrase(text: str, phrase: str) -> bool:
    return _normalize_text(phrase) in text



def _keyword_score(name_text: str, full_text: str, keywords: list[str]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for keyword in keywords:
        normalized = _normalize_text(keyword)
        if _contains_phrase(name_text, normalized):
            score += 4 if " " in normalized else 3
            matched.append(f"name:{normalized}")
        elif _contains_phrase(full_text, normalized):
            score += 2 if " " in normalized else 1
            matched.append(f"text:{normalized}")
    return score, matched



def assign_topic_with_reason(node: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    concept_name = _concept_name(node)
    full_text = _concept_text(node)

    if concept_name in EXACT_TOPIC_OVERRIDES:
        topic_id = EXACT_TOPIC_OVERRIDES[concept_name]
        topic = TOPICS_BY_ID[topic_id]
        return topic, {
            "method": "exact_override",
            "matched_rule": concept_name,
            "score_breakdown": {topic["name"]: 100},
            "matched_keywords": [concept_name],
        }

    for rule in PHRASE_RULES:
        for pattern in rule["patterns"]:
            normalized = _normalize_text(pattern)
            if _contains_phrase(concept_name, normalized):
                topic = TOPICS_BY_ID[rule["topic_id"]]
                return topic, {
                    "method": "phrase_rule",
                    "matched_rule": normalized,
                    "score_breakdown": {topic["name"]: 90},
                    "matched_keywords": [normalized],
                }

    scored = []
    for index, topic in enumerate(TOPIC_DEFINITIONS):
        score, matched = _keyword_score(concept_name, full_text, topic["keywords"])
        scored.append((score, index, topic, matched))
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored and scored[0][0] > 0:
        topic = scored[0][2]
        reason = {
            "method": "keyword_scoring",
            "matched_rule": None,
            "score_breakdown": {item[2]["name"]: item[0] for item in scored if item[0] > 0},
            "matched_keywords": scored[0][3],
        }
        return topic, reason

    default_topic = TOPICS_BY_ID[DEFAULT_TOPIC["id"]]
    return default_topic, {
        "method": "default_topic",
        "matched_rule": DEFAULT_TOPIC["id"],
        "score_breakdown": {default_topic["name"]: 0},
        "matched_keywords": [],
    }



def assign_topic(node: dict[str, Any]) -> dict[str, Any]:
    topic, _ = assign_topic_with_reason(node)
    return topic



def build_topic_plan(graph_path: Path) -> dict[str, Any]:
    data = _load_graph(graph_path)
    assignments: list[dict[str, Any]] = []
    topic_counts = {topic["id"]: 0 for topic in TOPIC_DEFINITIONS}
    topic_names = {topic["id"]: topic["name"] for topic in TOPIC_DEFINITIONS}
    method_counts: dict[str, int] = {}
    for node in data.get("nodes", []):
        concept_id = node.get("id")
        if not concept_id:
            continue
        topic, reason = assign_topic_with_reason(node)
        topic_counts[topic["id"]] += 1
        method_counts[reason["method"]] = method_counts.get(reason["method"], 0) + 1
        assignments.append(
            {
                "concept_id": concept_id,
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "assignment_method": reason["method"],
                "matched_rule": reason["matched_rule"],
                "matched_keywords": reason["matched_keywords"],
                "score_breakdown": reason["score_breakdown"],
            }
        )
    return {
        "graph_path": str(graph_path),
        "topics": [
            {
                "id": topic["id"],
                "name": topic["name"],
                "description": topic["description"],
                "concept_count": topic_counts[topic["id"]],
            }
            for topic in TOPIC_DEFINITIONS
        ],
        "assignments": assignments,
        "summary": {
            "concepts_seen": len(assignments),
            "topics_defined": len(TOPIC_DEFINITIONS),
            "topics_with_concepts": sum(1 for count in topic_counts.values() if count > 0),
            "belongs_to_edges": len(assignments),
            "topic_counts": {topic_names[topic_id]: count for topic_id, count in topic_counts.items()},
            "assignment_methods": method_counts,
        },
    }



def import_topics(graph_path: Path, write: bool = False, replace_existing: bool = False) -> dict[str, Any]:
    load_project_env()
    plan = build_topic_plan(graph_path)
    result = {
        "mode": "write" if write else "dry_run",
        "replace_existing": replace_existing,
        **plan,
    }
    if not write:
        return result

    driver = _driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            _apply_schema(session)
            if replace_existing:
                session.run("MATCH (:Concept)-[r:BELONGS_TO]->(:Topic) DELETE r")
            for topic in TOPIC_DEFINITIONS:
                session.run(
                    """
                    MERGE (t:Topic {id: $id})
                    SET t.name = $name,
                        t.description = $description,
                        t.source = $source,
                        t.created_from = $created_from
                    """,
                    id=topic["id"],
                    name=topic["name"],
                    description=topic["description"],
                    source="neo4j_topic_importer",
                    created_from="course_module_rule_plus_keyword_assignment",
                )
            for assignment in plan["assignments"]:
                session.run(
                    """
                    MATCH (c:Concept {id: $concept_id})
                    MATCH (t:Topic {id: $topic_id})
                    MERGE (c)-[r:BELONGS_TO]->(t)
                    SET r.source = $source,
                        r.method = $method,
                        r.rule = $rule,
                        r.matched_keywords = $matched_keywords
                    """,
                    concept_id=assignment["concept_id"],
                    topic_id=assignment["topic_id"],
                    source="neo4j_topic_importer",
                    method=assignment["assignment_method"],
                    rule=assignment["matched_rule"],
                    matched_keywords=json.dumps(assignment["matched_keywords"], ensure_ascii=False),
                )
    finally:
        driver.close()
    return result



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or import course-module Topic nodes for Neo4j.")
    parser.add_argument("--graph", default=str(GLOBAL_KG_JSON), help="Path to global_knowledge_graph.json")
    parser.add_argument("--write", action="store_true", help="Write Topic and BELONGS_TO to Neo4j. Omit for dry-run.")
    parser.add_argument("--replace-existing", action="store_true", help="Delete existing Concept-BELONGS_TO-Topic edges before writing the latest topic plan.")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    result = import_topics(Path(args.graph).resolve(), write=args.write, replace_existing=args.replace_existing)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
