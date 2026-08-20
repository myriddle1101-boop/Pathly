import os
import json
import networkx as nx
import matplotlib.pyplot as plt


def safe_print(msg: str):
    """Windows GBK 控制台安全打印"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("gbk", errors="ignore").decode("gbk", errors="ignore"))


def ask_path(prompt: str) -> str:
    p = input(prompt + "\n> ").strip().strip('"').strip("'")
    return p


def load_json(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_str(v):
    """GEXF 仅稳定支持标量，复杂对象转JSON字符串"""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return json.dumps(v, ensure_ascii=False)


def extract_topics(data):
    """
    支持:
    1) {"topics":[...]}
    2) [...]
    """
    if isinstance(data, dict):
        topics = data.get("topics", [])
    elif isinstance(data, list):
        topics = data
    else:
        topics = []

    out = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        name = (t.get("name") or "").strip()
        if not name:
            continue

        summary = t.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}

        # description 兜底
        desc = (t.get("description") or "").strip()
        if not desc:
            desc = f"Auto-generated topic: {name}"

        # difficulty 兜底（1~5）
        difficulty = summary.get("difficulty_level", None)
        if isinstance(difficulty, str) and difficulty.isdigit():
            difficulty = int(difficulty)
        if not isinstance(difficulty, int) or not (1 <= difficulty <= 5):
            difficulty = 3

        out.append({
            "name": name,
            "description": desc,
            "sub_topics": t.get("sub_topics", []),
            "summary": {
                "difficulty_level": difficulty,
                "target_audience": summary.get("target_audience", "Undergraduate"),
                "estimated_learning_time": summary.get("estimated_learning_time", "1-2 hours"),
                "prerequisites_summary": summary.get("prerequisites_summary", ""),
                "key_sub_concepts": summary.get("key_sub_concepts", []),
                "common_misconceptions": summary.get("common_misconceptions", []),
                "practical_applications": summary.get("practical_applications", [])
            }
        })
    return out


def extract_prerequisites(data):
    """
    支持:
    1) {"prerequisites":[...]}
    2) [...]
    """
    if isinstance(data, dict):
        rels = data.get("prerequisites", [])
    elif isinstance(data, list):
        rels = data
    else:
        rels = []
    return rels if isinstance(rels, list) else []


def extract_similarity(data):
    """
    支持:
    1) {"similarity_edges":[...]}
    2) [...]
    """
    if isinstance(data, dict):
        rels = data.get("similarity_edges", [])
    elif isinstance(data, list):
        rels = data
    else:
        rels = []
    return rels if isinstance(rels, list) else []


def build_graph(topics, prereq, sim):
    G = nx.DiGraph()

    # 节点
    for t in topics:
        s = t["summary"]
        G.add_node(
            t["name"],
            description=safe_str(t["description"]),
            sub_topics=safe_str(t.get("sub_topics", [])),
            difficulty_level=safe_str(s.get("difficulty_level")),
            target_audience=safe_str(s.get("target_audience")),
            estimated_learning_time=safe_str(s.get("estimated_learning_time")),
            prerequisites_summary=safe_str(s.get("prerequisites_summary")),
            key_sub_concepts=safe_str(s.get("key_sub_concepts", [])),
            common_misconceptions=safe_str(s.get("common_misconceptions", [])),
            practical_applications=safe_str(s.get("practical_applications", [])),
        )

    # 先修边
    for r in prereq:
        if not isinstance(r, dict):
            continue
        a = (r.get("from") or "").strip()
        b = (r.get("to") or "").strip()
        if a in G.nodes and b in G.nodes and a != b:
            G.add_edge(
                a, b,
                relation="prerequisite",
                reason=safe_str(r.get("reason", ""))
            )

    # 相似边
    for e in sim:
        if not isinstance(e, dict):
            continue
        a = (e.get("from") or "").strip()
        b = (e.get("to") or "").strip()
        if a in G.nodes and b in G.nodes and a != b:
            score = e.get("similarity", e.get("score", 0.0))
            try:
                score = float(score)
            except Exception:
                score = 0.0

            # 若已有边则附加相似度
            if G.has_edge(a, b):
                G[a][b]["similarity"] = score
            else:
                G.add_edge(a, b, relation="similarity", score=score)

    return G


def sanitize_graph_for_gexf(G):
    """确保所有属性都是GEXF可写类型"""
    H = nx.DiGraph()

    for n, d in G.nodes(data=True):
        nd = {}
        for k, v in d.items():
            nd[k] = safe_str(v)
        H.add_node(n, **nd)

    for u, v, d in G.edges(data=True):
        ed = {}
        for k, val in d.items():
            ed[k] = safe_str(val)
        H.add_edge(u, v, **ed)

    return H


def export_json_graph(G, out_json="knowledge_graph.json"):
    data = {"nodes": [], "edges": []}

    for n, d in G.nodes(data=True):
        node_obj = {"id": n}
        for k, v in d.items():
            node_obj[k] = safe_str(v)
        data["nodes"].append(node_obj)

    for u, v, d in G.edges(data=True):
        edge_obj = {"from": u, "to": v}
        for k, val in d.items():
            edge_obj[k] = safe_str(val)
        data["edges"].append(edge_obj)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    safe_print(f"[Saved] {out_json}")


def visualize_prereq(G, out_png="kg_prerequisite.png"):
    H = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if d.get("relation") == "prerequisite":
            H.add_edge(u, v)

    if H.number_of_edges() == 0:
        safe_print("[Info] No prerequisite edges. Skip prerequisite plot.")
        return

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(H, seed=42, k=1.2)
    nx.draw_networkx_nodes(H, pos, node_size=1800)
    nx.draw_networkx_edges(H, pos, arrows=True)
    nx.draw_networkx_labels(H, pos, font_size=9)
    plt.title("Prerequisite Graph")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png, dpi=220)
    plt.close()
    safe_print(f"[Saved] {out_png}")


def visualize_similarity(G, out_png="kg_similarity.png"):
    H = nx.Graph()
    for n in G.nodes:
        H.add_node(n)

    for u, v, d in G.edges(data=True):
        if d.get("relation") == "similarity":
            w = d.get("score", d.get("similarity", 0.0))
            try:
                w = float(w)
            except Exception:
                w = 0.0
            H.add_edge(u, v, weight=w)

    if H.number_of_edges() == 0:
        safe_print("[Info] No similarity edges. Skip similarity plot.")
        return

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(H, seed=42, k=1.2)
    widths = [1 + 4 * H[u][v]["weight"] for u, v in H.edges()]
    nx.draw_networkx_nodes(H, pos, node_size=1800)
    nx.draw_networkx_edges(H, pos, width=widths)
    nx.draw_networkx_labels(H, pos, font_size=9)
    plt.title("Similarity Graph")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png, dpi=220)
    plt.close()
    safe_print(f"[Saved] {out_png}")


def main():
    safe_print("=== Stage 4 v2: KG Merge & Visualization ===")

    p_topics = ask_path("Input stage3_topics_with_summary.json path")
    p_prereq = ask_path("Input stage2b_prerequisites.json path")
    p_sim = ask_path("Input stage2c_similarity_edges.json path")

    topics_data = load_json(p_topics)
    prereq_data = load_json(p_prereq)
    sim_data = load_json(p_sim)

    topics = extract_topics(topics_data)
    prereq = extract_prerequisites(prereq_data)
    sim = extract_similarity(sim_data)

    safe_print(f"[1] Topics: {len(topics)}")
    safe_print(f"[2] Prerequisites: {len(prereq)}")
    safe_print(f"[3] Similarity edges: {len(sim)}")

    G = build_graph(topics, prereq, sim)
    safe_print(f"[4] Graph nodes={G.number_of_nodes()}, edges={G.number_of_edges()}")

    # GEXF安全导出
    G_safe = sanitize_graph_for_gexf(G)
    nx.write_gexf(G_safe, "knowledge_graph.gexf")
    safe_print("[Saved] knowledge_graph.gexf")

    # JSON导出
    export_json_graph(G, "knowledge_graph.json")

    # 可视化
    visualize_prereq(G, "kg_prerequisite.png")
    visualize_similarity(G, "kg_similarity.png")

    safe_print("[OK] Stage4 completed.")


if __name__ == "__main__":
    main()

#python "d:/ic/master project/project_code/KG_construction/stage4_build_and_visualize_kg.py"