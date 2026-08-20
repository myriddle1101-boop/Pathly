import json
import os
import time
from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer

from infra.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_SIMILARITY_THRESHOLD, DEFAULT_TOP_K
from infra.device_manager import get_embedding_batch_size, load_with_device_fallback

# ========= 配置 =========
SIM_THRESHOLD = DEFAULT_SIMILARITY_THRESHOLD
TOP_K_PER_TOPIC = DEFAULT_TOP_K
MODEL_NAME = DEFAULT_EMBEDDING_MODEL


def ask_input_path():
    p = input("请输入 stage2a_topics_hybrid.json 完整路径：\n> ").strip().strip('"').strip("'")
    return p


def ask_output_path(default_name="stage2c_similarity_edges.json"):
    p = input(f"请输入输出JSON路径（回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p


def load_topics(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到输入文件: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        topics = data.get("topics", [])
    elif isinstance(data, list):
        topics = data
    else:
        topics = []

    clean = []
    for t in topics:
        name = (t.get("name") or "").strip()
        if not name:
            continue
        clean.append({
            "name": name,
            "description": (t.get("description") or "").strip()
        })
    return clean


def build_topic_text(t: Dict[str, str]) -> str:
    # 用 name + description 做语义表示
    if t["description"]:
        return f"{t['name']}. {t['description']}"
    return t["name"]


def cosine_sim_matrix(embeddings: np.ndarray) -> np.ndarray:
    # embeddings 已归一化时，点积=余弦相似度
    return np.matmul(embeddings, embeddings.T)


def compute_similarity_edges(
    topics: List[Dict[str, str]],
    threshold=0.72,
    top_k=5,
    force_device: str | None = None,
):
    texts = [build_topic_text(t) for t in topics]
    names = [t["name"] for t in topics]

    def _loader(device: str) -> SentenceTransformer:
        return SentenceTransformer(MODEL_NAME, device=device)

    model, runtime_info = load_with_device_fallback(
        _loader,
        component="stage2c.similarity",
        force_device=force_device,
    )
    embs = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=get_embedding_batch_size(runtime_info["selected_device"]),
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    sim = cosine_sim_matrix(np.array(embs))

    n = len(names)
    edges = []

    # 为了防止太密，按每个topic只保留top_k个高相似邻居
    for i in range(n):
        pairs = []
        for j in range(n):
            if i == j:
                continue
            s = float(sim[i, j])
            if s >= threshold:
                pairs.append((j, s))

        # 每个点只取 top_k
        pairs = sorted(pairs, key=lambda x: x[1], reverse=True)[:top_k]

        for j, s in pairs:
            a, b = names[i], names[j]
            # 用有序键去重（无向相似）
            u, v = sorted([a, b])
            edges.append((u, v, s))

    # 全局去重：同一对只保留最高分
    best = {}
    for u, v, s in edges:
        key = (u, v)
        if key not in best or s > best[key]:
            best[key] = s

    final_edges = [
        {"from": k[0], "to": k[1], "similarity": round(v, 4)}
        for k, v in best.items()
    ]
    final_edges.sort(key=lambda x: x["similarity"], reverse=True)
    return final_edges, runtime_info


def run_stage2c(in_path: str, out_path: str, force_device: str | None = None) -> dict[str, Any]:
    topics = load_topics(in_path)
    print(f"[1] 读取Topic数量: {len(topics)}")
    if len(topics) < 2:
        raise ValueError("Topic数量不足，无法计算相似关系")

    benchmark_start = time.perf_counter()
    edges, runtime_info = compute_similarity_edges(
        topics=topics,
        threshold=SIM_THRESHOLD,
        top_k=TOP_K_PER_TOPIC,
        force_device=force_device,
    )
    duration = time.perf_counter() - benchmark_start
    print(f"[2] 相似关系数量: {len(edges)} (threshold={SIM_THRESHOLD}, top_k={TOP_K_PER_TOPIC})")

    output = {
        "stage": "2c",
        "method": "sbert_cosine",
        "model": MODEL_NAME,
        "topic_count": len(topics),
        "similarity_count": len(edges),
        "threshold": SIM_THRESHOLD,
        "top_k_per_topic": TOP_K_PER_TOPIC,
        "similarity_edges": edges,
        "benchmark": {
            "duration_seconds": round(duration, 4),
            "device_info": runtime_info,
            "batch_size": get_embedding_batch_size(runtime_info["selected_device"]),
        },
    }

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[Saved] {out_path}")

    print("\n--- Similarity Preview (Top 15) ---")
    for i, e in enumerate(edges[:15], 1):
        print(f"{i:02d}. {e['from']} <-> {e['to']} | sim={e['similarity']}")

    print("\n Stage 2c 完成")
    return output


def main():
    print("=== Stage 2c: Topic相似关系（SBERT）===")

    in_path = ask_input_path()
    out_path = ask_output_path()
    run_stage2c(in_path, out_path)


if __name__ == "__main__":
    main()

#运行方式：python "d:/ic/master project/project_code/KG_construction/stage2c_similarity.py"
