"""KQ1 canonical teaching semantics for Pathly's verified five-node path.

The semantic layer is deliberately separate from the legacy ``Concept`` graph.
It gives V4 a reviewed, versioned teaching contract without rewriting planning
relationships that still serve v1/v2 and the broader knowledge graph.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from verified_golden_sources import GOLDEN_PATH, VerifiedGoldenSourceRegistry


KQ1_SEMANTICS_VERSION = "kq1-golden-teaching-semantics-v1"


def _claim(kind: str, text: str, pages: list[int]) -> dict[str, Any]:
    return {"kind": kind, "text": text, "source_pages": pages, "review_status": "approved"}


GOLDEN_TEACHING_PROFILES: dict[str, dict[str, Any]] = {
    "Linear Separability": {
        "canonical_id": "golden:linear-separability",
        "aliases": ["linearly separable", "linear decision boundary"],
        "prerequisites": [],
        "claims": [
            _claim("definition", "A binary classification problem is linearly separable in a representation when one straight decision boundary can place the classes on opposite sides.", [2, 3]),
            _claim("mechanism", "A linear classifier scores an input with a weighted sum and uses one boundary to divide the representation space.", [2, 3]),
            _claim("boundary", "Separability is a property of the current representation, not a guarantee that every problem is simple or that training will succeed.", [2, 3]),
            _claim("example", "In the original XOR input space, positive and negative examples occupy alternating corners.", [2, 3]),
            _claim("counterexample", "XOR is not linearly separable in its original two-dimensional input representation.", [2, 3]),
        ],
        "misconceptions": [
            {"id": "linear-separability-is-permanent", "text": "If a problem is not linearly separable once, it can never become separable.", "correction": "A nonlinear feature transformation can create a representation in which a later linear boundary works."},
            {"id": "linear-separability-is-training", "text": "Linear separability means a model has already learned the right weights.", "correction": "It describes whether a boundary exists in a representation; optimisation is the separate task of finding parameters."},
        ],
        "assessment_targets": [
            {"id": "linear-separability-mechanism", "kind": "mechanism", "text": "Trace the representation and identify whether one straight boundary can separate the classes."},
            {"id": "linear-separability-misconception", "kind": "misconception_discrimination", "text": "Distinguish representation limits from optimisation limits."},
            {"id": "linear-separability-boundary", "kind": "application_or_boundary", "text": "Decide when a feature transformation is needed before a linear decision."},
        ],
    },
    "XOR": {
        "canonical_id": "golden:xor",
        "aliases": ["exclusive or", "xor problem"],
        "prerequisites": ["Linear Separability"],
        "claims": [
            _claim("definition", "XOR outputs one when exactly one of two binary inputs is one, and outputs zero when the inputs match.", [2, 3, 7]),
            _claim("mechanism", "A hidden nonlinear representation can map XOR inputs into features that a later linear output can separate.", [4, 5, 6, 7]),
            _claim("boundary", "Adding more linear layers without nonlinear activations does not solve the representational limitation.", [4, 5, 6]),
            _claim("example", "The inputs (0,1) and (1,0) are positive while (0,0) and (1,1) are negative.", [2, 3, 7]),
            _claim("counterexample", "One straight boundary in the original input plane cannot isolate both positive XOR corners.", [2, 3]),
        ],
        "misconceptions": [
            {"id": "xor-needs-more-linear-layers", "text": "XOR can be solved simply by stacking more linear layers.", "correction": "Compositions of linear transformations remain linear; a nonlinear activation changes what can be represented."},
            {"id": "xor-label-pattern", "text": "XOR is difficult because its labels are arbitrary names.", "correction": "The issue is geometric: positive and negative inputs alternate in the original representation."},
        ],
        "assessment_targets": [
            {"id": "xor-mechanism", "kind": "mechanism", "text": "Explain why a nonlinear hidden representation changes the XOR solution."},
            {"id": "xor-misconception", "kind": "misconception_discrimination", "text": "Distinguish additional depth from adding nonlinearity."},
            {"id": "xor-boundary", "kind": "application_or_boundary", "text": "Recognise alternating labels as a reason to test representational limits."},
        ],
    },
    "Neural Networks": {
        "canonical_id": "golden:neural-networks",
        "aliases": ["neural network", "neural net"],
        "prerequisites": ["XOR"],
        "claims": [
            _claim("definition", "A neural network composes learned weighted transformations with nonlinear activations to produce an output from an input representation.", [13, 14]),
            _claim("mechanism", "Hidden layers transform inputs into features; the output layer makes a decision from those transformed features.", [13, 14]),
            _claim("boundary", "Depth alone is not enough when every layer is linear because the composition still behaves as one linear transformation.", [13, 14]),
            _claim("example", "A hidden layer can create features that make a previously nonlinearly separable task easier for a final linear classifier.", [13, 14]),
            _claim("counterexample", "A stack of purely linear layers cannot create the nonlinear representational change needed for XOR.", [13, 14]),
        ],
        "misconceptions": [
            {"id": "network-is-many-lines", "text": "A neural network is just many independent linear classifiers.", "correction": "Its key capability comes from composing transformations with nonlinear activations into new hidden features."},
            {"id": "network-automatically-learns", "text": "Adding a neural network automatically finds a good solution.", "correction": "Architecture provides representational capacity; optimisation still has to learn useful parameters."},
        ],
        "assessment_targets": [
            {"id": "network-mechanism", "kind": "mechanism", "text": "Trace input, hidden representation, activation, and output."},
            {"id": "network-misconception", "kind": "misconception_discrimination", "text": "Separate representational capacity from learning parameters."},
            {"id": "network-boundary", "kind": "application_or_boundary", "text": "Identify why a purely linear stacked architecture cannot add nonlinear capacity."},
        ],
    },
    "Activation Functions": {
        "canonical_id": "golden:activation-functions",
        "aliases": ["activation function", "activation", "nonlinearity", "relu", "sigmoid"],
        "prerequisites": ["Neural Networks"],
        "claims": [
            _claim("definition", "An activation function applies a nonlinear transformation to a layer's weighted input.", [15, 16, 17]),
            _claim("mechanism", "The activation changes the hidden representation so later layers can model relationships beyond one linear transformation.", [15, 16, 17]),
            _claim("boundary", "Without nonlinear activations, multiple stacked linear layers collapse into an equivalent linear transformation.", [17]),
            _claim("example", "ReLU returns zero for negative input and passes positive input through unchanged.", [15, 16]),
            _claim("counterexample", "Merely adding another linear layer does not add the nonlinearity required to change representational capacity.", [17]),
        ],
        "misconceptions": [
            {"id": "activation-is-output-label", "text": "An activation function only renames the final output class.", "correction": "It transforms intermediate numerical values and changes the features passed to later layers."},
            {"id": "depth-replaces-activation", "text": "More linear layers can replace activation functions.", "correction": "Linear composition remains linear, regardless of how many layers are stacked."},
        ],
        "assessment_targets": [
            {"id": "activation-mechanism", "kind": "mechanism", "text": "Explain what changes when an activation follows a weighted sum."},
            {"id": "activation-misconception", "kind": "misconception_discrimination", "text": "Distinguish an intermediate transformation from an output label."},
            {"id": "activation-boundary", "kind": "application_or_boundary", "text": "Predict what is lost when activations are removed from a multilayer network."},
        ],
    },
    "Gradient Descent": {
        "canonical_id": "golden:gradient-descent",
        "aliases": ["stochastic gradient descent", "sgd", "gradient optimization"],
        "prerequisites": ["Activation Functions"],
        "claims": [
            _claim("definition", "Gradient descent updates model parameters in the direction that locally reduces a chosen loss.", [18, 19, 20]),
            _claim("mechanism", "Compute the loss gradient, choose a learning rate, and move parameters in the opposite gradient direction.", [18, 19, 20]),
            _claim("boundary", "The update direction is local; learning rate choice, loss landscape, and gradient quality affect whether optimisation makes useful progress.", [18, 19, 20]),
            _claim("example", "A parameter update subtracts the learning rate times the loss gradient from the current parameter value.", [19]),
            _claim("counterexample", "Moving in the gradient direction increases the loss locally rather than performing gradient descent.", [19, 20]),
        ],
        "misconceptions": [
            {"id": "gradient-is-update", "text": "The gradient itself is the new parameter value.", "correction": "The gradient is a direction and rate of change; it is scaled and subtracted from the current parameters."},
            {"id": "learning-rate-only-speed", "text": "The learning rate only changes training speed and cannot affect success.", "correction": "A step that is too large can overshoot while a step that is too small can make progress impractically slow."},
        ],
        "assessment_targets": [
            {"id": "gradient-descent-mechanism", "kind": "mechanism", "text": "Trace loss, gradient, learning rate, and parameter update."},
            {"id": "gradient-descent-misconception", "kind": "misconception_discrimination", "text": "Distinguish a gradient from the update computed using it."},
            {"id": "gradient-descent-boundary", "kind": "application_or_boundary", "text": "Reason about a learning-rate choice or reversed update direction."},
        ],
    },
}


def teaching_profile(concept_name: str) -> dict[str, Any]:
    profile = GOLDEN_TEACHING_PROFILES[concept_name]
    return {"semantics_version": KQ1_SEMANTICS_VERSION, "concept_name": concept_name, **profile}


def validate_profiles() -> list[str]:
    errors: list[str] = []
    for index, concept in enumerate(GOLDEN_PATH):
        profile = GOLDEN_TEACHING_PROFILES.get(concept) or {}
        kinds = {claim.get("kind") for claim in profile.get("claims") or []}
        target_kinds = {target.get("kind") for target in profile.get("assessment_targets") or []}
        expected_prerequisites = [] if index == 0 else [GOLDEN_PATH[index - 1]]
        if not profile.get("canonical_id"):
            errors.append(f"{concept}:missing canonical_id")
        if profile.get("prerequisites") != expected_prerequisites:
            errors.append(f"{concept}:wrong prerequisite chain")
        if not {"definition", "mechanism", "boundary", "example", "counterexample"}.issubset(kinds):
            errors.append(f"{concept}:incomplete teaching claims")
        if len(profile.get("misconceptions") or []) < 2:
            errors.append(f"{concept}:insufficient misconceptions")
        if target_kinds != {"mechanism", "misconception_discrimination", "application_or_boundary"}:
            errors.append(f"{concept}:incomplete assessment targets")
        if any(not claim.get("source_pages") for claim in profile.get("claims") or []):
            errors.append(f"{concept}:claim lacks source pages")
    return errors


def _settings() -> tuple[str, str, str, str]:
    return (
        os.getenv("NEO4J_URI", "bolt://localhost:7687"), os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", ""), os.getenv("NEO4J_DATABASE", "neo4j"),
    )


def publish_to_neo4j(*, kg_dir: str, dry_run: bool = False) -> dict[str, Any]:
    """Upsert only KQ1-labelled semantic nodes; never alter legacy Concept nodes."""
    errors = validate_profiles()
    if errors:
        raise ValueError("; ".join(errors))
    registry = VerifiedGoldenSourceRegistry(kg_dir)
    if any(item["status"] != "verified" for item in registry.audit()):
        raise RuntimeError("KQ1 requires all five verified public source links")
    if dry_run:
        return {"dry_run": True, "concepts": len(GOLDEN_PATH), "claims": 25, "misconceptions": 10, "assessment_targets": 15}
    from neo4j import GraphDatabase
    uri, user, password, database = _settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    now = datetime.now(timezone.utc).isoformat()
    try:
        with driver.session(database=database) as session:
            for position, concept in enumerate(GOLDEN_PATH, 1):
                profile = teaching_profile(concept)
                source = registry.resolve(concept_id=concept, concept_name=concept)
                session.run("""
                    MERGE (c:CanonicalConcept {id: $id})
                    SET c.name=$name, c.aliases=$aliases, c.position=$position,
                        c.review_status='approved', c.semantics_version=$version,
                        c.updated_at=$now
                    WITH c
                    MERGE (d:Document {id: $document_id})
                    SET d.title=$document_title, d.resource_id=$resource_id, d.source_scope='public'
                    MERGE (c)-[:USES_DOCUMENT {semantics_version:$version}]->(d)
                """, id=profile["canonical_id"], name=concept, aliases=profile["aliases"], position=position,
                   version=KQ1_SEMANTICS_VERSION, now=now, document_id=source["document_id"],
                   document_title=source["document_title"], resource_id=source["resource_id"])
                for claim_index, claim in enumerate(profile["claims"], 1):
                    claim_id = f"{profile['canonical_id']}:claim:{claim['kind']}"
                    session.run("""
                        MATCH (c:CanonicalConcept {id:$concept_id})
                        MERGE (claim:TeachingClaim {id:$claim_id})
                        SET claim.kind=$kind, claim.text=$text, claim.review_status='approved', claim.semantics_version=$version
                        MERGE (c)-[:HAS_TEACHING_CLAIM {semantics_version:$version}]->(claim)
                        WITH claim
                        UNWIND $pages AS page_number
                        MERGE (p:Page {id:$document_id + ':page:' + toString(page_number)})
                        SET p.document_id=$document_id, p.page_number=page_number, p.review_status='approved'
                        MERGE (claim)-[:SUPPORTED_BY {semantics_version:$version}]->(p)
                    """, concept_id=profile["canonical_id"], claim_id=claim_id, kind=claim["kind"], text=claim["text"],
                       pages=claim["source_pages"], document_id=source["document_id"], version=KQ1_SEMANTICS_VERSION)
                for item in profile["misconceptions"]:
                    session.run("""
                        MATCH (c:CanonicalConcept {id:$concept_id})
                        MERGE (m:Misconception {id:$id})
                        SET m.text=$text, m.correction=$correction, m.review_status='approved', m.semantics_version=$version
                        MERGE (c)-[:HAS_MISCONCEPTION {semantics_version:$version}]->(m)
                    """, concept_id=profile["canonical_id"], id=item["id"], text=item["text"], correction=item["correction"], version=KQ1_SEMANTICS_VERSION)
                for item in profile["assessment_targets"]:
                    session.run("""
                        MATCH (c:CanonicalConcept {id:$concept_id})
                        MERGE (a:AssessmentTarget {id:$id})
                        SET a.kind=$kind, a.text=$text, a.review_status='approved', a.semantics_version=$version
                        MERGE (a)-[:ASSESSES {semantics_version:$version}]->(c)
                    """, concept_id=profile["canonical_id"], id=item["id"], kind=item["kind"], text=item["text"], version=KQ1_SEMANTICS_VERSION)
                if position > 1:
                    previous = teaching_profile(GOLDEN_PATH[position - 2])["canonical_id"]
                    session.run("""
                        MATCH (p:CanonicalConcept {id:$previous}), (c:CanonicalConcept {id:$current})
                        MERGE (p)-[:PREREQUISITE_OF {semantics_version:$version}]->(c)
                    """, previous=previous, current=profile["canonical_id"], version=KQ1_SEMANTICS_VERSION)
    finally:
        driver.close()
    return {"dry_run": False, "concepts": len(GOLDEN_PATH), "claims": 25, "misconceptions": 10, "assessment_targets": 15, "version": KQ1_SEMANTICS_VERSION}


def read_profile_from_neo4j(concept_name: str) -> dict[str, Any] | None:
    """Retrieve one complete V4 teaching profile in one graph query."""
    profile = GOLDEN_TEACHING_PROFILES.get(concept_name)
    if not profile:
        return None
    from neo4j import GraphDatabase
    uri, user, password, database = _settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            row = session.run("""
                MATCH (c:CanonicalConcept {id:$id})
                OPTIONAL MATCH (c)-[:HAS_TEACHING_CLAIM]->(claim:TeachingClaim)-[:SUPPORTED_BY]->(page:Page)
                WITH c, claim, collect(DISTINCT page.page_number) AS pages
                WITH c, collect(CASE WHEN claim IS NULL THEN null ELSE {kind:claim.kind,text:claim.text,source_pages:pages} END) AS claims
                OPTIONAL MATCH (c)-[:HAS_MISCONCEPTION]->(m:Misconception)
                WITH c, claims, collect(CASE WHEN m IS NULL THEN null ELSE {id:m.id,text:m.text,correction:m.correction} END) AS misconceptions
                OPTIONAL MATCH (a:AssessmentTarget)-[:ASSESSES]->(c)
                RETURN c.name AS concept_name, c.id AS canonical_id, c.aliases AS aliases,
                       claims, misconceptions,
                       collect(CASE WHEN a IS NULL THEN null ELSE {id:a.id,kind:a.kind,text:a.text} END) AS assessment_targets
            """, id=profile["canonical_id"]).single()
        if not row or not row["concept_name"]:
            return None
        return {key: row[key] for key in row.keys()}
    finally:
        driver.close()
