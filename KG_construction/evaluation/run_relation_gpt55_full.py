"""Safe parallel rerun of Stage 2b and Stage 4 for the full candidate library.

This script never edits historical runs and never publishes to Neo4j/RAG.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "web_data" / "runs"
OUT = ROOT / "web_data" / "model_runs" / "relation_gpt55" / "all"
STAGE2B = ROOT / "stage2b_prerequisites_hybrid.py"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists(): PYTHON = Path(sys.executable)

REQUIRED = ["stage1_chunks.json", "stage2a_topics_hybrid.json", "stage2c_similarity_edges.json", "stage3_topics_with_summary.json"]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()

def read_json(path: Path):
    with path.open(encoding="utf-8") as f: return json.load(f)

def candidates():
    seen = set(); rows = []
    for mf in RUNS.rglob("manifest.json"):
        d = mf.parent
        try: m = read_json(mf)
        except Exception as e: rows.append({"source_dir": str(d), "status":"excluded", "reason":f"bad_manifest:{e}"}); continue
        doc = m.get("document", {})
        key = doc.get("sha256") or str(d)
        if key in seen: continue
        seen.add(key)
        missing = [x for x in REQUIRED if not (d/x).exists()]
        pdf = Path(doc.get("pdf_path", ""))
        if not pdf.exists():
            local = next(iter(d.glob("*.pdf")), None)
            pdf = local or pdf
        reason = []
        if m.get("status") != "success": reason.append(f"manifest_status:{m.get('status')}")
        if missing: reason.append("missing:" + ",".join(missing))
        if not pdf.exists(): reason.append("missing_pdf")
        rows.append({"source_dir":str(d), "run_id":m.get("run_id", d.name), "file_name":doc.get("file_name", pdf.name), "sha256":doc.get("sha256", ""), "pdf_path":str(pdf), "status":"eligible" if not reason else "excluded", "reason":";".join(reason)})
    return rows

def write_csv(path, rows):
    if not rows: return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def graph_from_files(outdir: Path):
    sys.path.insert(0, str(ROOT))
    import stage4_build_and_visualize_kg as s4
    topics=s4.extract_topics(read_json(outdir/"stage3_topics_with_summary.json"))
    rel=s4.extract_prerequisites(read_json(outdir/"stage2b_prerequisites_gpt55.json"))
    sim=s4.extract_similarity(read_json(outdir/"stage2c_similarity_edges.json"))
    G=s4.build_graph(topics, rel, sim)
    s4.export_json_graph(G, str(outdir/"knowledge_graph_gpt55.json"))
    nx=s4.sanitize_graph_for_gexf(G)
    import networkx as _nx
    _nx.write_gexf(nx, outdir/"knowledge_graph_gpt55.gexf")
    return len(G.nodes), len(G.edges), len(rel)

def run_one(row, run_id, force=False, model="gpt-5.5", output_root=None):
    output_root = output_root or OUT
    src=Path(row["source_dir"]); safe=row["run_id"].replace("/","_").replace("\\","_")
    dst=output_root/run_id/safe
    dst.mkdir(parents=True, exist_ok=True)
    cfg=dst/"run_config.json"
    if cfg.exists() and not force:
        old=read_json(cfg)
        if old.get("status")=="success": return old
    for name in REQUIRED + ["manifest.json"]:
        shutil.copy2(src/name, dst/name)
    if Path(row["pdf_path"]).exists(): shutil.copy2(row["pdf_path"], dst/Path(row["pdf_path"]).name)
    env=os.environ.copy(); env["KG_RELATION_MODEL"]=model
    log=dst/"stage2b_gpt55.log"
    p=subprocess.run([str(PYTHON), str(STAGE2B)], input=str(dst/"stage2a_topics_hybrid.json")+"\n"+str(dst/"stage2b_prerequisites_gpt55.json")+"\n", text=True, capture_output=True, env=env, cwd=ROOT)
    log.write_text(p.stdout+"\n--- STDERR ---\n"+p.stderr, encoding="utf-8")
    status="success"; reason=""
    if p.returncode!=0: status="failed"; reason="stage2b_process_error"
    else:
        try:
            data=read_json(dst/"stage2b_prerequisites_gpt55.json")
            if data.get("method")!="llm": status="failed"; reason="model_fallback:"+str(data.get("method"))
        except Exception as e: status="failed"; reason=f"invalid_stage2b:{e}"
    nodes=edges=rels=0
    if status=="success":
        try: nodes,edges,rels=graph_from_files(dst)
        except Exception as e: status="failed"; reason=f"stage4_error:{e}"
    oldrel=0
    try: oldrel=len(read_json(src/"stage2b_prerequisites.json").get("prerequisites", []))
    except Exception: pass
    result={"status":status,"reason":reason,"source_dir":str(src),"run_id":row["run_id"],"model":model,"created_at":datetime.now(timezone.utc).isoformat(),"source_hashes":{n:sha256(src/n) for n in REQUIRED},"old_relation_count":oldrel,"new_relation_count":rels,"new_node_count":nodes,"new_edge_count":edges,"golden_path_resource":False}
    cfg.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (dst/"comparison_metadata.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int); ap.add_argument("--force",action="store_true"); ap.add_argument("--eligibility-only",action="store_true"); ap.add_argument("--model",default="gpt-5.5"); ap.add_argument("--output-root")
    a=ap.parse_args(); output_root=Path(a.output_root) if a.output_root else ROOT/"web_data"/"model_runs"/f"relation_{a.model.replace('.', '')}"/"all"; output_root.mkdir(parents=True,exist_ok=True); rid=datetime.now().strftime("%Y%m%d_%H%M%S")
    rows=candidates(); write_csv(output_root/"eligibility_report.csv",rows); (output_root/"eligibility_report.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    eligible=[r for r in rows if r["status"]=="eligible"][:a.limit] if a.limit else [r for r in rows if r["status"]=="eligible"]
    if a.eligibility_only: print(json.dumps({"total":len(rows),"eligible":len(eligible)},ensure_ascii=False)); return
    results=[run_one(r,rid,a.force,a.model,output_root) for r in eligible]
    summary={"run_id":rid,"total_discovered":len(rows),"eligible":len(eligible),"succeeded":sum(x.get("status")=="success" for x in results),"failed":sum(x.get("status")!="success" for x in results),"excluded":sum(x["status"]=="excluded" for x in rows),"results":results}
    (output_root/rid/"run_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("run_id","total_discovered","eligible","succeeded","failed","excluded")},ensure_ascii=False))
if __name__=="__main__": main()
