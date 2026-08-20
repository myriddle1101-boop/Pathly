"""Resumable PDF-aware comparison of legacy and GPT-5.5 relation outputs.

The cache is deliberately stored inside the parallel model run.  It does not
modify historical extraction runs, the candidate registry, Neo4j, or RAG.
"""
from __future__ import annotations
import argparse, csv, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web_data" / "model_runs" / "relation_gpt55" / "all"

def pooled_metric(counts):
    tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2*p*r/(p+r), 4) if p+r else 0.0, **counts}

def safe_name(run_id): return run_id.replace("/", "_").replace("\\", "_")

def load_cache(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None

def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames); writer.writeheader(); writer.writerows(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--judge-model", default="gpt-5.6-terra")
    ap.add_argument("--limit", type=int, help="Evaluate at most N successful resources this invocation.")
    ap.add_argument("--refresh", action="store_true", help="Ignore existing per-item Judge cache.")
    args = ap.parse_args()
    run = OUT / args.run_id
    summary = json.loads((run / "run_summary.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT))
    from infra.kg_review_workflow import CandidateKGWorkflow
    workflow = CandidateKGWorkflow(ROOT / "web_data")
    targets = [x for x in summary["results"] if x.get("status") == "success"]
    if args.limit: targets = targets[:args.limit]
    progress = {"run_id": args.run_id, "judge_model": args.judge_model, "started_at": datetime.now(timezone.utc).isoformat(), "items": []}
    for index, item in enumerate(targets, 1):
        source = Path(item["source_dir"])
        parallel = run / safe_name(item["run_id"])
        alias = parallel / "stage2b_prerequisites.json"
        if not alias.exists(): shutil.copy2(parallel / "stage2b_prerequisites_gpt55.json", alias)
        outcome = {"run_id": item["run_id"], "file_name": item.get("file_name", ""), "status": "success", "versions": {}}
        for label, doc_dir in (("baseline", source), ("gpt55", parallel)):
            cache = parallel / f"judge_{label}_{args.judge_model.replace('.', '_')}.json"
            result = None if args.refresh else load_cache(cache)
            if result is None:
                candidate = {"candidate_id": f"modelcmp-{label}-{item['run_id']}", "file_name": item.get("file_name", item["run_id"]), "doc_dir": str(doc_dir)}
                try:
                    result = workflow.judge_with_llm(candidate=candidate, model=args.judge_model)
                    cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception as exc:
                    outcome["status"] = "judge_error"; outcome["versions"][label] = {"error": str(exc)}; continue
            outcome["versions"][label] = result
        progress["items"].append(outcome)
        (run / "comparison_progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{index}/{len(targets)}] {item['run_id']}: {outcome['status']}", flush=True)
    # Build result files solely from successfully cached pairs. This makes every rerun resumable.
    rows, errors = [], []
    totals = {f"{m}_{g}": {"tp":0,"fp":0,"fn":0} for m in ("baseline","gpt55") for g in ("topics","prerequisites")}
    golden_totals = {f"{m}_{g}": {"tp":0,"fp":0,"fn":0} for m in ("baseline","gpt55") for g in ("topics","prerequisites")}
    for item in progress["items"]:
        versions = item["versions"]
        if not all(v in versions and "error" not in versions[v] for v in ("baseline", "gpt55")): continue
        row = {"run_id":item["run_id"], "file_name":item["file_name"], "golden_path_resource":False}
        for model in ("baseline", "gpt55"):
            result = versions[model]
            for group, field in (("topics", "topic_metrics"), ("prerequisites", "prerequisite_metrics")):
                m = result[field]
                for k in ("tp", "fp", "fn"): totals[f"{model}_{group}"][k] += m[k]
                row[f"{model}_{group[:-1]}_f1"] = m["f1"]
            ledger = result.get("judge_ledger", {})
            for kind, decision, key, formatter in (("topic", "unsupported", "unsupported_topics", lambda x:x.get("name", "")), ("prerequisite", "rejected", "rejected_prerequisites", lambda x:f"{x.get('from','')} -> {x.get('to','')}")):
                for entry in ledger.get(key, []): errors.append({"run_id":item["run_id"], "model":model, "item_type":kind, "decision":decision, "item":formatter(entry), "reason":entry.get("reason", "")})
        row["prerequisite_f1_delta"] = round(row["gpt55_prerequisite_f1"] - row["baseline_prerequisite_f1"], 4)
        rows.append(row)
    overall = [{"model":model, "metric_group":group, **pooled_metric(totals[f"{model}_{group}"])} for model in ("baseline", "gpt55") for group in ("topics", "prerequisites")]
    write_csv(OUT / "relation_model_comparison_per_file.csv", ["run_id","file_name","golden_path_resource","baseline_topic_f1","gpt55_topic_f1","baseline_prerequisite_f1","gpt55_prerequisite_f1","prerequisite_f1_delta"], rows)
    write_csv(OUT / "relation_model_comparison_overall.csv", ["model","metric_group","precision","recall","f1","tp","fp","fn"], overall)
    write_csv(OUT / "relation_model_error_cases.csv", ["run_id","model","item_type","decision","item","reason"], errors)
    payload = {"created_at":datetime.now(timezone.utc).isoformat(), "run_id":args.run_id, "judge_model":args.judge_model, "completed_pairs":len(rows), "requested_pairs":len(targets), "pooled_overall":overall, "golden_path_overall":[], "note":"LLM-assisted PDF evaluation, not independent ground truth."}
    (OUT / "relation_model_comparison.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"completed_pairs":len(rows),"requested_pairs":len(targets),"overall":overall}, ensure_ascii=False))

if __name__ == "__main__": main()
