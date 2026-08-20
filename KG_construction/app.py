import os
import json
import subprocess
import hashlib
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LOCAL_SITE_PACKAGES = PROJECT_DIR / ".venv" / "Lib" / "site-packages"
if LOCAL_SITE_PACKAGES.exists():
    local_site_packages_str = str(LOCAL_SITE_PACKAGES)
    if local_site_packages_str not in sys.path:
        sys.path.insert(0, local_site_packages_str)

import streamlit as st
import pandas as pd

from env_loader import load_project_env
from infra.benchmark_kg import benchmark_kg
from infra import config as infra_config
from infra.difficulty_calibration import calibrate_graph
from infra.harness import run_harness
from infra.neo4j_importer import _resolve_auto_resource_path, _resource_params, import_graph
from infra.neo4j_topic_importer import build_topic_plan, import_topics
from infra.neo4j_verify import verify_graph
from infra.rag_ingestion import build_rag_rows, ingest_stage1_chunks_with_report
from infra.rag_verify import verify_rag
from infra.node_details_audit import audit_calibrated_node_details
from infra.pipeline_runtime import (
    append_json_record,
    append_run_event,
    build_doc_dir,
    ensure_manifest,
    now_iso,
    save_json,
    save_manifest,
    stage_json_log_path,
    stage_text_log_path,
    update_recovery_state,
)
from infra.profile_seed import seed_profiles
from infra.profile_schema import LearnerProfile
from infra.profile_store import ProfileStore
from infra.profile_verify import verify_profiles
from infra.kg_review_workflow import CandidateKGWorkflow

PATHLY_DIR = PROJECT_DIR.parent / ".trae"
if str(PATHLY_DIR) not in sys.path:
    sys.path.insert(0, str(PATHLY_DIR))
from knowledge_release import KnowledgeReleaseService

load_project_env()

MANIFEST_DIR = getattr(infra_config, "MANIFEST_DIR", infra_config.DATA_DIR / "manifests")

# Streamlit page config must be the first Streamlit call
st.set_page_config(page_title="KG Developer Console", layout="wide")

# ========= Project Paths =========
def resolve_python_executable() -> Path:
    preferred = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    if preferred.exists():
        return preferred
    return Path(sys.executable)


PYTHON_EXE = resolve_python_executable()

# ========= Script Paths =========
STAGE1_SCRIPT = PROJECT_DIR / "stage1_adaptive_chunking.py"
STAGE2A_SCRIPT = PROJECT_DIR / "stage2a_hybrid_keybert_llm.py"
STAGE2B_SCRIPT = PROJECT_DIR / "stage2b_prerequisites_hybrid.py"
STAGE2C_SCRIPT = PROJECT_DIR / "stage2c_similarity.py"
STAGE3_SCRIPT = PROJECT_DIR / "stage3_node_summary_hybrid.py"
STAGE4_SCRIPT = PROJECT_DIR / "stage4_build_and_visualize_kg.py"  # 寤鸿鐢╲2

# ========= Data Directories =========
DATA_DIR = PROJECT_DIR / "web_data"
RUN_DIR = DATA_DIR / "runs"
GLOBAL_DIR = DATA_DIR / "global"

HISTORY_JSON = GLOBAL_DIR / "upload_history.json"
PROCESSED_JSON = GLOBAL_DIR / "processed_files.json"
GLOBAL_KG_JSON = GLOBAL_DIR / "global_knowledge_graph.json"
BATCH_RUN_LOG_JSON = GLOBAL_DIR / "batch_run_log.json"

for d in [RUN_DIR, GLOBAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

WORKFLOW = CandidateKGWorkflow(GLOBAL_DIR)

# ========= i18n =========
I18N = {
    "中文": {
        "title": "知识图谱构建平台（批量上传 + 累积知识库）",
        "upload": "上传一个或多个 PDF",
        "run": "运行流水线",
        "show_stats": "显示全局统计",
        "lang": "语言 / Language",
        "warn_upload": "请至少上传一个 PDF。",
        "processing": "处理中",
        "skip": "已处理过，已跳过（同名 + 同哈希）",
        "done": "完成",
        "failed": "失败",
        "global_stats": "全局统计",
        "history": "上传历史",
        "nodes": "节点数",
        "edges": "边数",
        "sample_nodes": "示例节点",
        "sample_edges": "示例边",
        "download_global": "下载全局 knowledge_graph.json",
        "viz": "图谱检查",
        "pre_img_missing": "未找到 prerequisite 图像。",
        "sim_img_missing": "未找到 similarity 图像。",
        "nodes_table": "节点表",
        "edges_table": "边表",
        "edge_filter": "按关系筛选边",
        "download_filtered": "下载筛选后的边 JSON",
        "no_history": "暂无历史记录。",
        "diff_dist": "难度分布",
        "global_empty": "全局图谱为空，请先处理至少一个 PDF。",
    },
    "English": {
        "title": "KG Developer Console (KG / Profile / RAG / Runtime)",
        "upload": "Upload one or more PDFs",
        "run": "Run Pipeline",
        "show_stats": "Show Global Stats",
        "lang": "Language / 中文",
        "warn_upload": "Please upload at least one PDF.",
        "processing": "Processing",
        "skip": "Already processed, skipped (same name + hash)",
        "done": "Done",
        "failed": "Failed",
        "global_stats": "Global Stats",
        "history": "Upload History",
        "nodes": "Nodes",
        "edges": "Edges",
        "sample_nodes": "Sample Nodes",
        "sample_edges": "Sample Edges",
        "download_global": "Download global knowledge_graph.json",
        "viz": "Graph Checks",
        "pre_img_missing": "Prerequisite image not found.",
        "sim_img_missing": "Similarity image not found.",
        "nodes_table": "Nodes Table",
        "edges_table": "Edges Table",
        "edge_filter": "Filter edge relations",
        "download_filtered": "Download filtered edges JSON",
        "no_history": "No history yet.",
        "diff_dist": "Difficulty Distribution",
        "global_empty": "Global graph is empty. Run at least one PDF first.",
    },
}

lang = st.sidebar.selectbox("Language / \u8bed\u8a00", ["\u4e2d\u6587", "English"])
T = I18N[lang]






# ========= Utility Helpers =========
# ========= Utility Helpers =========
# ========= Utility Helpers =========
def load_json_safe(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_safe(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def file_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def run_script_with_inputs(script_path: Path, inputs: list[str], cwd: Path):
    if not script_path.exists():
        return {
            "return_code": 1,
            "stdout": "",
            "stderr": f"[Error] Script not found: {script_path}",
            "combined_log": f"--- STDOUT ---\n\n\n--- STDERR ---\n[Error] Script not found: {script_path}",
            "duration_seconds": 0.0,
            "command": [str(PYTHON_EXE), str(script_path)],
            "cwd": str(cwd),
        }

    input_text = "\n".join(inputs) + "\n"
    started = time.perf_counter()
    try:
        p = subprocess.run(
            [str(PYTHON_EXE), str(script_path)],
            input=input_text,
            text=True,
            capture_output=True,
            cwd=str(cwd)
        )
        duration = time.perf_counter() - started
        log = f"--- STDOUT ---\n{p.stdout}\n\n--- STDERR ---\n{p.stderr}"
        return {
            "return_code": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
            "combined_log": log,
            "duration_seconds": round(duration, 4),
            "command": [str(PYTHON_EXE), str(script_path)],
            "cwd": str(cwd),
        }
    except Exception as e:
        duration = time.perf_counter() - started
        error_text = f"Subprocess error: {e}"
        return {
            "return_code": 1,
            "stdout": "",
            "stderr": error_text,
            "combined_log": f"--- STDOUT ---\n\n\n--- STDERR ---\n{error_text}",
            "duration_seconds": round(duration, 4),
            "command": [str(PYTHON_EXE), str(script_path)],
            "cwd": str(cwd),
        }


def get_processed_digest(processed: dict, filename: str) -> str | None:
    value = processed.get(filename)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        sha256 = value.get("sha256")
        if isinstance(sha256, str):
            return sha256
    return None


def tail_text(text: str, limit: int = 4000) -> str:
    return text[-limit:] if text else ""


def validate_json_path(path: Path, expected_type: str | None = None, required_keys: list[str] | None = None) -> tuple[bool, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        return False, f"{path.name}: JSON validation failed: {exc}"

    if expected_type == "list" and not isinstance(payload, list):
        return False, f"{path.name}: expected JSON list"
    if expected_type == "dict" and not isinstance(payload, dict):
        return False, f"{path.name}: expected JSON object"
    if required_keys and isinstance(payload, dict):
        missing = [key for key in required_keys if key not in payload]
        if missing:
            return False, f"{path.name}: missing required keys {missing}"
    return True, f"{path.name}: OK"


def validate_stage_artifacts(stage: dict) -> dict:
    missing_inputs = [str(path) for path in stage["input_paths"] if not path.exists()]
    missing_outputs = [str(path) for path in stage["output_paths"] if not path.exists()]
    details = []

    for path in stage["output_paths"]:
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            rule = stage.get("json_rules", {}).get(path.name, {})
            ok, detail = validate_json_path(
                path,
                expected_type=rule.get("expected_type"),
                required_keys=rule.get("required_keys"),
            )
            details.append(detail)
            if not ok and str(path) not in missing_outputs:
                missing_outputs.append(str(path))
        elif path.stat().st_size == 0:
            missing_outputs.append(str(path))
            details.append(f"{path.name}: file is empty")

    for path in stage.get("optional_output_paths", []):
        if path.exists():
            details.append(f"{path.name}: optional output present")
        else:
            details.append(f"{path.name}: optional output missing")

    return {
        "inputs_ok": len(missing_inputs) == 0,
        "outputs_ok": len(missing_outputs) == 0,
        "missing_inputs": missing_inputs,
        "missing_outputs": missing_outputs,
        "details": details,
    }



def write_stage_logs(doc_dir: Path, stage: dict, result: dict, validation: dict) -> tuple[Path, Path]:
    text_log_path = stage_text_log_path(doc_dir, stage["key"])
    json_log_path = stage_json_log_path(doc_dir, stage["key"])
    text_log = (
        f"[stage] {stage['key']}\n"
        f"[started_at] {now_iso()}\n"
        f"[cwd] {result['cwd']}\n"
        f"[command] {' '.join(result['command'])}\n"
        f"[return_code] {result['return_code']}\n"
        f"[duration_seconds] {result['duration_seconds']}\n"
        f"[inputs] {[str(path) for path in stage['input_paths']]}\n"
        f"[outputs] {[str(path) for path in stage['output_paths']]}\n"
        f"[validation] {json.dumps(validation, ensure_ascii=False, indent=2)}\n\n"
        f"{result['combined_log']}\n"
    )
    text_log_path.write_text(text_log, encoding="utf-8")
    save_json(
        json_log_path,
        {
            "stage": stage["key"],
            "script_path": str(stage["script_path"]),
            "cwd": result["cwd"],
            "command": result["command"],
            "input_paths": [str(path) for path in stage["input_paths"]],
            "output_paths": [str(path) for path in stage["output_paths"]],
            "optional_output_paths": [str(path) for path in stage.get("optional_output_paths", [])],
            "return_code": result["return_code"],
            "duration_seconds": result["duration_seconds"],
            "validation": validation,
            "stdout_tail": tail_text(result["stdout"], 2000),
            "stderr_tail": tail_text(result["stderr"], 2000),
        },
    )
    return text_log_path, json_log_path


def build_stage_plan(doc_dir: Path, pdf_path: Path) -> list[dict]:
    stage1_out = doc_dir / "stage1_chunks.json"
    stage2a_out = doc_dir / "stage2a_topics_hybrid.json"
    stage2b_out = doc_dir / "stage2b_prerequisites.json"
    stage2c_out = doc_dir / "stage2c_similarity_edges.json"
    stage3_out = doc_dir / "stage3_topics_with_summary.json"
    return [
        {
            "key": "stage1",
            "script_path": STAGE1_SCRIPT,
            "inputs_for_script": [str(pdf_path), str(stage1_out)],
            "input_paths": [pdf_path],
            "output_paths": [stage1_out, doc_dir / "stage1_text_cleaned.txt"],
            "optional_output_paths": [],
            "json_rules": {"stage1_chunks.json": {"expected_type": "list"}},
            "cwd": PROJECT_DIR,
        },
        {
            "key": "stage2a",
            "script_path": STAGE2A_SCRIPT,
            "inputs_for_script": [str(stage1_out), str(stage2a_out)],
            "input_paths": [stage1_out],
            "output_paths": [stage2a_out],
            "optional_output_paths": [],
            "json_rules": {"stage2a_topics_hybrid.json": {"expected_type": "dict", "required_keys": ["topics"]}},
            "cwd": PROJECT_DIR,
        },
        {
            "key": "stage2b",
            "script_path": STAGE2B_SCRIPT,
            "inputs_for_script": [str(stage2a_out), str(stage2b_out)],
            "input_paths": [stage2a_out],
            "output_paths": [stage2b_out],
            "optional_output_paths": [],
            "json_rules": {"stage2b_prerequisites.json": {"expected_type": "dict", "required_keys": ["prerequisites"]}},
            "cwd": PROJECT_DIR,
        },
        {
            "key": "stage2c",
            "script_path": STAGE2C_SCRIPT,
            "inputs_for_script": [str(stage2a_out), str(stage2c_out)],
            "input_paths": [stage2a_out],
            "output_paths": [stage2c_out],
            "optional_output_paths": [],
            "json_rules": {"stage2c_similarity_edges.json": {"expected_type": "dict", "required_keys": ["similarity_edges"]}},
            "cwd": PROJECT_DIR,
        },
        {
            "key": "stage3",
            "script_path": STAGE3_SCRIPT,
            "inputs_for_script": [str(stage2a_out), str(stage3_out)],
            "input_paths": [stage2a_out],
            "output_paths": [stage3_out],
            "optional_output_paths": [],
            "json_rules": {"stage3_topics_with_summary.json": {"expected_type": "dict", "required_keys": ["topics"]}},
            "cwd": PROJECT_DIR,
        },
        {
            "key": "stage4",
            "script_path": STAGE4_SCRIPT,
            "inputs_for_script": [str(stage3_out), str(stage2b_out), str(stage2c_out)],
            "input_paths": [stage3_out, stage2b_out, stage2c_out],
            "output_paths": [doc_dir / "knowledge_graph.json", doc_dir / "knowledge_graph.gexf"],
            "optional_output_paths": [doc_dir / "kg_prerequisite.png", doc_dir / "kg_similarity.png"],
            "json_rules": {"knowledge_graph.json": {"expected_type": "dict", "required_keys": ["nodes", "edges"]}},
            "cwd": doc_dir,
        },
    ]


def determine_resume_stage(manifest: dict, stage_plan: list[dict]) -> str | None:
    for stage in stage_plan:
        stage_key = stage["key"]
        stage_entry = manifest.get("stages", {}).get(stage_key, {})
        validation = validate_stage_artifacts(stage)
        if stage_entry.get("status") == "success" and validation["inputs_ok"] and validation["outputs_ok"]:
            continue
        return stage_key
    return None


def completed_stage_keys(manifest: dict, stage_plan: list[dict]) -> list[str]:
    completed = []
    for stage in stage_plan:
        stage_entry = manifest.get("stages", {}).get(stage["key"], {})
        validation = validate_stage_artifacts(stage)
        if stage_entry.get("status") == "success" and validation["inputs_ok"] and validation["outputs_ok"]:
            completed.append(stage["key"])
            continue
        break
    return completed


def merge_global_kg(global_json_path: Path, doc_kg_json_path: Path):
    g = load_json_safe(global_json_path, {"nodes": [], "edges": []})
    d = load_json_safe(doc_kg_json_path, None)

    if d is None:
        return g

    node_map = {n["id"]: n for n in g.get("nodes", []) if "id" in n}
    for n in d.get("nodes", []):
        nid = n.get("id")
        if nid:
            node_map[nid] = n

    edge_set = set()
    edges = []
    for e in g.get("edges", []) + d.get("edges", []):
        key = (e.get("from"), e.get("to"), e.get("relation"))
        if key not in edge_set:
            edge_set.add(key)
            edges.append(e)

    merged = {"nodes": list(node_map.values()), "edges": edges}
    save_json_safe(global_json_path, merged)
    return merged


def get_latest_success_doc_dir(history_rows: list[dict]) -> Path | None:
    for row in reversed(history_rows):
        if row.get("status") == "done" and row.get("doc_dir"):
            path = Path(row["doc_dir"])
            if path.exists():
                return path
    return None


def register_existing_successful_runs(workflow: CandidateKGWorkflow) -> int:
    """Make historical successful runs reviewable without publishing them again."""
    registered = 0
    for manifest_path in RUN_DIR.glob("**/manifest.json"):
        manifest = load_json_safe(manifest_path, {})
        doc_dir = manifest_path.parent
        if manifest.get("status") != "success" or not (doc_dir / "knowledge_graph.json").exists():
            continue
        document = manifest.get("document") or {}
        workflow.register(
            doc_dir=doc_dir,
            file_name=str(document.get("file_name") or doc_dir.name),
            sha256=str(document.get("sha256") or "historical-run"),
        )
        registered += 1
    return registered


def ensure_profiles_exist() -> list:
    store = ProfileStore()
    profiles = store.list_profiles()
    if profiles:
        return profiles
    seed_profiles()
    return store.list_profiles()


def build_profile_label(profile) -> str:
    return (
        f"{profile.name} | {profile.user_id} | "
        f"{profile.target_days} days | {profile.daily_minutes} min/day | {profile.domain}"
    )


def split_csv_text(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

def render_profile_status(profile, key_prefix: str = "profile_status") -> None:
    snapshot = profile.to_dict()
    known_topics_text = ", ".join(profile.known_topics) if profile.known_topics else "None yet"
    completed_topics_text = ", ".join(profile.completed_topics) if profile.completed_topics else "None yet"
    if profile.skill_tree:
        skill_preview = ", ".join(f"{topic}: {score:.2f}" for topic, score in sorted(profile.skill_tree.items()))
    else:
        skill_preview = "None yet"
    st.caption("Profile Store: SQLite / data/learner_profiles.db")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Target Days", profile.target_days)
    metric_cols[1].metric("Daily Minutes", profile.daily_minutes)
    metric_cols[2].metric("Current Day", profile.current_day)
    metric_cols[3].metric("Mastery Items", len(profile.mastery_vector))
    metric_cols[4].metric("Skill Tree Items", len(profile.skill_tree))
    st.write(
        f"**{profile.name}** (`{profile.user_id}`) | "
        f"domain: `{profile.domain}` | pace: `{profile.pace_preference}` | "
        f"confidence/anxiety: `{profile.confidence_level}/{profile.anxiety_level}`"
    )
    st.write(f"**Goal**: {profile.goal_text}")
    st.write(f"**Known topics**: {known_topics_text}")
    st.write(f"**Completed topics**: {completed_topics_text}")
    st.write(f"**Skill tree**: {skill_preview}")
    st.download_button(
        "Download selected profile JSON",
        data=json.dumps(snapshot, ensure_ascii=False, indent=2),
        file_name=f"{profile.user_id}_profile.json",
        mime="application/json",
        key=f"{key_prefix}_{profile.user_id}_download",
    )
    with st.expander("Profile JSON snapshot", expanded=False):
        st.json(snapshot)


def render_topic_review(graph_path: Path) -> None:
    if not graph_path.exists():
        st.info(f"Topic review source not found: {graph_path}")
        return

    topic_plan = build_topic_plan(graph_path)
    summary = topic_plan.get("summary", {})
    topics = topic_plan.get("topics", [])
    assignments = topic_plan.get("assignments", [])

    st.subheader("Topic Dry-Run Review")
    st.caption("Review Topic grouping before writing Topic and BELONGS_TO into Neo4j.")

    action_col1, action_col2 = st.columns([1, 1])
    if action_col1.button("Write Topic/BELONGS_TO to Neo4j", key="topic_review_write"):
        try:
            write_result = import_topics(graph_path, write=True, replace_existing=True)
            st.success(
                f"Topic import completed: {write_result['summary'].get('topics_defined', 0)} topics, "
                f"{write_result['summary'].get('belongs_to_edges', 0)} BELONGS_TO edges."
            )
        except Exception as exc:
            st.error(f"Topic import failed: {exc}")

    if action_col2.button("Verify Topic Coverage in Neo4j", key="topic_review_verify"):
        try:
            verify_result = verify_graph(graph_path, live=True, include_topics=True)
            if verify_result.get("passed"):
                st.success("Topic verification passed.")
            else:
                st.warning("Topic verification found mismatches. Review the details below.")
            with st.expander("Topic verification result", expanded=not verify_result.get("passed", False)):
                st.json(verify_result)
        except Exception as exc:
            st.error(f"Topic verification failed: {exc}")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Concepts", summary.get("concepts_seen", 0))
    metric_cols[1].metric("Topics", summary.get("topics_defined", 0))
    metric_cols[2].metric("Topics With Concepts", summary.get("topics_with_concepts", 0))
    metric_cols[3].metric("BELONGS_TO", summary.get("belongs_to_edges", 0))

    method_counts = summary.get("assignment_methods", {})
    if method_counts:
        method_df = pd.DataFrame(
            [{"method": key, "count": value} for key, value in sorted(method_counts.items())]
        )
        st.caption("Assignment methods")
        st.dataframe(method_df, use_container_width=True, hide_index=True)

    review_tab1, review_tab2, review_tab3 = st.tabs(["Topic Distribution", "Assignments", "Dry-Run JSON"])

    with review_tab1:
        topic_df = pd.DataFrame(topics)
        if not topic_df.empty:
            st.dataframe(topic_df, use_container_width=True, hide_index=True)
            chart_df = topic_df.set_index("name")["concept_count"]
            st.bar_chart(chart_df)
        else:
            st.info("No Topic summary available.")

    with review_tab2:
        assignment_df = pd.DataFrame(assignments)
        if not assignment_df.empty:
            topic_options = sorted(summary.get("topic_counts", {}).keys())
            selected_topics = st.multiselect(
                "Filter Topics",
                options=topic_options,
                default=topic_options,
                key="topic_review_topic_filter",
            )
            method_options = sorted(assignment_df["assignment_method"].dropna().unique().tolist())
            selected_methods = st.multiselect(
                "Filter Methods",
                options=method_options,
                default=method_options,
                key="topic_review_method_filter",
            )
            concept_query = st.text_input("Search Concept", value="", key="topic_review_concept_query")
            filtered_df = assignment_df.copy()
            if selected_topics:
                filtered_df = filtered_df[filtered_df["topic_name"].isin(selected_topics)]
            if selected_methods:
                filtered_df = filtered_df[filtered_df["assignment_method"].isin(selected_methods)]
            if concept_query.strip():
                filtered_df = filtered_df[
                    filtered_df["concept_id"].str.contains(concept_query.strip(), case=False, na=False)
                ]
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        else:
            st.info("No assignment details available.")

    with review_tab3:
        st.json(topic_plan)

    st.download_button(
        "Download Topic Dry-Run JSON",
        data=json.dumps(topic_plan, ensure_ascii=False, indent=2),
        file_name="topic_dry_run.json",
        mime="application/json",
        key="topic_review_download",
    )



def render_rag_review(doc_dir: Path, collection_name: str = "kg_chunks") -> None:
    st.subheader("RAG Review")
    st.caption("Review chunk metadata, ingest into ChromaDB, and verify Resource-to-chunk alignment.")

    stage1_path = doc_dir / "stage1_chunks.json"
    graph_path = doc_dir / "knowledge_graph.json"
    resource_path = _resolve_auto_resource_path(graph_path)
    resource = _resource_params(resource_path) if resource_path else None

    if not stage1_path.exists():
        st.info(f"stage1_chunks.json not found for: {doc_dir}")
        return

    try:
        rows = build_rag_rows(stage1_path)
    except Exception as exc:
        st.error(f"Failed to read stage1 chunks: {exc}")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Rows Ready", len(rows))
    metric_cols[1].metric("Resource Bound", 1 if resource else 0)
    metric_cols[2].metric("Collection", collection_name)
    metric_cols[3].metric("Current Chroma Count", get_chroma_resource_chunk_count(resource["id"], collection_name)[0] if resource else 0)

    action_col1, action_col2 = st.columns([1, 1])
    if action_col1.button("Ingest Latest stage1_chunks into ChromaDB", key="rag_review_ingest"):
        try:
            report = ingest_stage1_chunks_with_report(stage1_path, collection_name=collection_name)
            st.success(f"RAG ingestion completed: inserted {report.get('inserted', 0)} chunks.")
            with st.expander("RAG ingestion report", expanded=False):
                st.json(report)
        except Exception as exc:
            st.error(f"RAG ingestion failed: {exc}")

    if action_col2.button("Verify RAG Coverage", key="rag_review_verify"):
        try:
            result = verify_rag(
                collection_name=collection_name,
                resource_id=resource["id"] if resource else None,
                min_chunks=1,
            )
            if result.get("passed"):
                st.success("RAG verification passed.")
            else:
                st.warning("RAG verification found issues. Review the details below.")
            with st.expander("RAG verification result", expanded=not result.get("passed", False)):
                st.json(result)
        except Exception as exc:
            st.error(f"RAG verification failed: {exc}")

    review_tab1, review_tab2, review_tab3 = st.tabs(["Chunk Summary", "Chunk Rows", "Live Verify JSON"])

    with review_tab1:
        summary_rows = [
            {"field": "doc_dir", "value": str(doc_dir)},
            {"field": "stage1_path", "value": str(stage1_path)},
            {"field": "resource_id", "value": resource["id"] if resource else ""},
            {"field": "resource_filename", "value": resource["filename"] if resource else ""},
            {"field": "row_count", "value": len(rows)},
        ]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
        if resource:
            chunk_count, chunk_error = get_chroma_resource_chunk_count(resource["id"], collection_name)
            if chunk_error:
                st.info(f"Current live chunk check: {chunk_error}")
            else:
                st.caption(f"Current sampled Chroma chunks for this resource: {chunk_count}")

    with review_tab2:
        rows_df = pd.DataFrame(rows)
        if not rows_df.empty:
            concept_query = st.text_input("Search concept/topic in chunks", value="", key="rag_review_query")
            filtered_df = rows_df.copy()
            if concept_query.strip():
                mask = (
                    filtered_df["concept_name"].astype(str).str.contains(concept_query.strip(), case=False, na=False)
                    | filtered_df["topic_name"].astype(str).str.contains(concept_query.strip(), case=False, na=False)
                    | filtered_df["doc_name"].astype(str).str.contains(concept_query.strip(), case=False, na=False)
                )
                filtered_df = filtered_df[mask]
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        else:
            st.info("No chunk rows are ready for ingestion.")

    with review_tab3:
        try:
            verify_preview = verify_rag(
                collection_name=collection_name,
                resource_id=resource["id"] if resource else None,
                min_chunks=1,
            )
            st.json(verify_preview)
        except Exception as exc:
            st.info(f"Live verify preview unavailable: {exc}")

    st.download_button(
        "Download RAG rows JSON",
        data=json.dumps(rows, ensure_ascii=False, indent=2),
        file_name="rag_rows_preview.json",
        mime="application/json",
        key="rag_review_download",
    )

# ========= UI =========
def count_graph_payload(path: Path) -> dict:
    graph = load_json_safe(path, {"nodes": [], "edges": []})
    return {
        "nodes": len(graph.get("nodes", [])),
        "prerequisite_edges": sum(1 for edge in graph.get("edges", []) if edge.get("relation") == "prerequisite"),
        "similarity_edges": sum(1 for edge in graph.get("edges", []) if edge.get("relation") == "similarity"),
        "edges": len(graph.get("edges", [])),
    }


def get_chroma_resource_chunk_count(resource_id: str, collection_name: str = "kg_chunks") -> tuple[int, str | None]:
    if not resource_id:
        return 0, "Missing resource_id."
    try:
        import chromadb
        from infra.config import CHROMA_PATH

        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_or_create_collection(name=collection_name)
        result = collection.get(where={"resource_id": resource_id}, limit=100000)
        return len(result.get("ids", [])), None
    except Exception as exc:
        return 0, str(exc)


def build_sync_status(doc_dir: Path, sync_neo4j: bool = False) -> dict:
    doc_kg_json = doc_dir / "knowledge_graph.json"
    stage1_chunks = doc_dir / "stage1_chunks.json"
    resource_path = _resolve_auto_resource_path(doc_kg_json)
    resource = _resource_params(resource_path) if resource_path else None
    status = {
        "doc_dir": str(doc_dir),
        "kg_json": {
            "ok": doc_kg_json.exists(),
            "path": str(doc_kg_json),
            "counts": count_graph_payload(doc_kg_json) if doc_kg_json.exists() else {},
        },
        "neo4j_concepts": {"ok": False, "stats": None, "error": None},
        "resource": {"ok": False, "resource": resource, "stats": None, "error": None},
        "has_resource": {"ok": False, "count": 0},
        "rag_chunks": {
            "ok": False,
            "count": 0,
            "stage1_path": str(stage1_chunks),
            "stage1_exists": stage1_chunks.exists(),
            "error": None,
        },
    }

    if sync_neo4j and doc_kg_json.exists():
        try:
            concept_stats = import_graph(GLOBAL_KG_JSON)
            status["neo4j_concepts"] = {"ok": True, "stats": concept_stats, "error": None}
        except Exception as exc:
            status["neo4j_concepts"]["error"] = str(exc)

        try:
            resource_stats = import_graph(doc_kg_json, auto_resource=True)
            has_resource_count = int(resource_stats.get("has_resource_edges", 0))
            status["resource"]["ok"] = int(resource_stats.get("resources", 0)) > 0
            status["resource"]["stats"] = resource_stats
            status["has_resource"] = {"ok": has_resource_count > 0, "count": has_resource_count}
        except Exception as exc:
            status["resource"]["error"] = str(exc)
            status["has_resource"] = {"ok": False, "count": 0}

    if resource:
        chunk_count, chunk_error = get_chroma_resource_chunk_count(resource["id"])
        status["rag_chunks"]["count"] = chunk_count
        status["rag_chunks"]["ok"] = chunk_count > 0
        status["rag_chunks"]["error"] = chunk_error

    return status


def render_status_badge(label: str, ok: bool, detail: str = "") -> None:
    icon = "[OK]" if ok else "[TODO]"
    if detail:
        st.write(f"{icon} **{label}**: {detail}")
    else:
        st.write(f"{icon} **{label}**")


def render_sync_status(status: dict) -> None:
    kg_counts = status["kg_json"].get("counts", {})
    kg_detail = (
        f"{kg_counts.get('nodes', 0)} concepts / {kg_counts.get('edges', 0)} edges"
        if status["kg_json"]["ok"]
        else "missing knowledge_graph.json"
    )
    render_status_badge("KG JSON written", status["kg_json"]["ok"], kg_detail)

    concept_stats = status["neo4j_concepts"].get("stats") or {}
    concept_detail = (
        f"{concept_stats.get('concepts', 0)} concepts synced"
        if status["neo4j_concepts"]["ok"]
        else status["neo4j_concepts"].get("error") or "not synced in this check"
    )
    render_status_badge("Neo4j concepts synced", status["neo4j_concepts"]["ok"], concept_detail)

    resource = status["resource"].get("resource") or {}
    resource_detail = (
        resource.get("filename", "")
        if status["resource"]["ok"]
        else status["resource"].get("error") or "not written in this check"
    )
    render_status_badge("Resource written", status["resource"]["ok"], resource_detail)
    render_status_badge("HAS_RESOURCE created", status["has_resource"]["ok"], f"{status['has_resource']['count']} edges")

    rag_detail = (
        f"{status['rag_chunks']['count']} chunks"
        if status["rag_chunks"]["ok"]
        else status["rag_chunks"].get("error") or "not ingested yet"
    )
    render_status_badge("RAG chunks ingested", status["rag_chunks"]["ok"], rag_detail)


def latest_harness_manifest() -> dict | None:
    if not MANIFEST_DIR.exists():
        return None
    manifests = sorted(MANIFEST_DIR.glob("harness_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        return None
    payload = load_json_safe(manifests[0], {})
    payload["path"] = str(manifests[0])
    return payload


def build_runtime_status() -> dict:
    status = {
        "node_details_audit": audit_calibrated_node_details(GLOBAL_KG_JSON),
        "kg_benchmark": benchmark_kg(GLOBAL_KG_JSON),
        "profile_store": verify_profiles(),
        "latest_harness_manifest": latest_harness_manifest(),
    }
    status["passed"] = (
        status["node_details_audit"].get("status") in {"success", "warning"}
        and status["kg_benchmark"].get("status") == "success"
        and status["profile_store"].get("passed") is True
    )
    return status


def render_runtime_status(status: dict) -> None:
    audit = status["node_details_audit"]
    benchmark = status["kg_benchmark"]
    profile = status["profile_store"]
    latest_manifest = status.get("latest_harness_manifest")
    st.header("Runtime Infrastructure status")
    cols = st.columns(4)
    cols[0].metric("Concepts", audit.get("total_concepts", 0))
    cols[1].metric("Description coverage", audit.get("field_coverage", {}).get("description", 0.0))
    cols[2].metric("Difficulty L2 ratio", audit.get("difficulty_distribution", {}).get("2", 0.0))
    cols[3].metric("Profiles", profile.get("profile_count", 0))
    render_status_badge("Node details audit", audit.get("status") in {"success", "warning"}, "; ".join(audit.get("warnings", [])) or "ok")
    render_status_badge("KG benchmark", benchmark.get("status") == "success", f"{benchmark.get('structural_metrics', {}).get('edge_count', 0)} edges")
    render_status_badge("Profile Store verify", profile.get("passed") is True, f"{profile.get('profile_count', 0)} profiles")
    render_status_badge(
        "Latest harness manifest",
        latest_manifest is not None,
        latest_manifest.get("path", "not generated yet") if latest_manifest else "not generated yet",
    )
    with st.expander("Runtime status JSON", expanded=False):
        st.json(status)


def render_teaching_knowledge_review() -> None:
    """KQ5 admin review: knowledge facts and fallback blueprints, never learner answers."""
    service = KnowledgeReleaseService(kg_dir=PROJECT_DIR)
    st.header("V4 Teaching Knowledge Review")
    st.caption("Review canonical concepts, source evidence, misconceptions, assessment targets, and fallback blueprints. Runtime learner questions remain governed by the automatic V4 quality gate.")
    st.json(service.status())
    if st.button("Build review candidate", key="kq5_build_candidate"):
        try:
            st.session_state["kq5_candidate"] = service.build_candidate()
            st.success(f"Candidate {st.session_state['kq5_candidate']['candidate_id']} is ready for review.")
        except Exception as exc:
            st.error(f"Could not build knowledge candidate: {exc}")
    candidate = st.session_state.get("kq5_candidate")
    if candidate:
        review = service.review(candidate)
        st.subheader(f"Candidate {candidate['candidate_id']}")
        st.dataframe(pd.DataFrame(review["checks"]), use_container_width=True)
        with st.expander("Candidate JSON", expanded=False):
            st.json(candidate)
        if review["passed"] and st.button("Publish approved knowledge", key="kq5_publish_candidate"):
            published = service.publish(candidate)
            st.success(f"Published {published['candidate_id']} atomically.")
    published = sorted(service.releases_dir.glob("*.json")) if service.releases_dir.exists() else []
    if published:
        selected = st.selectbox("Restore published version", [path.stem for path in published], key="kq5_restore_version")
        if st.button("Restore this published version", key="kq5_restore"):
            service.rollback(selected)
            st.success(f"Restored {selected} atomically.")


def render_dashboard(workflow: CandidateKGWorkflow) -> None:
    published = load_json_safe(GLOBAL_KG_JSON, {"nodes": [], "edges": []})
    candidates = workflow.list_candidates()
    runtime = build_runtime_status()
    st.header("Knowledge Provider & Evaluation Console")
    st.caption("Candidate resources are isolated from the published Neo4j/RAG knowledge layer until explicit review and publication.")
    columns = st.columns(4)
    columns[0].metric("Published concepts", len(published.get("nodes", [])))
    columns[1].metric("Published edges", len(published.get("edges", [])))
    columns[2].metric("Candidate resources", sum(row.get("status") != "published" for row in candidates))
    columns[3].metric("Published resources", sum(row.get("status") == "published" for row in candidates))
    if candidates:
        rows = []
        for candidate in candidates[:10]:
            summary = workflow.review_summary(candidate)
            rows.append({"candidate": candidate["candidate_id"], "file": candidate["file_name"], "status": candidate["status"], **summary})
        st.subheader("Candidate review queue")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    render_status_badge("Runtime health", runtime["passed"], "See Runtime Health for detail")


def render_kg_review(workflow: CandidateKGWorkflow) -> None:
    st.header("KG Review")
    st.caption("Review each extracted concept or relation against the original PDF and its evidence chunks. Neo4j remains the source of truth for published full-graph exploration.")
    candidates = workflow.list_candidates()
    if not candidates:
        st.info("No candidate KG is ready. Upload a PDF in Resources and complete the pipeline first.")
        return
    labels = {row["candidate_id"]: f"{row['file_name']} · {row['status']} · {row['candidate_id']}" for row in candidates}
    selected_id = st.selectbox("Candidate resource", list(labels), format_func=labels.get, key="review_candidate")
    candidate = workflow.get(selected_id)
    if not candidate:
        return
    graph = workflow.graph(candidate)
    review_rows = workflow.review_rows(candidate)
    summary = workflow.review_summary(candidate)
    quality = workflow.resource_quality(candidate)
    st.info(f"You are reviewing one PDF resource: **{candidate['file_name']}**. The concepts, relations and evidence chunks below all come from this selected PDF; they are not drawn from the published Neo4j graph.")
    st.subheader("Step 1 — Is this PDF a usable learning resource?")
    quality_columns = st.columns(6)
    quality_columns[0].metric("PDF available", "Yes" if quality["pdf_exists"] else "No")
    quality_columns[1].metric("Chunks", quality["chunk_count"])
    quality_columns[2].metric("Words", quality["total_words"])
    quality_columns[3].metric("Direct evidence coverage", f"{quality['concept_evidence_coverage']:.0%}")
    quality_columns[4].metric("OCR artifacts", quality["ocr_artifact_count"])
    quality_columns[5].metric("Page metadata", f"{quality['page_metadata_coverage']}/{quality['chunk_count']}")
    st.caption("These indicators flag resource and extraction risks. They do not replace a human judgement about source authority, factual accuracy, or pedagogical quality.")
    if quality["pdf_exists"]:
        st.subheader("Original PDF — primary review evidence")
        st.caption("Use this source view together with the evidence chunks below to judge whether each concept and directional relation is actually supported by the document.")
        st.pdf(Path(quality["pdf_path"]).read_bytes(), height=900)
    else:
        st.error("Original PDF is unavailable for this candidate; do not approve it as source-grounded.")
    with st.expander("Resource file details and download", expanded=False):
        st.write(f"**Resource:** {candidate['file_name']}")
        st.write(f"**Pipeline status:** {quality['pipeline_status']} | **SHA-256 present:** {quality['sha256_present']}")
        st.write(f"**PDF path:** `{quality['pdf_path']}`")
        if quality["pdf_exists"]:
            st.download_button("Download original PDF", Path(quality["pdf_path"]).read_bytes(), file_name=candidate["file_name"], mime="application/pdf", key=f"download_pdf_{selected_id}")
    previous_resource_assessment = workflow.resource_assessment(selected_id)
    with st.expander("Record PDF resource assessment", expanded=not bool(previous_resource_assessment)):
        st.caption("Rate the source itself, separately from whether an individual concept/edge was extracted correctly. 1 = very weak, 5 = very strong.")
        assessment_cols = st.columns(4)
        credibility = assessment_cols[0].selectbox("Author/source credibility", [1, 2, 3, 4, 5], index=max(0, int(previous_resource_assessment.get("credibility_1_5", 3)) - 1), key="resource_credibility")
        relevance = assessment_cols[1].selectbox("Goal/topic relevance", [1, 2, 3, 4, 5], index=max(0, int(previous_resource_assessment.get("relevance_1_5", 3)) - 1), key="resource_relevance")
        pedagogical = assessment_cols[2].selectbox("Pedagogical quality", [1, 2, 3, 4, 5], index=max(0, int(previous_resource_assessment.get("pedagogical_quality_1_5", 3)) - 1), key="resource_pedagogical")
        readability = assessment_cols[3].selectbox("Readability / extraction quality", [1, 2, 3, 4, 5], index=max(0, int(previous_resource_assessment.get("readability_1_5", 3)) - 1), key="resource_readability")
        rights_status = st.selectbox("Rights / reuse status", ["unknown", "public_or_permitted", "restricted_or_review_needed"], index=["unknown", "public_or_permitted", "restricted_or_review_needed"].index(previous_resource_assessment.get("rights_status", "unknown")), key="resource_rights")
        resource_note = st.text_area("Resource-quality rationale", value=previous_resource_assessment.get("note", ""), key="resource_quality_note")
        if st.button("Save resource assessment", key="save_resource_assessment"):
            workflow.save_resource_assessment(candidate_id=selected_id, credibility=credibility, relevance=relevance, pedagogical_quality=pedagogical, readability=readability, rights_status=rights_status, reviewer="reviewer-1", note=resource_note)
            st.success("Resource-quality assessment saved.")
            st.rerun()
    st.subheader("Review summary for this PDF")
    st.caption("The detailed concept and relation checks are separated below.")
    columns = st.columns(5)
    concept_rows = [row for row in review_rows if row["item_type"] == "concept"]
    edge_rows = [row for row in review_rows if row["item_type"] == "edge"]
    columns[0].metric("Concepts", len(concept_rows))
    columns[1].metric("Edges", len(edge_rows))
    columns[2].metric("Approved", summary["approved"])
    columns[3].metric("Pending", summary["pending"])
    columns[4].metric("Publishable", "Yes" if summary["publishable"] else "No")
    st.download_button("Download review trail", json.dumps({"candidate": candidate, "reviews": workflow.reviews(selected_id)}, ensure_ascii=False, indent=2), file_name=f"{selected_id}_review.json", mime="application/json")
    st.subheader("Step 2 — Review concepts extracted from this PDF")
    st.caption("Each evidence chunk is from the selected PDF. Check the original passage before deciding whether a concept was correctly extracted.")
    st.dataframe(pd.DataFrame(concept_rows), use_container_width=True, height=280)
    if concept_rows:
        concept_options = {row["item_key"]: row["label"] for row in concept_rows}
        selected_concept = st.selectbox("Concept to review", list(concept_options), format_func=concept_options.get, key="review_concept_item")
        concept_item = next(row for row in concept_rows if row["item_key"] == selected_concept)
        evidence = workflow.evidence_for_concept(candidate, selected_concept)
        st.write(f"**Source evidence for concept: {concept_item['label']}**")
        if evidence["candidate_matches"]:
            st.dataframe(pd.DataFrame(evidence["candidate_matches"]), use_container_width=True)
        if evidence["chunks"]:
            for chunk in evidence["chunks"]:
                with st.expander(f"Source chunk {chunk.get('chunk_id')} — {chunk.get('word_count', 0)} words", expanded=False):
                    st.text(chunk.get("text") or "")
        else:
            st.warning("No PDF source chunk was linked to this concept. Review the PDF manually, or mark it as needing correction.")
        concept_decision_col, concept_reviewer_col = st.columns(2)
        concept_decision = concept_decision_col.selectbox("Concept decision", ["approved", "rejected", "needs_correction"], key="concept_review_decision")
        concept_reviewer = concept_reviewer_col.text_input("Concept reviewer", value="reviewer-1", key="concept_reviewer_name")
        concept_note = st.text_area("Concept evidence note / correction rationale", key="concept_review_note")
        if st.button("Save concept decision", key="save_concept_review_decision"):
            workflow.save_review(candidate_id=selected_id, item_type="concept", item_key=selected_concept, decision=concept_decision, reviewer=concept_reviewer, note=concept_note)
            st.success("Concept decision saved. Reloading the candidate summary.")
            st.rerun()

    st.subheader("Step 3 — Review prerequisite relations inferred from the concepts")
    st.caption("These relations are inferred by the prerequisite agent from the concept list. Review whether each relation is a strong, correctly directed prerequisite; this step does not require PDF chunk matching.")
    edge_display_rows = [{key: value for key, value in row.items() if key not in {"evidence", "evidence_chunks"}} for row in edge_rows]
    st.dataframe(pd.DataFrame(edge_display_rows), use_container_width=True, height=280)
    if edge_rows:
        edge_options = {row["item_key"]: row["label"] for row in edge_rows}
        selected_edge = st.selectbox("Prerequisite relation to review", list(edge_options), format_func=edge_options.get, key="review_edge_item")
        edge_item = next(row for row in edge_rows if row["item_key"] == selected_edge)
        raw_edge = next(edge for edge in graph.get("edges", []) if f"{edge.get('from', '')}|{edge.get('relation', '')}|{edge.get('to', '')}" == selected_edge)
        st.write(f"**Inferred relation: {edge_item['label']}**")
        st.write(f"**Agent reasoning:** {raw_edge.get('reason') or 'No reason was produced.'}")
        edge_decision_col, edge_reviewer_col = st.columns(2)
        edge_decision = edge_decision_col.selectbox("Relation decision", ["approved", "rejected", "needs_correction"], key="edge_review_decision")
        edge_reviewer = edge_reviewer_col.text_input("Relation reviewer", value="reviewer-1", key="edge_reviewer_name")
        edge_note = st.text_area("Relation rationale / correction", key="edge_review_note")
        if st.button("Save relation decision", key="save_edge_review_decision"):
            workflow.save_review(candidate_id=selected_id, item_type="edge", item_key=selected_edge, decision=edge_decision, reviewer=edge_reviewer, note=edge_note)
            st.success("Relation decision saved. Reloading the candidate summary.")
            st.rerun()
    return
    st.subheader("Record a review decision")
    item_options = {row["item_key"]: f"{row['item_type']}: {row['label']}" for row in review_rows}
    selected_item = st.selectbox("Concept or relation", list(item_options), format_func=item_options.get, key="review_item")
    item = next(row for row in review_rows if row["item_key"] == selected_item)
    if item["item_type"] == "concept":
        evidence = workflow.evidence_for_concept(candidate, item["item_key"])
        st.subheader(f"Source evidence for concept: {item['label']}")
        st.caption(f"Evidence status: {evidence['evidence_status']} · matched extraction candidates: {evidence['match_count']}")
        if evidence["candidate_matches"]:
            st.dataframe(pd.DataFrame(evidence["candidate_matches"]), use_container_width=True)
    else:
        raw_edge = next(edge for edge in graph.get("edges", []) if f"{edge.get('from', '')}|{edge.get('relation', '')}|{edge.get('to', '')}" == selected_item)
        evidence = workflow.evidence_for_edge(candidate, raw_edge)
        st.subheader(f"Source evidence for relation: {item['label']}")
        st.write(f"**Extracted reason:** {raw_edge.get('reason') or 'No reason was produced.'}")
        st.caption(f"Evidence status: {evidence['evidence_status']}. {evidence['review_question']}")
    if evidence["chunks"]:
        st.write("**Original extracted passages**")
        for chunk in evidence["chunks"]:
            with st.expander(f"Chunk {chunk.get('chunk_id')} · {chunk.get('word_count', 0)} words", expanded=False):
                st.text(chunk.get("text") or "")
    else:
        st.warning("No direct source chunk was linked to this item. This is evidence of an extraction traceability gap, not proof that the concept or relation is false.")
    decision_col, reviewer_col = st.columns(2)
    decision = decision_col.selectbox("Decision", ["approved", "rejected", "needs_correction"], key="review_decision")
    reviewer = reviewer_col.text_input("Reviewer", value="reviewer-1", key="reviewer_name")
    note = st.text_area("Evidence note / correction rationale", key="review_note")
    if st.button("Save review decision", key="save_review_decision"):
        workflow.save_review(candidate_id=selected_id, item_type=item["item_type"], item_key=selected_item, decision=decision, reviewer=reviewer, note=note)
        st.success("Review decision saved. Reloading the candidate summary.")
        st.rerun()
    with st.expander("Candidate graph JSON", expanded=False):
        st.json(graph)


def _uploaded_json(uploaded) -> dict | None:
    if uploaded is None:
        return None
    try:
        return json.loads(uploaded.getvalue().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def render_evaluation_lab(workflow: CandidateKGWorkflow) -> None:
    st.header("Evaluation Lab")
    st.caption("Run a stronger-model PDF judge as the main evaluation route, with an optional human-gold audit below. Engineering health checks do not substitute for either evaluation.")
    candidates = workflow.list_candidates()
    if not candidates:
        st.info("No candidate KG is ready for evaluation.")
        return
    labels = {row["candidate_id"]: f"{row['file_name']} · {row['candidate_id']}" for row in candidates}
    selected_id = st.selectbox("Candidate for evaluation", list(labels), format_func=labels.get, key="evaluation_candidate")
    aggregate_ids = st.multiselect(
        "PDFs included in overall evaluation",
        list(labels),
        default=[selected_id],
        format_func=labels.get,
        key="evaluation_aggregate_candidates",
        help="Overall metrics pool TP/FP/FN across selected PDFs; they do not average per-PDF F1 scores.",
    )
    aggregate_model = st.text_input("Overall-evaluation Judge model", value="gpt-4.1", key="kg_aggregate_judge_model")
    if st.button("Run overall evaluation for selected PDFs", key="run_overall_judge"):
        if not aggregate_ids:
            st.warning("Select at least one PDF for the overall evaluation.")
        else:
            per_file = []
            topic_totals = {key: 0 for key in ("tp", "fp", "fn")}
            edge_totals = {key: 0 for key in ("tp", "fp", "fn")}
            try:
                with st.spinner("Running the same Judge across the selected PDFs..."):
                    for candidate_id in aggregate_ids:
                        candidate_result = workflow.judge_with_llm(candidate=workflow.get(candidate_id), model=aggregate_model.strip())
                        topic_metrics = candidate_result["topic_metrics"]
                        edge_metrics = candidate_result["prerequisite_metrics"]
                        per_file.append({"file": workflow.get(candidate_id)["file_name"], "topic_f1": topic_metrics["f1"], "prerequisite_f1": edge_metrics["f1"], "topic_tp": topic_metrics["tp"], "topic_fp": topic_metrics["fp"], "topic_fn": topic_metrics["fn"], "edge_tp": edge_metrics["tp"], "edge_fp": edge_metrics["fp"], "edge_fn": edge_metrics["fn"]})
                        for key in topic_totals:
                            topic_totals[key] += int(topic_metrics[key])
                            edge_totals[key] += int(edge_metrics[key])
                def pooled_metrics(totals):
                    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 0.0
                    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else 0.0
                    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0, **totals}
                pooled = pd.DataFrame([{"metric_group": "topics", **pooled_metrics(topic_totals)}, {"metric_group": "prerequisites", **pooled_metrics(edge_totals)}])
                st.success("Overall evaluation complete. Metrics were pooled from all selected PDFs.")
                st.dataframe(pooled, use_container_width=True)
                st.caption("Overall P/R/F1 use pooled TP/FP/FN, not an average of per-PDF F1 values.")
                st.dataframe(pd.DataFrame(per_file), use_container_width=True)
            except Exception as exc:
                st.error(f"Overall evaluation failed: {exc}")
    st.subheader("Primary route — LLM-assisted PDF evaluation")
    st.caption("The judge reads this PDF's extracted text chunks, concepts and inferred prerequisite relations. It produces an item-level review ledger and Topic / Prerequisite P/R/F1. This is auxiliary evidence, not independent ground truth.")
    judge_model = st.text_input("Judge model", value="gpt-4.1", key="kg_judge_model", help="Use a model stronger than the extraction model. Change this name if your account uses a different available model.")
    if st.button("Run LLM-assisted evaluation", key="run_llm_judge"):
        try:
            with st.spinner("The judge is reviewing the PDF, concepts and relations..."):
                result = workflow.judge_with_llm(candidate=workflow.get(selected_id), model=judge_model.strip())
            metrics = pd.DataFrame([
                {"metric_group": "topics", **{key: result["topic_metrics"][key] for key in ("precision", "recall", "f1", "tp", "fp", "fn")}},
                {"metric_group": "prerequisites", **{key: result["prerequisite_metrics"][key] for key in ("precision", "recall", "f1", "tp", "fp", "fn")}},
            ])
            st.success("LLM-assisted evaluation complete. The JSON, summary CSV and item-level ledger CSV were saved.")
            st.dataframe(metrics, use_container_width=True)
            st.write(f"**Judge note:** {result['judge_ledger'].get('overall_note', '')}")
            rejected_rows = ([
                {"item_type": "topic", "decision": "unsupported", "item": row.get("name", ""), "reason": row.get("reason", "")} for row in result["judge_ledger"].get("unsupported_topics", [])
            ] + [
                {"item_type": "prerequisite", "decision": "rejected", "item": f"{row.get('from', '')} -> {row.get('to', '')}", "reason": row.get("reason", "")} for row in result["judge_ledger"].get("rejected_prerequisites", [])
            ])
            if rejected_rows:
                st.dataframe(pd.DataFrame(rejected_rows), use_container_width=True)
            for label, path in result["artifacts"].items():
                file_path = Path(path)
                if file_path.exists():
                    st.download_button(f"Download {label.replace('_', ' ')}", file_path.read_bytes(), file_name=file_path.name, key=f"judge_download_{label}")
        except Exception as exc:
            st.error(f"LLM-assisted evaluation failed: {exc}")
    st.divider()
    st.caption("Optional human audit route — upload a small independent sample only if you want to cross-check the LLM judge. It does not block the primary route.")
    gold_topic_upload = st.file_uploader("Gold concepts JSON (format: {\"topics\": [{\"name\": \"...\"}]})", type=["json"], key="gold_topics_upload")
    gold_edge_upload = st.file_uploader("Gold prerequisite JSON (format: {\"prerequisites\": [{\"from\": \"...\", \"to\": \"...\"}]})", type=["json"], key="gold_edges_upload")
    gold_topics = _uploaded_json(gold_topic_upload); gold_edges = _uploaded_json(gold_edge_upload)
    if gold_topic_upload and gold_topics is None or gold_edge_upload and gold_edges is None:
        st.error("One gold annotation file is not valid UTF-8 JSON.")
    if st.button("Run KG semantic evaluation", key="run_kg_evaluation"):
        if gold_topics is None or gold_edges is None:
            st.warning("Upload both gold annotation files first.")
        else:
            result = workflow.evaluate(candidate=workflow.get(selected_id), gold_topics=gold_topics, gold_prerequisites=gold_edges, output_prefix="kg_evaluation")
            metrics = pd.DataFrame([
                {"metric_group": "topics", **{key: result["topic_metrics"][key] for key in ("precision", "recall", "f1", "tp", "fp", "fn")}},
                {"metric_group": "prerequisites", **{key: result["prerequisite_metrics"][key] for key in ("precision", "recall", "f1", "tp", "fp", "fn")}},
            ])
            st.success("Evaluation complete. JSON, summary CSV and error-case CSV were written to the evaluation run folder.")
            st.dataframe(metrics, use_container_width=True)
            st.json(result["artifacts"])
    st.download_button("Download gold annotation starter", json.dumps({"topics": [{"name": "Example Concept"}], "prerequisites": [{"from": "Prerequisite Concept", "to": "Target Concept"}]}, ensure_ascii=False, indent=2), file_name="kg_gold_annotation_starter.json", mime="application/json")


def render_publish_sync(workflow: CandidateKGWorkflow) -> None:
    st.header("Publish & Sync")
    st.caption("Publication writes to the global KG, Neo4j and RAG. It is intentionally separate from PDF upload and requires a fully approved candidate.")
    candidates = workflow.list_candidates()
    if not candidates:
        st.info("No candidate resources are available.")
        return
    labels = {row["candidate_id"]: f"{row['file_name']} · {row['status']}" for row in candidates}
    selected_id = st.selectbox("Candidate to publish", list(labels), format_func=labels.get, key="publish_candidate")
    candidate = workflow.get(selected_id)
    summary = workflow.review_summary(candidate)
    st.json({"candidate": candidate, "review_summary": summary})
    approved = st.checkbox("I confirm that this reviewed candidate may update the published KG, Neo4j and RAG.", key="publish_confirm")
    if st.button("Publish approved candidate", disabled=not (summary["publishable"] and approved), key="publish_candidate_button"):
        paths = workflow.paths(candidate)
        try:
            merged = merge_global_kg(GLOBAL_KG_JSON, paths["graph"])
            global_stats = import_graph(GLOBAL_KG_JSON)
            resource_stats = import_graph(paths["graph"], auto_resource=True)
            rag_stats = ingest_stage1_chunks_with_report(paths["stage1"])
            artifacts = {"global_nodes": len(merged.get("nodes", [])), "global_edges": len(merged.get("edges", [])), "neo4j_global": global_stats, "neo4j_resource": resource_stats, "rag": rag_stats}
            workflow.mark_published(selected_id, artifacts)
            st.success("Published and synced to Neo4j/RAG.")
            st.json(artifacts)
        except Exception as exc:
            st.error(f"Publication failed; inspect the error before retrying: {exc}")


def render_reorganized_app() -> None:
    history = load_json_safe(HISTORY_JSON, [])
    processed = load_json_safe(PROCESSED_JSON, {})
    workflow = WORKFLOW

    st.title("Knowledge Provider & Evaluation Console" if lang == "English" else "知识资源与评估后台")
    st.caption("Candidate resources are reviewed before publication to the Neo4j/RAG production layer. Pathly remains the separate learner-facing app." if lang == "English" else "候选资源须经审核后才能发布到 Neo4j/RAG 正式层；Pathly 仍是独立的学习者前台。")

    top_tab_labels = [
        "Dashboard" if lang == "English" else "总览",
        "Resources" if lang == "English" else "资源入库",
        "KG Review" if lang == "English" else "KG 审核",
        "Evaluation Lab" if lang == "English" else "评估实验室",
        "Publish & Sync" if lang == "English" else "发布与同步",
        "Profile Insights" if lang == "English" else "画像洞察",
        "Runtime Health" if lang == "English" else "运行健康",
    ]

    dashboard_tab, resources_tab, review_tab, evaluation_tab, publish_tab, profile_tab, runtime_tab = st.tabs(top_tab_labels)

    with dashboard_tab:
        render_dashboard(workflow)

    with resources_tab:
        st.caption("Upload PDFs and build isolated candidate KGs. Review and publish explicitly before production sync." if lang == "English" else "上传 PDF 并构建隔离的候选 KG；审核通过后再显式发布。")
        if st.button("Register historical successful runs as candidates" if lang == "English" else "将历史成功运行登记为候选资源", key="register_historical_candidates"):
            count = register_existing_successful_runs(workflow)
            st.success(f"Registered {count} historical runs. They remain unpublished until reviewed.")
        uploaded_files = st.file_uploader(
            T["upload"],
            type=["pdf"],
            accept_multiple_files=True,
            key="kg_builder_upload",
        )
        action_col1, action_col2 = st.columns([1, 1])
        run_btn = action_col1.button(T["run"], key="kg_builder_run")
        show_global_btn = action_col2.button(T["show_stats"], key="kg_builder_show_stats")
        st.info("Pipeline completion creates a Candidate KG only. It will not update global KG, Neo4j or RAG until Publish & Sync.")

        if run_btn:
            if not uploaded_files:
                st.warning(T["warn_upload"])
            else:
                for up in uploaded_files:
                    raw = up.read()
                    digest = file_sha256(raw)
                    filename = up.name
                    doc_dir = build_doc_dir(RUN_DIR, filename, digest)
                    pdf_path = doc_dir / filename
                    doc_dir.mkdir(parents=True, exist_ok=True)
                    with open(pdf_path, "wb") as f:
                        f.write(raw)

                    stage_plan = build_stage_plan(doc_dir, pdf_path)
                    stage_names = [stage["key"] for stage in stage_plan]
                    manifest, manifest_path, run_log_path, recovery_state_path = ensure_manifest(
                        doc_dir=doc_dir,
                        file_name=filename,
                        digest=digest,
                        pdf_path=pdf_path,
                        pdf_size_bytes=len(raw),
                        stage_names=stage_names,
                    )
                    resume_from_stage = determine_resume_stage(manifest, stage_plan)
                    processed_digest = get_processed_digest(processed, filename)

                    if processed_digest == digest and manifest.get("status") == "success" and resume_from_stage is None:
                        st.info(f"{filename}: {T['skip']}")
                        skip_record = {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "file_name": filename,
                            "sha256": digest,
                            "status": "skipped_same_file",
                            "doc_dir": str(doc_dir),
                            "manifest_path": str(manifest_path),
                            "run_log_path": str(run_log_path),
                            "recovery_state_path": str(recovery_state_path),
                        }
                        history.append(skip_record)
                        append_json_record(BATCH_RUN_LOG_JSON, skip_record)
                        continue

                    manifest["run_attempts"] = int(manifest.get("run_attempts", 0)) + 1
                    manifest["status"] = "running"
                    manifest["last_attempt_at"] = now_iso()
                    manifest["summary"]["failed_stage"] = None
                    manifest["summary"]["next_resume_stage"] = resume_from_stage or stage_names[0]
                    manifest["summary"]["last_resume_from_stage"] = resume_from_stage
                    run_started_at = time.perf_counter()
                    save_manifest(manifest_path, manifest)
                    append_run_event(
                        run_log_path,
                        level="info",
                        message="Document pipeline started",
                        data={
                            "file_name": filename,
                            "sha256": digest,
                            "doc_dir": str(doc_dir),
                            "resume_from_stage": resume_from_stage,
                            "run_attempts": manifest["run_attempts"],
                        },
                    )
                    update_recovery_state(
                        recovery_state_path,
                        run_id=manifest["run_id"],
                        completed_stages=completed_stage_keys(manifest, stage_plan),
                        next_resume_stage=resume_from_stage or stage_names[0],
                        failed_stage=None,
                        can_resume=True,
                    )

                    st.subheader(f"{T['processing']}: {filename}")
                    log_box = st.empty()
                    resume_index = len(stage_plan) if resume_from_stage is None else stage_names.index(resume_from_stage)
                    failed_stage = None

                    for idx, stage in enumerate(stage_plan):
                        stage_key = stage["key"]
                        pre_validation = validate_stage_artifacts(stage)
                        stage_entry = manifest["stages"][stage_key]

                        if idx < resume_index:
                            stage_entry["reused_on_resume"] = True
                            stage_entry["input_paths"] = [str(path) for path in stage["input_paths"]]
                            stage_entry["output_paths"] = [str(path) for path in stage["output_paths"]]
                            stage_entry["validation"] = pre_validation
                            save_manifest(manifest_path, manifest)
                            append_run_event(
                                run_log_path,
                                level="info",
                                stage=stage_key,
                                message="Stage reused from previous successful output",
                                data={"output_paths": stage_entry["output_paths"]},
                            )
                            log_box.text(f"{stage_key}: resume reuse\n{tail_text(json.dumps(pre_validation, ensure_ascii=False, indent=2))}")
                            continue

                        if not pre_validation["inputs_ok"]:
                            failed_stage = stage_key
                            stage_entry["status"] = "failed"
                            stage_entry["input_paths"] = [str(path) for path in stage["input_paths"]]
                            stage_entry["output_paths"] = [str(path) for path in stage["output_paths"]]
                            stage_entry["validation"] = pre_validation
                            stage_entry["return_code"] = None
                            stage_entry["started_at"] = now_iso()
                            stage_entry["ended_at"] = now_iso()
                            stage_entry["duration_seconds"] = 0.0
                            save_json(
                                Path(stage_entry["log_json_path"]),
                                {
                                    "stage": stage_key,
                                    "error": "missing_stage_inputs",
                                    "validation": pre_validation,
                                },
                            )
                            Path(stage_entry["log_text_path"]).write_text(
                                json.dumps(pre_validation, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            append_run_event(
                                run_log_path,
                                level="error",
                                stage=stage_key,
                                message="Stage input validation failed",
                                data=pre_validation,
                            )
                            log_box.text(f"{stage_key}: input validation failed\n{json.dumps(pre_validation, ensure_ascii=False, indent=2)}")
                            break

                        stage_entry["status"] = "running"
                        stage_entry["attempts"] = int(stage_entry.get("attempts", 0)) + 1
                        stage_entry["started_at"] = now_iso()
                        stage_entry["input_paths"] = [str(path) for path in stage["input_paths"]]
                        stage_entry["output_paths"] = [str(path) for path in stage["output_paths"]]
                        stage_entry["validation"] = pre_validation
                        stage_entry["reused_on_resume"] = False
                        save_manifest(manifest_path, manifest)
                        append_run_event(
                            run_log_path,
                            level="info",
                            stage=stage_key,
                            message="Stage started",
                            data={"attempt": stage_entry["attempts"], "cwd": str(stage["cwd"])},
                        )

                        result = run_script_with_inputs(
                            stage["script_path"],
                            stage["inputs_for_script"],
                            cwd=stage["cwd"],
                        )
                        post_validation = validate_stage_artifacts(stage)
                        text_log_path, json_log_path = write_stage_logs(doc_dir, stage, result, post_validation)

                        stage_entry["ended_at"] = now_iso()
                        stage_entry["duration_seconds"] = result["duration_seconds"]
                        stage_entry["return_code"] = result["return_code"]
                        stage_entry["log_text_path"] = str(text_log_path)
                        stage_entry["log_json_path"] = str(json_log_path)
                        stage_entry["validation"] = post_validation
                        stage_entry["stdout_tail"] = tail_text(result["stdout"], 2000)
                        stage_entry["stderr_tail"] = tail_text(result["stderr"], 2000)
                        stage_entry["status"] = "success" if result["return_code"] == 0 and post_validation["outputs_ok"] else "failed"
                        save_manifest(manifest_path, manifest)

                        append_run_event(
                            run_log_path,
                            level="info" if stage_entry["status"] == "success" else "error",
                            stage=stage_key,
                            message="Stage finished",
                            data={
                                "return_code": result["return_code"],
                                "duration_seconds": result["duration_seconds"],
                                "outputs_ok": post_validation["outputs_ok"],
                            },
                        )
                        log_box.text(result["combined_log"][-4000:])

                        if stage_entry["status"] != "success":
                            failed_stage = stage_key
                            break

                    if failed_stage:
                        manifest["status"] = "failed"
                        manifest["summary"]["failed_stage"] = failed_stage
                        manifest["summary"]["next_resume_stage"] = failed_stage
                        manifest["summary"]["completed_stages"] = completed_stage_keys(manifest, stage_plan)
                        manifest["summary"]["duration_seconds"] = round(time.perf_counter() - run_started_at, 4)
                        save_manifest(manifest_path, manifest)
                        update_recovery_state(
                            recovery_state_path,
                            run_id=manifest["run_id"],
                            completed_stages=manifest["summary"]["completed_stages"],
                            next_resume_stage=failed_stage,
                            failed_stage=failed_stage,
                            can_resume=True,
                        )
                        failure_record = {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "file_name": filename,
                            "sha256": digest,
                            "status": f"failed_{failed_stage}",
                            "failed_stage": failed_stage,
                            "resume_from_stage": failed_stage,
                            "doc_dir": str(doc_dir),
                            "manifest_path": str(manifest_path),
                            "run_log_path": str(run_log_path),
                            "recovery_state_path": str(recovery_state_path),
                            "completed_stages": manifest["summary"]["completed_stages"],
                        }
                        history.append(failure_record)
                        append_json_record(BATCH_RUN_LOG_JSON, failure_record)
                        st.error(f"{failed_stage} failed")
                        continue

                    manifest["status"] = "success"
                    manifest["summary"]["failed_stage"] = None
                    manifest["summary"]["next_resume_stage"] = None
                    manifest["summary"]["completed_stages"] = stage_names
                    manifest["summary"]["duration_seconds"] = round(time.perf_counter() - run_started_at, 4)
                    save_manifest(manifest_path, manifest)
                    update_recovery_state(
                        recovery_state_path,
                        run_id=manifest["run_id"],
                        completed_stages=stage_names,
                        next_resume_stage=None,
                        failed_stage=None,
                        can_resume=False,
                    )
                    append_run_event(
                        run_log_path,
                        level="info",
                        message="Document pipeline completed",
                        data={"completed_stages": stage_names},
                    )

                    candidate = workflow.register(doc_dir=doc_dir, file_name=filename, sha256=digest)
                    success_record = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "file_name": filename,
                        "sha256": digest,
                        "status": "candidate_ready",
                        "candidate_id": candidate["candidate_id"],
                        "doc_dir": str(doc_dir),
                        "manifest_path": str(manifest_path),
                        "run_log_path": str(run_log_path),
                        "recovery_state_path": str(recovery_state_path),
                        "resume_from_stage": resume_from_stage,
                        "completed_stages": stage_names,
                    }
                    history.append(success_record)
                    append_json_record(BATCH_RUN_LOG_JSON, success_record)

                    st.success(f"{filename}: candidate KG is ready for review ({candidate['candidate_id']}).")
                    st.info("No global KG, Neo4j or RAG update was performed. Continue in KG Review and Publish & Sync.")

                save_json_safe(PROCESSED_JSON, processed)
                save_json_safe(HISTORY_JSON, history)

        if show_global_btn:
            g = load_json_safe(GLOBAL_KG_JSON, {"nodes": [], "edges": []})
            if len(g.get("nodes", [])) == 0 and len(g.get("edges", [])) == 0:
                st.info(T["global_empty"])
            else:
                metric_cols = st.columns(2)
                metric_cols[0].metric(T["nodes"], len(g.get("nodes", [])))
                metric_cols[1].metric(T["edges"], len(g.get("edges", [])))
                st.subheader(T["sample_nodes"])
                st.json(g.get("nodes", [])[:5])
                st.subheader(T["sample_edges"])
                st.json(g.get("edges", [])[:5])
                st.download_button(
                    T["download_global"],
                    data=json.dumps(g, ensure_ascii=False, indent=2),
                    file_name="global_knowledge_graph.json",
                    mime="application/json",
                    key="kg_builder_download_global",
                )

        kg = load_json_safe(GLOBAL_KG_JSON, {"nodes": [], "edges": []})
        nodes = kg.get("nodes", [])
        edges = kg.get("edges", [])
        st.subheader(T["nodes_table"])
        st.dataframe(pd.DataFrame(nodes), use_container_width=True)
        st.subheader(T["edges_table"])
        rel_options = sorted(list(set([e.get("relation", "") for e in edges if e.get("relation", "")])))
        rel_filter = st.multiselect(T["edge_filter"], options=rel_options, default=rel_options, key="kg_builder_edge_filter")
        edges_filtered = [e for e in edges if e.get("relation", "") in rel_filter] if rel_filter else edges
        st.dataframe(pd.DataFrame(edges_filtered), use_container_width=True)
        st.download_button(
            T["download_filtered"],
            data=json.dumps(edges_filtered, ensure_ascii=False, indent=2),
            file_name="filtered_edges.json",
            mime="application/json",
            key="kg_builder_download_filtered",
        )

        calibrated_graph = calibrate_graph(GLOBAL_KG_JSON)["graph"]
        calibrated_nodes = [node for node in calibrated_graph.get("nodes", []) if node.get("id")]
        diff_vals = [
            int(node["calibrated_difficulty_level"])
            for node in calibrated_nodes
            if str(node.get("calibrated_difficulty_level", "")).isdigit()
        ]

        if diff_vals:
            st.caption("Showing calibrated difficulty distribution, not the raw LLM-assigned field." if lang == "English" else "\u8fd9\u91cc\u5c55\u793a\u7684\u662f\u6821\u51c6\u540e\u7684\u96be\u5ea6\u5206\u5e03，\u4e0d\u662f\u539f\u59cb\u7684 LLM difficulty 字段。")
            df_diff = pd.DataFrame({"calibrated_difficulty_level": diff_vals})
            st.bar_chart(df_diff["calibrated_difficulty_level"].value_counts().sort_index())

        st.divider()
        render_topic_review(GLOBAL_KG_JSON)
        st.divider()
        st.header(T["history"])
        history_df = load_json_safe(HISTORY_JSON, [])
        if history_df:
            st.dataframe(pd.DataFrame(history_df[::-1]), use_container_width=True)
        else:
            st.info(T["no_history"])
    with review_tab:
        render_kg_review(workflow)

    with evaluation_tab:
        render_evaluation_lab(workflow)

    with publish_tab:
        render_publish_sync(workflow)
        published_candidates = [row for row in workflow.list_candidates() if row.get("status") == "published"]
        if published_candidates:
            st.divider()
            latest = published_candidates[0]
            st.subheader("Latest published resource status")
            status = build_sync_status(Path(latest["doc_dir"]), sync_neo4j=False)
            render_sync_status(status)

    with profile_tab:
        st.header("Profile Store" if lang == "English" else "画像存储")
        st.caption("Read-only profile inspection backed by SQLite. Pathly writes these records; Neo4j does not store learner state." if lang == "English" else "\u8fd9\u91cc\u662f\u57fa\u4e8e SQLite \u7684\u53ea\u8bfb\u753b\u50cf\u68c0\u89c6\u754c\u9762\u3002Pathly \u524d\u7aef\u4f1a\u5199\u5165\u8fd9\u4e9b\u6570\u636e\uff0cNeo4j \u4e0d\u4f1a\u4fdd\u5b58\u7528\u6237\u72b6\u6001\u3002")
        profiles = ensure_profiles_exist()
        if not profiles:
            st.warning("No learner profile is available yet. Pathly should create one first." if lang == "English" else "\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u7528\u7684\u5b66\u4e60\u8005\u753b\u50cf\uff0c\u9700\u8981\u5148\u7531 Pathly \u524d\u53f0\u521b\u5efa\u3002")
        else:
            st.info("Profiles are created from Pathly onboarding. This backend only supports inspection and export." if lang == "English" else "\u753b\u50cf\u7531 Pathly onboarding \u521b\u5efa\u3002\u8fd9\u4e2a\u540e\u53f0\u53ea\u63d0\u4f9b\u67e5\u770b\u548c\u5bfc\u51fa\u3002")
            selected_profile_for_view = st.selectbox(
                "Select learner profile to inspect" if lang == "English" else "选择要查看的学习者画像",
                profiles,
                format_func=build_profile_label,
                key="profile_tab_selected_profile",
            )
            render_profile_status(selected_profile_for_view, key_prefix="profile_tab")
            with st.expander("Profile Store verify", expanded=False):
                st.json(verify_profiles())
    with runtime_tab:
        st.caption("Safe infrastructure checks. The calibrate stage writes a separate calibrated graph and does not overwrite the original KG.")
        render_runtime_status(build_runtime_status())
        st.divider()
        harness_col1, harness_col2, harness_col3 = st.columns(3)
        harness_stage = harness_col1.selectbox(
            "Harness stage",
            ["all", "audit", "calibrate", "kg_benchmark", "profile", "rag", "reproducibility", "neo4j"],
            index=0,
            key="runtime_harness_stage",
        )
        harness_live_neo4j = harness_col2.checkbox("Live Neo4j check", value=False, key="runtime_harness_live_neo4j")
        harness_rag_collection = harness_col3.text_input("RAG collection", value="kg_chunks", key="runtime_harness_rag_collection")
        if st.button("Run Runtime Harness", key="runtime_harness_run"):
            try:
                manifest = run_harness(
                    stage=harness_stage,
                    graph_path=GLOBAL_KG_JSON,
                    live_neo4j=harness_live_neo4j,
                    rag_collection=harness_rag_collection,
                )
                if manifest.get("status") == "failed":
                    st.error(f"Harness failed: {manifest.get('manifest_path')}")
                elif manifest.get("status") == "warning":
                    st.warning(f"Harness completed with warning: {manifest.get('manifest_path')}")
                else:
                    st.success(f"Harness passed: {manifest.get('manifest_path')}")

                stage_rows = [
                    {
                        "stage": stage_name,
                        "status": stage_entry.get("status"),
                        "started_at": stage_entry.get("started_at"),
                        "ended_at": stage_entry.get("ended_at"),
                        "error": stage_entry.get("error", ""),
                    }
                    for stage_name, stage_entry in manifest.get("stages", {}).items()
                ]
                if stage_rows:
                    st.dataframe(pd.DataFrame(stage_rows), use_container_width=True)
                for stage_name, stage_entry in manifest.get("stages", {}).items():
                    with st.expander(f"{stage_name}: {stage_entry.get('status')}", expanded=stage_entry.get("status") != "success"):
                        st.json(stage_entry)
                with st.expander("Full harness manifest", expanded=False):
                    st.json(manifest)
            except Exception as exc:
                st.error(f"Runtime Harness failed: {exc}")


render_reorganized_app()
st.stop()
