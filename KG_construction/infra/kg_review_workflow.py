"""Candidate-KG review and evaluation workflow for the educator console.

Candidates remain separate from the published global KG until a reviewer has
explicitly approved them.  All state is stored in JSON so the review trail can
be exported with a paper's evaluation artefacts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _normal(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").split())


def _terms(value: Any) -> set[str]:
    aliases = {"nets": "networks", "network": "networks", "technique": "techniques"}
    raw = re.findall(r"[a-z0-9]+", _normal(value))
    return {aliases.get(term, term) for term in raw if term not in {"in", "of", "and", "the", "to", "for"}}


class CandidateKGWorkflow:
    def __init__(self, global_dir: Path):
        self.global_dir = Path(global_dir)
        self.registry_path = self.global_dir / "candidate_registry.json"
        self.review_dir = self.global_dir / "candidate_reviews"
        self.evaluation_dir = self.global_dir / "evaluation_runs"

    def _registry(self) -> list[dict[str, Any]]:
        return list(_read(self.registry_path, []))

    def _save_registry(self, rows: list[dict[str, Any]]) -> None:
        _write(self.registry_path, rows)

    @staticmethod
    def candidate_id(doc_dir: Path) -> str:
        return "candidate-" + hashlib.sha256(str(doc_dir.resolve()).encode("utf-8")).hexdigest()[:12]

    def register(self, *, doc_dir: Path, file_name: str, sha256: str) -> dict[str, Any]:
        doc_dir = Path(doc_dir).resolve()
        identifier = self.candidate_id(doc_dir)
        rows = self._registry()
        existing = next((row for row in rows if row.get("candidate_id") == identifier), None)
        payload = {
            "candidate_id": identifier,
            "file_name": file_name,
            "sha256": sha256,
            "doc_dir": str(doc_dir),
            "status": (existing or {}).get("status", "candidate_ready"),
            "created_at": (existing or {}).get("created_at", _now()),
            "updated_at": _now(),
            "published_at": (existing or {}).get("published_at"),
            "published_artifacts": (existing or {}).get("published_artifacts", {}),
        }
        rows = [row for row in rows if row.get("candidate_id") != identifier] + [payload]
        self._save_registry(rows)
        return payload

    def list_candidates(self) -> list[dict[str, Any]]:
        return sorted(self._registry(), key=lambda row: row.get("updated_at", ""), reverse=True)

    def get(self, candidate_id: str) -> dict[str, Any] | None:
        return next((row for row in self._registry() if row.get("candidate_id") == candidate_id), None)

    def paths(self, candidate: dict[str, Any]) -> dict[str, Path]:
        root = Path(candidate["doc_dir"])
        return {
            "root": root,
            "graph": root / "knowledge_graph.json",
            "topics": root / "stage2a_topics_hybrid.json",
            "prerequisites": root / "stage2b_prerequisites.json",
            "similarity": root / "stage2c_similarity_edges.json",
            "stage1": root / "stage1_chunks.json",
            "manifest": root / "manifest.json",
        }

    def graph(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return _read(self.paths(candidate)["graph"], {"nodes": [], "edges": []})

    def _chunks(self, candidate: dict[str, Any]) -> dict[int, dict[str, Any]]:
        return {int(row.get("chunk_id", 0)): row for row in _read(self.paths(candidate)["stage1"], []) if row.get("chunk_id") is not None}

    def _topic_candidates(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        return list(_read(self.paths(candidate)["topics"], {}).get("candidates", []))

    def evidence_for_concept(self, candidate: dict[str, Any], concept_name: str) -> dict[str, Any]:
        target = _terms(concept_name)
        matched = []
        chunk_ids: set[int] = set()
        for item in self._topic_candidates(candidate):
            source_terms = _terms(item.get("name"))
            if not target or not source_terms:
                continue
            overlap = len(target & source_terms) / max(1, len(target | source_terms))
            if overlap >= 0.5:
                ids = [int(value) for value in item.get("chunk_ids", []) if str(value).isdigit()]
                matched.append({"extracted_candidate": item.get("name"), "score": item.get("avg_score"), "chunk_ids": ids})
                chunk_ids.update(ids)
        chunks = self._chunks(candidate)
        return {
            "concept": concept_name,
            "match_count": len(matched),
            "candidate_matches": matched,
            "chunk_ids": sorted(chunk_ids),
            "chunks": [chunks[chunk_id] for chunk_id in sorted(chunk_ids) if chunk_id in chunks],
            "evidence_status": "direct_candidate_evidence" if chunk_ids else "no_direct_candidate_evidence",
        }

    def evidence_for_edge(self, candidate: dict[str, Any], edge: dict[str, Any]) -> dict[str, Any]:
        source = self.evidence_for_concept(candidate, str(edge.get("from") or ""))
        target = self.evidence_for_concept(candidate, str(edge.get("to") or ""))
        chunk_ids = sorted(set(source["chunk_ids"]) | set(target["chunk_ids"]))
        chunks = self._chunks(candidate)
        return {
            "edge": {"from": edge.get("from"), "to": edge.get("to"), "relation": edge.get("relation"), "reason": edge.get("reason", "")},
            "source_evidence": source,
            "target_evidence": target,
            "chunk_ids": chunk_ids,
            "chunks": [chunks[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks],
            "evidence_status": "endpoint_evidence_only" if source["chunk_ids"] and target["chunk_ids"] else "insufficient_endpoint_evidence",
            "review_question": "Does the original PDF support this directional relationship, not merely mention both concepts?",
        }

    def resource_quality(self, candidate: dict[str, Any]) -> dict[str, Any]:
        paths = self.paths(candidate)
        manifest = _read(paths["manifest"], {})
        document = manifest.get("document") or {}
        raw_pdf_path = str(document.get("pdf_path") or "").strip()
        pdf_path = Path(raw_pdf_path) if raw_pdf_path else None
        chunks = list(self._chunks(candidate).values())
        graph = self.graph(candidate)
        concept_evidence = [self.evidence_for_concept(candidate, str(node.get("id") or node.get("name") or "")) for node in graph.get("nodes", [])]
        text = " ".join(str(row.get("text") or "") for row in chunks)
        return {
            "pdf_path": str(pdf_path) if pdf_path else "",
            "pdf_exists": bool(pdf_path and pdf_path.exists() and pdf_path.is_file()),
            "pdf_size_bytes": pdf_path.stat().st_size if pdf_path and pdf_path.exists() and pdf_path.is_file() else 0,
            "sha256_present": bool(document.get("sha256")),
            "pipeline_status": manifest.get("status", "unknown"),
            "chunk_count": len(chunks),
            "total_words": sum(int(row.get("word_count") or 0) for row in chunks),
            "ocr_artifact_count": text.count("鈥") + text.count("�"),
            "page_metadata_coverage": sum(bool(row.get("page") or row.get("page_number") or row.get("page_start")) for row in chunks),
            "concept_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "concepts_with_direct_evidence": sum(bool(item["chunk_ids"]) for item in concept_evidence),
            "concept_evidence_coverage": round(sum(bool(item["chunk_ids"]) for item in concept_evidence) / max(1, len(concept_evidence)), 4),
            "quality_interpretation": "Automatic indicators support review; they do not establish pedagogical or factual quality without a human judgement.",
        }

    def _review_path(self, candidate_id: str) -> Path:
        return self.review_dir / f"{candidate_id}.json"

    def _resource_assessment_path(self, candidate_id: str) -> Path:
        return self.review_dir / f"{candidate_id}_resource_assessment.json"

    def resource_assessment(self, candidate_id: str) -> dict[str, Any]:
        return dict(_read(self._resource_assessment_path(candidate_id), {}))

    def save_resource_assessment(self, *, candidate_id: str, credibility: int, relevance: int, pedagogical_quality: int, readability: int, rights_status: str, reviewer: str, note: str) -> None:
        _write(self._resource_assessment_path(candidate_id), {
            "candidate_id": candidate_id,
            "credibility_1_5": int(credibility),
            "relevance_1_5": int(relevance),
            "pedagogical_quality_1_5": int(pedagogical_quality),
            "readability_1_5": int(readability),
            "rights_status": rights_status,
            "reviewer": reviewer.strip() or "anonymous_reviewer",
            "note": note.strip(),
            "reviewed_at": _now(),
        })

    def reviews(self, candidate_id: str) -> list[dict[str, Any]]:
        return list(_read(self._review_path(candidate_id), []))

    def save_review(self, *, candidate_id: str, item_type: str, item_key: str, decision: str, reviewer: str, note: str = "") -> None:
        rows = self.reviews(candidate_id)
        record = {
            "item_type": item_type,
            "item_key": item_key,
            "decision": decision,
            "reviewer": reviewer.strip() or "anonymous_reviewer",
            "note": note.strip(),
            "reviewed_at": _now(),
        }
        rows = [row for row in rows if not (row.get("item_type") == item_type and row.get("item_key") == item_key)]
        rows.append(record)
        _write(self._review_path(candidate_id), rows)

    def review_rows(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        graph = self.graph(candidate)
        lookup = {(row["item_type"], row["item_key"]): row for row in self.reviews(candidate["candidate_id"])}
        rows = []
        for node in graph.get("nodes", []):
            key = str(node.get("id") or node.get("name") or "")
            saved = lookup.get(("concept", key), {})
            evidence = self.evidence_for_concept(candidate, key)
            rows.append({"item_type": "concept", "item_key": key, "label": node.get("name") or key, "relation": "", "evidence": evidence["evidence_status"], "evidence_chunks": ", ".join(map(str, evidence["chunk_ids"])), "decision": saved.get("decision", "pending"), "reviewer": saved.get("reviewer", ""), "note": saved.get("note", "")})
        for edge in graph.get("edges", []):
            key = f"{edge.get('from', '')}|{edge.get('relation', '')}|{edge.get('to', '')}"
            saved = lookup.get(("edge", key), {})
            evidence = self.evidence_for_edge(candidate, edge)
            rows.append({"item_type": "edge", "item_key": key, "label": f"{edge.get('from', '')} → {edge.get('to', '')}", "relation": edge.get("relation", ""), "evidence": evidence["evidence_status"], "evidence_chunks": ", ".join(map(str, evidence["chunk_ids"])), "decision": saved.get("decision", "pending"), "reviewer": saved.get("reviewer", ""), "note": saved.get("note", "")})
        return rows

    def review_summary(self, candidate: dict[str, Any]) -> dict[str, int | bool]:
        rows = self.review_rows(candidate)
        decisions = [row["decision"] for row in rows]
        return {
            "total_items": len(rows),
            "approved": decisions.count("approved"),
            "rejected": decisions.count("rejected"),
            "needs_correction": decisions.count("needs_correction"),
            "pending": decisions.count("pending"),
            "publishable": bool(rows) and not any(item in {"pending", "rejected", "needs_correction"} for item in decisions),
        }

    def mark_published(self, candidate_id: str, artifacts: dict[str, Any]) -> None:
        rows = self._registry()
        for row in rows:
            if row.get("candidate_id") == candidate_id:
                row.update({"status": "published", "published_at": _now(), "updated_at": _now(), "published_artifacts": artifacts})
                break
        self._save_registry(rows)

    def evaluate(self, *, candidate: dict[str, Any], gold_topics: dict[str, Any], gold_prerequisites: dict[str, Any], output_prefix: str) -> dict[str, Any]:
        paths = self.paths(candidate)
        predicted_topics = _read(paths["topics"], {}).get("topics", [])
        predicted_edges = _read(paths["prerequisites"], {}).get("prerequisites", [])
        def topics(items: list[dict[str, Any]]) -> set[str]: return {_normal(item.get("name")) for item in items if _normal(item.get("name"))}
        def edges(items: list[dict[str, Any]]) -> set[tuple[str, str]]: return {(_normal(item.get("from")), _normal(item.get("to"))) for item in items if _normal(item.get("from")) and _normal(item.get("to"))}
        def metrics(predicted: set[Any], gold: set[Any]) -> dict[str, Any]:
            tp = sorted(predicted & gold); only_pred = sorted(predicted - gold); only_gold = sorted(gold - predicted)
            p = len(tp) / len(predicted) if predicted else 0.0; r = len(tp) / len(gold) if gold else 0.0
            return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "tp": len(tp), "fp": len(only_pred), "fn": len(only_gold), "predicted_only": only_pred, "gold_only": only_gold}
        topic_metric = metrics(topics(predicted_topics), topics(gold_topics.get("topics", gold_topics)))
        prereq_metric = metrics(edges(predicted_edges), edges(gold_prerequisites.get("prerequisites", gold_prerequisites)))
        result = {"created_at": _now(), "candidate_id": candidate["candidate_id"], "file_name": candidate["file_name"], "topic_metrics": topic_metric, "prerequisite_metrics": prereq_metric}
        output = self.evaluation_dir / f"{output_prefix}_{candidate['candidate_id']}.json"; _write(output, result)
        csv_output = output.with_suffix(".csv")
        with csv_output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric_group", "precision", "recall", "f1", "tp", "fp", "fn"]); writer.writeheader()
            writer.writerow({"metric_group": "topics", **{key: topic_metric[key] for key in writer.fieldnames[1:]}})
            writer.writerow({"metric_group": "prerequisites", **{key: prereq_metric[key] for key in writer.fieldnames[1:]}})
        errors = []
        errors += [{"error_type": "missing_concept", "item": item} for item in topic_metric["gold_only"]]
        errors += [{"error_type": "incorrect_concept", "item": item} for item in topic_metric["predicted_only"]]
        errors += [{"error_type": "missing_prerequisite", "item": " → ".join(item)} for item in prereq_metric["gold_only"]]
        errors += [{"error_type": "incorrect_or_directional_prerequisite", "item": " → ".join(item)} for item in prereq_metric["predicted_only"]]
        error_output = output.with_name(output.stem + "_error_cases.csv")
        with error_output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["error_type", "item"]); writer.writeheader(); writer.writerows(errors)
        result["artifacts"] = {"json": str(output), "summary_csv": str(csv_output), "error_cases_csv": str(error_output)}; _write(output, result)
        return result

    def judge_with_llm(self, *, candidate: dict[str, Any], model: str) -> dict[str, Any]:
        """Run a stronger-model, PDF-aware auxiliary judge over one candidate KG.

        The judge is intentionally separate from the extraction pipeline. It receives
        the original Stage-1 text chunks and the predicted concepts/relations, then
        creates a review ledger and a gold-like comparison set. This remains
        LLM-assisted evaluation, not an independent ground truth.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is required for LLM-assisted evaluation.")
        paths = self.paths(candidate)
        predicted_topics = list(_read(paths["topics"], {}).get("topics", []))
        predicted_edges = list(_read(paths["prerequisites"], {}).get("prerequisites", []))
        source_chunks = list(self._chunks(candidate).values())
        source_text = "\n\n".join(
            f"[Chunk {row.get('chunk_id')}] {str(row.get('text') or '')}" for row in source_chunks
        )[:50000]
        topic_names = [str(item.get("name") or "") for item in predicted_topics if str(item.get("name") or "")]
        edge_payload = [{"from": row.get("from"), "to": row.get("to"), "reason": row.get("reason", "")} for row in predicted_edges]
        prompt = f"""
You are an independent expert reviewer for a machine-learning learning-resource knowledge graph.
Review the predicted concepts and prerequisite relations against the source PDF text below.

Important distinction:
- A concept is supported if it is a meaningful learning concept represented in the source.
- A prerequisite A -> B must be a strong, directional learning dependency. Do not accept mere co-occurrence, hierarchy, application order, or a weak association.
- Identify important missing concepts or prerequisites only when they are clearly supported by the source; keep the list small and conservative.
- Use exact names from the predicted list for supported/unsupported predictions. For missing items, provide concise canonical names.

SOURCE PDF TEXT:
{source_text}

PREDICTED CONCEPTS:
{json.dumps(topic_names, ensure_ascii=False)}

PREDICTED PREREQUISITES:
{json.dumps(edge_payload, ensure_ascii=False)}

Return JSON only with this exact schema:
{{
  "supported_topics": ["exact predicted concept name"],
  "unsupported_topics": [{{"name": "exact predicted concept name", "reason": "brief reason"}}],
  "missing_topics": [{{"name": "canonical missing concept", "reason": "brief source-based reason"}}],
  "accepted_prerequisites": [{{"from": "exact predicted source", "to": "exact predicted target", "reason": "brief reason"}}],
  "rejected_prerequisites": [{{"from": "exact predicted source", "to": "exact predicted target", "reason": "brief reason"}}],
  "missing_prerequisites": [{{"from": "canonical prerequisite", "to": "canonical target", "reason": "brief source-based reason"}}],
  "overall_note": "one concise limitation or conclusion"
}}
"""
        request = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        # GPT-5.x models reject an explicit temperature parameter in this
        # Chat Completions path; keep deterministic temperature for legacy
        # judges while allowing the GPT-5.6 Terra evaluator to run.
        if not model.startswith("gpt-5"):
            request["temperature"] = 0
        response = OpenAI(api_key=api_key).chat.completions.create(**request)
        judge = json.loads(response.choices[0].message.content or "{}")
        predicted_topic_set = {_normal(name) for name in topic_names if _normal(name)}
        predicted_edge_set = {(_normal(row.get("from")), _normal(row.get("to"))) for row in predicted_edges if _normal(row.get("from")) and _normal(row.get("to"))}
        supported_topic_set = {_normal(name) for name in judge.get("supported_topics", []) if _normal(name)} & predicted_topic_set
        accepted_edge_set = {(_normal(row.get("from")), _normal(row.get("to"))) for row in judge.get("accepted_prerequisites", []) if _normal(row.get("from")) and _normal(row.get("to"))} & predicted_edge_set
        missing_topic_set = {_normal(row.get("name")) for row in judge.get("missing_topics", []) if _normal(row.get("name"))}
        missing_edge_set = {(_normal(row.get("from")), _normal(row.get("to"))) for row in judge.get("missing_prerequisites", []) if _normal(row.get("from")) and _normal(row.get("to"))}

        def metric(supported: set[Any], predicted: set[Any], missing: set[Any]) -> dict[str, Any]:
            precision = len(supported) / len(predicted) if predicted else 0.0
            recall = len(supported) / (len(supported) + len(missing)) if supported or missing else 0.0
            return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0, "tp": len(supported), "fp": len(predicted - supported), "fn": len(missing)}

        topic_metrics = metric(supported_topic_set, predicted_topic_set, missing_topic_set)
        prereq_metrics = metric(accepted_edge_set, predicted_edge_set, missing_edge_set)
        result = {
            "created_at": _now(), "evaluation_type": "llm_assisted_pdf_judge", "candidate_id": candidate["candidate_id"],
            "file_name": candidate["file_name"], "judge_model": model, "source_chunk_count": len(source_chunks),
            "topic_metrics": topic_metrics, "prerequisite_metrics": prereq_metrics, "judge_ledger": judge,
            "interpretation": "LLM-assisted evidence, not independent ground truth. Audit a sample manually before reporting results.",
        }
        output = self.evaluation_dir / f"llm_judge_{candidate['candidate_id']}.json"; _write(output, result)
        summary_csv = output.with_suffix(".csv")
        with summary_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric_group", "precision", "recall", "f1", "tp", "fp", "fn"]); writer.writeheader()
            writer.writerow({"metric_group": "topics", **topic_metrics}); writer.writerow({"metric_group": "prerequisites", **prereq_metrics})
        ledger_csv = output.with_name(output.stem + "_ledger.csv")
        ledger_rows = ([{"item_type": "topic", "decision": "supported", "item": name, "reason": ""} for name in judge.get("supported_topics", [])] +
                       [{"item_type": "topic", "decision": "unsupported", "item": row.get("name", ""), "reason": row.get("reason", "")} for row in judge.get("unsupported_topics", [])] +
                       [{"item_type": "topic", "decision": "missing", "item": row.get("name", ""), "reason": row.get("reason", "")} for row in judge.get("missing_topics", [])] +
                       [{"item_type": "prerequisite", "decision": "accepted", "item": f"{row.get('from', '')} -> {row.get('to', '')}", "reason": row.get("reason", "")} for row in judge.get("accepted_prerequisites", [])] +
                       [{"item_type": "prerequisite", "decision": "rejected", "item": f"{row.get('from', '')} -> {row.get('to', '')}", "reason": row.get("reason", "")} for row in judge.get("rejected_prerequisites", [])] +
                       [{"item_type": "prerequisite", "decision": "missing", "item": f"{row.get('from', '')} -> {row.get('to', '')}", "reason": row.get("reason", "")} for row in judge.get("missing_prerequisites", [])])
        with ledger_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["item_type", "decision", "item", "reason"]); writer.writeheader(); writer.writerows(ledger_rows)
        result["artifacts"] = {"json": str(output), "summary_csv": str(summary_csv), "ledger_csv": str(ledger_csv)}; _write(output, result)
        return result
