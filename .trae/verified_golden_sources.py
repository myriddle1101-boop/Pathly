"""Verified source registry consumed by the normal Pathly content flow.

The registry never creates a plan or a prebuilt learner session. It only
certifies immutable offline source coverage when a normally generated plan
contains a matching canonical concept.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


GOLDEN_PATH_VERSION = "source-grounded-golden-s2-v1"
GOLDEN_PATH = [
    "Linear Separability",
    "XOR",
    "Neural Networks",
    "Activation Functions",
    "Gradient Descent",
]

VERIFIED_GOAL_PATTERNS = (
    "neural network",
    "xor",
    "linear separability",
    "nonlinear classification",
    "activation function",
    "gradient descent",
)


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def verified_canonical_concept_name(value: Any) -> str | None:
    """Return the verified canonical name when a term is one of the golden concepts."""
    key = _normal(value)
    for concept_name in GOLDEN_PATH:
        if _normal(concept_name) == key:
            return concept_name
    aliases = {
        "linearly separable": "Linear Separability",
        "not linearly separable": "Linear Separability",
        "non linearly separable": "Linear Separability",
        "nonlinear classification": "Linear Separability",
        "non linear classification": "Linear Separability",
        "exclusive or": "XOR",
        "xor problem": "XOR",
        "neural network": "Neural Networks",
        "neural net": "Neural Networks",
        "neural nets": "Neural Networks",
        "activation function": "Activation Functions",
        "activation": "Activation Functions",
        "nonlinearity": "Activation Functions",
        "non linearity": "Activation Functions",
        "nonlinear activation": "Activation Functions",
        "non linear activation": "Activation Functions",
        "relu": "Activation Functions",
        "sigmoid": "Activation Functions",
        "sgd": "Gradient Descent",
        "stochastic gradient descent": "Gradient Descent",
        "gradient optimization": "Gradient Descent",
    }
    if key in aliases:
        return aliases[key]
    for alias, concept_name in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in key:
            return concept_name
    return None


def verified_goal_concepts_for_goal(goal_text: str) -> list[str]:
    """Expand a normal learner goal into the verified source-grounded concept chain.

    This is intentionally stricter than ``matches_goal``.  A broad "learn neural
    networks" goal should not always be forced into the XOR demonstration path.
    The normal golden demo target must mention XOR/linear separability or combine
    neural networks with the solving mechanism.
    """
    goal = _normal(goal_text)
    if not goal:
        return []
    has_xor_problem = "xor" in goal or "linear separability" in goal or "linearly separable" in goal
    has_solution_chain = (
        ("neural network" in goal or "neural networks" in goal)
        and ("gradient descent" in goal or "activation function" in goal or "activation functions" in goal)
    )
    if has_xor_problem or has_solution_chain:
        return list(GOLDEN_PATH)
    return []


def _page_sequence(start: int, end: int, roles: dict[int, str] | None = None) -> list[dict[str, Any]]:
    roles = roles or {}
    return [
        {
            "page_number": page,
            "role": roles.get(
                page,
                "introduction" if page == start else ("worked_example" if page == end else "mechanism"),
            ),
            "chunk_ids": [],
        }
        for page in range(start, end + 1)
    ]


GOLDEN_SOURCES: dict[str, dict[str, Any]] = {
    "linear separability": {
        "resource_id": "01e27d8d07707beb3f8eb4ba3bfe4018f3dd4a2d14e2976aaba0ddf32c867207",
        "run_dir": ("06_mlp", "01e27d8d0770"),
        "pages": (2, 3),
        "roles": {2: "introduction", 3: "mechanism"},
        "required_terms": {3: ["xor", "not linearly separable"]},
        "source_readiness": "offline_kg_resource",
        "reason": "Pages 2-3 introduce the XOR problem and show directly why its classes are not linearly separable.",
    },
    "xor": {
        "resource_id": "01e27d8d07707beb3f8eb4ba3bfe4018f3dd4a2d14e2976aaba0ddf32c867207",
        "run_dir": ("06_mlp", "01e27d8d0770"),
        "pages": (2, 7),
        "roles": {2: "introduction", 3: "problem", 4: "nonlinearity", 5: "architecture", 6: "mechanism", 7: "worked_example"},
        "required_terms": {3: ["xor", "not linearly separable"], 7: ["solving xor", "learned"]},
        "source_readiness": "offline_kg_resource",
        "reason": "Pages 2-7 form a continuous worked sequence from the XOR problem through a learned nonlinear representation.",
    },
    "neural networks": {
        "resource_id": "8aae94ed012561752b0e064e7d1d6d6f81ebb973da4d19e44693e3f0763cf773",
        "run_dir": ("cs224n-2026-lecture03-neuralnets", "8aae94ed0125"),
        "pages": (13, 14),
        "roles": {13: "introduction", 14: "mechanism"},
        "required_terms": {13: ["neural network classifier", "linear decision boundary"], 14: ["non linear function"]},
        "source_readiness": "public_chroma",
        "reason": "Pages 13-14 contrast a linear classifier with a neural classifier and introduce its nonlinear hidden computation.",
    },
    "activation functions": {
        "resource_id": "8aae94ed012561752b0e064e7d1d6d6f81ebb973da4d19e44693e3f0763cf773",
        "run_dir": ("cs224n-2026-lecture03-neuralnets", "8aae94ed0125"),
        "pages": (15, 17),
        "roles": {15: "introduction", 16: "examples", 17: "mechanism"},
        "required_terms": {15: ["relu", "sigmoid"], 17: ["without non linearities", "linear transform"]},
        "source_readiness": "public_chroma",
        "reason": "Pages 15-17 compare common activation functions and explain why nonlinearity is necessary.",
    },
    "gradient descent": {
        "resource_id": "8aae94ed012561752b0e064e7d1d6d6f81ebb973da4d19e44693e3f0763cf773",
        "run_dir": ("cs224n-2026-lecture03-neuralnets", "8aae94ed0125"),
        "pages": (18, 20),
        "roles": {18: "objective", 19: "update_rule", 20: "gradient_computation"},
        "required_terms": {18: ["cross entropy"], 19: ["stochastic gradient descent", "learning rate"], 20: ["gradients"]},
        "source_readiness": "public_chroma",
        "reason": "Pages 18-20 connect the loss objective to the stochastic-gradient update and gradient computation.",
    },
}


@lru_cache(maxsize=8)
def _load_pages(pdf_path: str) -> tuple[str, ...]:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return tuple(_normal(page.extract_text() or "") for page in pdf.pages)


class VerifiedGoldenSourceRegistry:
    def __init__(self, kg_dir: str | Path):
        self.kg_dir = Path(kg_dir)

    def matches_goal(self, goal_text: str) -> bool:
        """Whether a normal learner goal is likely to traverse verified coverage."""
        return bool(verified_goal_concepts_for_goal(goal_text)) or any(
            _normal(pattern) in _normal(goal_text)
            for pattern in VERIFIED_GOAL_PATTERNS
        )

    def recommended_concepts_for_goal(self, goal_text: str) -> list[str]:
        """Verified concepts that a normal matching goal should try to traverse."""
        return verified_goal_concepts_for_goal(goal_text)

    def coverage_for_concepts(self, concepts: list[dict[str, Any] | str]) -> dict[str, Any]:
        names = [str(item.get("display_name") or item.get("name") or item.get("concept_id") or "") if isinstance(item, dict) else str(item) for item in concepts]
        covered = [name for name in names if self.resolve(concept_id=name, concept_name=name)]
        return {"registry_version": GOLDEN_PATH_VERSION, "covered_concepts": covered, "covered_count": len(covered), "total_count": len(names)}

    def _manifest(self, spec: dict[str, Any]) -> tuple[dict[str, Any], Path] | None:
        run_name, run_hash = spec["run_dir"]
        path = self.kg_dir / "web_data" / "runs" / run_name / run_hash / "manifest.json"
        try:
            document = (json.loads(path.read_text(encoding="utf-8")).get("document") or {})
            pdf_path = Path(str(document.get("pdf_path") or ""))
        except Exception:
            return None
        if not pdf_path.exists() or str(document.get("sha256") or "") != spec["resource_id"]:
            return None
        return document, pdf_path

    def _validated(self, spec: dict[str, Any], pdf_path: Path) -> bool:
        try:
            pages = _load_pages(str(pdf_path))
        except Exception:
            return False
        start, end = spec["pages"]
        if start < 1 or end > len(pages) or start > end:
            return False
        for page_number, terms in spec["required_terms"].items():
            page_text = pages[page_number - 1]
            if not all(_normal(term) in page_text for term in terms):
                return False
        return True

    def resolve(self, *, concept_id: str, concept_name: str) -> dict[str, Any] | None:
        canonical = verified_canonical_concept_name(concept_name) or verified_canonical_concept_name(concept_id)
        key = _normal(canonical or concept_name)
        if key not in GOLDEN_SOURCES:
            key = _normal(concept_id)
        spec = GOLDEN_SOURCES.get(key)
        if not spec:
            return None
        resolved = self._manifest(spec)
        if resolved is None:
            return None
        document, pdf_path = resolved
        if not self._validated(spec, pdf_path):
            return None
        start, end = spec["pages"]
        return {
            "resource_id": spec["resource_id"],
            "document_id": f"public:{spec['resource_id']}",
            "document_title": document.get("file_name") or pdf_path.name,
            "source_scope": "public",
            "page_sequence": _page_sequence(start, end, spec.get("roles")),
            "chunk_ids": [],
            "relevance_score": 1.0,
            "coverage_score": 1.0,
            "match_method": "s2_verified_golden_source",
            "match_reason": spec["reason"],
            "review_status": "verified",
            "source_readiness": spec["source_readiness"],
            "golden_path_version": GOLDEN_PATH_VERSION,
            "golden_path_position": GOLDEN_PATH.index(next(name for name in GOLDEN_PATH if _normal(name) == key)) + 1,
        }

    def page_evidence(self, link: dict[str, Any]) -> list[dict[str, Any]]:
        """Return text for pages belonging to a link already verified by this registry."""
        key = _normal(link.get("concept_name") or link.get("concept_id"))
        spec = GOLDEN_SOURCES.get(key)
        if not spec:
            return []
        resolved = self._manifest(spec)
        if resolved is None:
            return []
        _, pdf_path = resolved
        if not self._validated(spec, pdf_path):
            return []
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                return [
                    {"page_number": page, "text": pdf.pages[page - 1].extract_text() or ""}
                    for page in [int(item.get("page_number") or 0) for item in link.get("page_sequence") or []]
                    if 0 < page <= len(pdf.pages)
                ]
        except Exception:
            return []

    def pdf_path_for_resource(self, resource_id: str) -> Path | None:
        """Resolve an already verified public resource to its local PDF."""
        for spec in GOLDEN_SOURCES.values():
            if str(spec.get("resource_id")) != str(resource_id):
                continue
            resolved = self._manifest(spec)
            if resolved is None:
                return None
            _, pdf_path = resolved
            return pdf_path if self._validated(spec, pdf_path) else None
        return None
    def audit(self) -> list[dict[str, Any]]:
        output = []
        for position, concept_name in enumerate(GOLDEN_PATH, 1):
            source = self.resolve(concept_id=concept_name, concept_name=concept_name)
            output.append({
                "concept_name": concept_name,
                "position": position,
                "status": "verified" if source else "unlinked",
                "source": source,
            })
        return output
