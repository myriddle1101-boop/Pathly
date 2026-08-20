"""Turn completed evaluation outputs into conservative, thesis-ready tables."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
OUT = RESULTS / "paper_ready"


def read_csv(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def markdown_table(rows: list[dict[str, object]]) -> str:
    headers = list(rows[0])
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(row[key]) for key in headers) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = {row["metric"]: row["value"] for row in read_csv("kg_corpus_audit_summary.csv")}
    golden = json.loads((RESULTS / "kg_golden_chain_audit.json").read_text(encoding="utf-8"))["summary"]
    planning = {row["metric"]: row["value"] for row in read_csv("planning_summary.csv")}
    evidence = [
        {"evaluation_component": "KG corpus structural/provenance health", "sample": f"{corpus['run_count']} persisted pipeline runs", "result": f"{corpus['topic_instances']} topic instances; {corpus['prerequisite_edges']} prerequisite edges; {corpus['runs_with_dangling_edges']} runs with dangling edges; {corpus['runs_with_cycles']} with cycles", "claim_boundary": "Structural/provenance health only; not semantic correctness."},
        {"evaluation_component": "Live verified neural-foundations chain", "sample": "5 canonical concepts in live Neo4j/Chroma", "result": f"{golden['verified_overall']}/{golden['concept_count']} verified overall", "claim_boundary": "Only the reviewed five-concept source-grounded scope."},
        {"evaluation_component": "Planning automatic checks", "sample": "5 controlled goal phrasings x 2 profiles = 10 plans", "result": f"10/10 generated; time constraint handled {float(planning['time_constraint_handled']):.0%}; direct daily-limit compliance {float(planning['within_daily_limit']):.0%}", "claim_boundary": "Plans issue a warning when an individual topic exceeds the daily budget; human quality scoring remains required."},
        {"evaluation_component": "Content V4", "sample": "Controlled dual-profile golden path", "result": "Engineering gates and prior dual-profile artifact exist; no new independent human/LLM quality scores in this pack.", "claim_boundary": "Do not claim educational superiority until blinded ratings are completed."},
        {"evaluation_component": "Adaptation", "sample": "Prototype candidate retrieval", "result": "Implementation/test inventory only", "claim_boundary": "Treated as future work; no effectiveness claim."},
    ]
    write_csv("current_evidence_table.csv", evidence)
    (OUT / "current_evidence_table.md").write_text("# Current evaluation evidence\n\n" + markdown_table(evidence), encoding="utf-8")
    score_rows = read_csv("planning_scores.csv")
    compact = [{key: row[key] for key in ("case_id", "goal_id", "tier", "status", "within_daily_limit", "time_constraint_handled", "per_item_limit_warning", "known_or_mastered_not_repeated", "target_mapping_present", "max_daily_minutes_observed")} for row in score_rows]
    write_csv("planning_automatic_results.csv", compact)
    (OUT / "planning_automatic_results.md").write_text("# Planning Agent: automatic checks\n\n" + markdown_table(compact), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
