import os
import re
import json
import torch
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer

# ========= 参数 =========
TOP_N_PER_CHUNK = 6
NGRAM_RANGE = (1, 2)          # 限制到1~2gram，减少长句
MIN_TOPIC_CHAR = 3
MAX_TOPIC_WORDS = 4
MAX_TOPICS_FINAL = 50
SCORE_THRESHOLD = 0.20

BAD_WORDS = {
    "imperial", "london", "figure", "week",
    "machinelearningfordesignengineers",
    "tableof", "content"
}


def ask_input_path():
    p = input("请输入 stage1_chunks.json 完整路径：\n> ").strip().strip('"').strip("'")
    return p


def ask_output_path(default_name="stage2a_topics_keybert_gpu.json"):
    p = input(f"请输入输出JSON路径（回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p


def load_chunks(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到输入文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = []
    for item in data:
        text = item.get("text", "")
        if text and text.strip():
            chunks.append({
                "chunk_id": item.get("chunk_id", len(chunks) + 1),
                "text": text.strip(),
                "word_count": item.get("word_count", len(text.split()))
            })
    return chunks


def clean_chunk_text(text: str) -> str:
    # 换行和多空格清理
    text = re.sub(r"\s+", " ", text)

    # 小写->大写处补空格：linearseparationWe -> linearseparation We
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # 字母数字边界补空格
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)

    # 去掉过多符号
    text = re.sub(r"[|•·■◆►]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_topic_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(".,;:()[]{}<>|/\\\"'")
    return s


def is_good_topic(name: str, score: float) -> bool:
    if score < SCORE_THRESHOLD:
        return False
    if len(name) < MIN_TOPIC_CHAR:
        return False

    wc = len(name.split())
    if wc == 0 or wc > MAX_TOPIC_WORDS:
        return False

    low = name.lower()
    low_no_space = low.replace(" ", "")

    # 纯数字/符号过滤
    if re.fullmatch(r"[\d\W_]+", name):
        return False

    # 噪声词过滤
    for b in BAD_WORDS:
        if b in low_no_space:
            return False

    # 太长token（常见粘连垃圾）
    for token in name.split():
        if len(token) > 25:
            return False

    return True


def build_keybert_gpu():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Info] torch={torch.__version__}, cuda_available={torch.cuda.is_available()}")
    if device == "cuda":
        print(f"[Info] Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("[Info] Using CPU (未检测到CUDA)")

    sbert = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device=device)
    kw_model = KeyBERT(model=sbert)
    return kw_model


def extract_candidates(kw_model, chunk_text: str, top_n=6):
    text = clean_chunk_text(chunk_text)

    kws = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=NGRAM_RANGE,
        stop_words="english",   # 英文slides建议启用
        use_maxsum=True,
        nr_candidates=20,
        top_n=top_n
    )

    out = []
    for kw, sc in kws:
        name = clean_topic_name(kw)
        if is_good_topic(name, float(sc)):
            out.append((name, float(sc)))
    return out


def aggregate_topics(chunks, kw_model):
    topic_map = {}
    total = len(chunks)

    for i, ch in enumerate(chunks, 1):
        print(f"[KeyBERT] chunk {i}/{total} ...")
        cands = extract_candidates(kw_model, ch["text"], TOP_N_PER_CHUNK)

        for name, score in cands:
            if name not in topic_map:
                topic_map[name] = {
                    "name": name,
                    "score_sum": 0.0,
                    "count": 0,
                    "chunk_ids": set()
                }
            topic_map[name]["score_sum"] += score
            topic_map[name]["count"] += 1
            topic_map[name]["chunk_ids"].add(ch["chunk_id"])

    # 排序
    topics = []
    for _, v in topic_map.items():
        avg_score = v["score_sum"] / max(v["count"], 1)
        topics.append({
            "name": v["name"],
            "avg_score": round(avg_score, 4),
            "frequency": v["count"],
            "chunk_ids": sorted(list(v["chunk_ids"]))
        })

    topics.sort(key=lambda x: (x["frequency"], x["avg_score"]), reverse=True)
    return topics


def build_subtopics_simple(ranked_topics):
    names = [t["name"] for t in ranked_topics]
    sub_map = {n: [] for n in names}

    for p in names:
        for c in names:
            if p == c:
                continue
            if p in c and len(c) > len(p):
                sub_map[p].append(c)

    # 每个topic最多2个子主题
    for k in sub_map:
        uniq = []
        seen = set()
        for x in sorted(sub_map[k], key=lambda z: len(z)):
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        sub_map[k] = uniq[:2]

    final_topics = []
    for t in ranked_topics[:MAX_TOPICS_FINAL]:
        name = t["name"]
        subs = [{"name": s, "description": f"{name} 的细化概念"} for s in sub_map.get(name, [])]
        final_topics.append({
            "name": name,
            "description": f"KeyBERT离线提取（出现{t['frequency']}次，平均相关度{t['avg_score']}）",
            "sub_topics": subs,
            "meta": {
                "avg_score": t["avg_score"],
                "frequency": t["frequency"],
                "chunk_ids": t["chunk_ids"]
            }
        })
    return final_topics


def main():
    print("=== Stage 2a 增强版（GPU优先）===")

    in_path = ask_input_path()
    out_path = ask_output_path()

    chunks = load_chunks(in_path)
    print(f"[1] 读取chunks成功：{len(chunks)} 个")

    kw_model = build_keybert_gpu()
    print("[2] KeyBERT模型加载完成")

    ranked = aggregate_topics(chunks, kw_model)
    print(f"[3] 候选Topic数：{len(ranked)}")

    final_topics = build_subtopics_simple(ranked)
    print(f"[4] 最终Topic数：{len(final_topics)}")

    output = {
        "stage": "2a",
        "method": "keybert_offline_gpu_enhanced",
        "input_chunks": len(chunks),
        "topics_count": len(final_topics),
        "topics": final_topics
    }

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[Saved] {out_path}")

    print("\n--- Top 15 Topics Preview ---")
    for i, t in enumerate(final_topics[:15], 1):
        print(f"{i:02d}. {t['name']} | freq={t['meta']['frequency']} | score={t['meta']['avg_score']}")

    print("\n Stage 2a 增强版完成")


if __name__ == "__main__":
    main()