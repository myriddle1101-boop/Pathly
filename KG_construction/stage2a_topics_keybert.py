import os
import re
import json
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer


# ========= 可调参数 =========
TOP_N_PER_CHUNK = 8               # 每个chunk提取关键词数量
NGRAM_RANGE = (1, 3)              # 关键词n-gram范围
MIN_TOPIC_LEN = 2                 # 最短topic字符数
MAX_TOPICS_FINAL = 120            # 最终最多保留多少个topic
SUBTOPIC_TOP_K = 3                # 每个topic最多挂多少子主题
SCORE_THRESHOLD = 0.15            # 关键词最低分阈值（可根据效果调整）


def ask_input_json_path() -> str:
    p = input("请输入 stage1_chunks.json 的完整路径：\n> ").strip().strip('"').strip("'")
    return p


def ask_output_json_path(default_name="stage2a_topics_keybert.json") -> str:
    p = input(f"请输入输出JSON路径（直接回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p


def normalize_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def clean_topic_name(s: str) -> str:
    s = normalize_text(s)
    # 去掉一些明显噪声字符
    s = s.strip(".,;:()[]{}<>|/\\\"'")
    return s


def load_chunks(chunks_json_path: str):
    if not os.path.exists(chunks_json_path):
        raise FileNotFoundError(f"找不到文件: {chunks_json_path}")

    with open(chunks_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 兼容格式：[{chunk_id, text, ...}, ...]
    chunks = []
    for item in data:
        t = item.get("text", "")
        if t and t.strip():
            chunks.append({
                "chunk_id": item.get("chunk_id", len(chunks) + 1),
                "text": t.strip(),
                "word_count": item.get("word_count", len(t.split()))
            })
    return chunks


def build_keybert():
    # 复用多语种句向量模型
    sbert = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    kw_model = KeyBERT(model=sbert)
    return kw_model


def extract_candidates_from_chunk(kw_model, chunk_text: str, top_n=8):
    kws = kw_model.extract_keywords(
        chunk_text,
        keyphrase_ngram_range=NGRAM_RANGE,
        stop_words=None,              # 保持中英文兼容
        use_maxsum=True,              # 降低重复关键词
        nr_candidates=30,
        top_n=top_n
    )
    # kws: [(keyword, score), ...]
    cleaned = []
    for kw, sc in kws:
        name = clean_topic_name(kw)
        if len(name) < MIN_TOPIC_LEN:
            continue
        if sc < SCORE_THRESHOLD:
            continue
        cleaned.append((name, float(sc)))
    return cleaned


def aggregate_topics(chunks, kw_model):
    """
    聚合策略：
    - 对每个chunk提关键词
    - 全局按topic名聚合（累计分数、出现次数、来源chunk）
    """
    topic_map = {}

    for ch in chunks:
        chunk_id = ch["chunk_id"]
        text = ch["text"]

        candidates = extract_candidates_from_chunk(
            kw_model=kw_model,
            chunk_text=text,
            top_n=TOP_N_PER_CHUNK
        )

        for name, score in candidates:
            if name not in topic_map:
                topic_map[name] = {
                    "name": name,
                    "score_sum": 0.0,
                    "count": 0,
                    "chunk_ids": set(),
                }
            topic_map[name]["score_sum"] += score
            topic_map[name]["count"] += 1
            topic_map[name]["chunk_ids"].add(chunk_id)

    # 转list并排序
    topics = []
    for _, v in topic_map.items():
        avg_score = v["score_sum"] / max(v["count"], 1)
        topics.append({
            "name": v["name"],
            "avg_score": round(avg_score, 4),
            "frequency": v["count"],
            "chunk_ids": sorted(list(v["chunk_ids"]))
        })

    # 排序：先按频次，再按平均分
    topics.sort(key=lambda x: (x["frequency"], x["avg_score"]), reverse=True)
    return topics


def build_subtopics_simple(topics):
    """
    简单规则：
    - 如果A是B的子串，且A更短，A更可能是topic，B作为sub-topic候选
    - 每个topic最多挂 SUBTOPIC_TOP_K 个
    """
    names = [t["name"] for t in topics]
    name_set = set(names)

    sub_map = {n: [] for n in names}

    for parent in names:
        for child in names:
            if parent == child:
                continue
            # child包含parent，且child更长 => 作为子主题候选
            if parent in child and len(child) > len(parent):
                sub_map[parent].append(child)

    # 去重 + 截断
    for k in sub_map:
        uniq = []
        seen = set()
        for x in sorted(sub_map[k], key=lambda z: len(z)):
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        sub_map[k] = uniq[:SUBTOPIC_TOP_K]

    # 组装最终结构
    final = []
    for t in topics[:MAX_TOPICS_FINAL]:
        name = t["name"]
        sub_topics = [{"name": s, "description": f"{name} 的细化概念"} for s in sub_map.get(name, [])]

        final.append({
            "name": name,
            "description": f"由KeyBERT从课程语义块自动提取（出现{t['frequency']}次，平均相关度{t['avg_score']}）",
            "sub_topics": sub_topics,
            "meta": {
                "avg_score": t["avg_score"],
                "frequency": t["frequency"],
                "chunk_ids": t["chunk_ids"]
            }
        })
    return final


def main():
    print("=== Stage 2a: KeyBERT Topic提取（离线） ===")

    in_path = ask_input_json_path()
    out_path = ask_output_json_path()

    chunks = load_chunks(in_path)
    print(f"[1] 读取chunks成功：{len(chunks)} 个")

    kw_model = build_keybert()
    print("[2] KeyBERT模型加载完成")

    ranked_topics = aggregate_topics(chunks, kw_model)
    print(f"[3] 候选Topic数：{len(ranked_topics)}")

    final_topics = build_subtopics_simple(ranked_topics)
    print(f"[4] 最终Topic数（截断后）：{len(final_topics)}")

    output = {
        "stage": "2a",
        "method": "keybert_offline",
        "input_chunks": len(chunks),
        "topics_count": len(final_topics),
        "topics": final_topics
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True) if os.path.dirname(out_path) else None
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[Saved] {out_path}")

    # 预览前10个
    print("\n--- Top 10 Topics Preview ---")
    for i, t in enumerate(final_topics[:10], 1):
        print(f"{i:02d}. {t['name']}  | freq={t['meta']['frequency']} | score={t['meta']['avg_score']}")

    print("\n Stage 2a 完成（离线KeyBERT版）")


if __name__ == "__main__":
    main()