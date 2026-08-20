import os
import re
import json
import time
from typing import List, Dict, Any

import torch
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from openai import OpenAI

from env_loader import load_project_env

load_project_env()


# ================= 配置 =================
MODEL_NAME = "gpt-4o-mini"
TOP_N_PER_CHUNK = 6
NGRAM_RANGE = (1, 2)
MAX_CANDIDATES_FOR_LLM = 80
MIN_SCORE = 0.18
MAX_TOPIC_WORDS = 4
SLEEP_BETWEEN_CALLS = 0.2

BAD_WORDS = {
    "imperial", "london", "figure", "week", "table", "content",
    "machinelearningfordesignengineers", "copyright"
}


# ================= IO =================
def ask_input_path():
    p = input("请输入 stage1_chunks.json 完整路径：\n> ").strip().strip('"').strip("'")
    return p


def ask_output_path(default_name="stage2a_topics_hybrid.json"):
    p = input(f"请输入输出JSON路径（回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p


def load_chunks(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到输入文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = []
    for item in data:
        t = item.get("text", "")
        if t and t.strip():
            chunks.append({
                "chunk_id": item.get("chunk_id", len(chunks) + 1),
                "text": t.strip()
            })
    return chunks


# ================= KeyBERT召回 =================
def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)
    return text.strip()


def clean_phrase(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    s = s.strip(".,;:()[]{}<>|/\\\"'")
    return s


def is_good_candidate(phrase: str, score: float) -> bool:
    if score < MIN_SCORE:
        return False
    if len(phrase) < 3:
        return False
    wc = len(phrase.split())
    if wc == 0 or wc > MAX_TOPIC_WORDS:
        return False

    low = phrase.lower()
    low_nospace = low.replace(" ", "")
    if re.fullmatch(r"[\d\W_]+", phrase):
        return False
    if any(b in low_nospace for b in BAD_WORDS):
        return False
    if any(len(tok) > 25 for tok in phrase.split()):
        return False
    return True


def build_keybert():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Info] torch={torch.__version__}, cuda_available={torch.cuda.is_available()}, device={device}")
    if device == "cuda":
        print(f"[Info] GPU: {torch.cuda.get_device_name(0)}")
    sbert = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device=device)
    return KeyBERT(model=sbert)


def keybert_recall(chunks: List[Dict[str, Any]]):
    kw_model = build_keybert()
    topic_map = {}

    for i, ch in enumerate(chunks, 1):
        print(f"[KeyBERT] chunk {i}/{len(chunks)} ...")
        text = clean_text(ch["text"])

        kws = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=NGRAM_RANGE,
            stop_words="english",
            use_maxsum=False,     # CPU友好
            nr_candidates=20,
            top_n=TOP_N_PER_CHUNK
        )

        for kw, sc in kws:
            phrase = clean_phrase(kw)
            score = float(sc)
            if not is_good_candidate(phrase, score):
                continue

            key = phrase.lower()
            if key not in topic_map:
                topic_map[key] = {
                    "name": phrase,
                    "score_sum": 0.0,
                    "freq": 0,
                    "chunk_ids": set()
                }
            topic_map[key]["score_sum"] += score
            topic_map[key]["freq"] += 1
            topic_map[key]["chunk_ids"].add(ch["chunk_id"])

    cands = []
    for _, v in topic_map.items():
        avg = v["score_sum"] / max(v["freq"], 1)
        cands.append({
            "name": v["name"],
            "avg_score": round(avg, 4),
            "frequency": v["freq"],
            "chunk_ids": sorted(list(v["chunk_ids"]))
        })

    cands.sort(key=lambda x: (x["frequency"], x["avg_score"]), reverse=True)
    cands = cands[:MAX_CANDIDATES_FOR_LLM]
    return cands


# ================= LLM精修 =================
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("未检测到 OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def llm_refine_topics(client: OpenAI, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 只给候选列表，不喂全文，省token
    candidate_lines = []
    for c in candidates:
        candidate_lines.append(f"- {c['name']} (freq={c['frequency']}, score={c['avg_score']})")
    cand_text = "\n".join(candidate_lines)

    prompt = f"""
You are building a Machine Learning course knowledge graph.

Given candidate topic phrases, refine them into clean Topics + Sub-Topics.

Candidate list:
{cand_text}

Rules:
1) Keep only true ML concepts (no headers/school names/noise).
2) Merge synonyms/variants (e.g., "artificial neural", "neural networks" if appropriate).
3) Topic name should be short noun phrase.
4) Provide concise description.
5) Each topic can have 0-3 sub_topics.
6) Output JSON only.

Output JSON format:
{{
  "topics": [
    {{
      "name": "...",
      "description": "...",
      "sub_topics": [
        {{"name": "...", "description": "..."}}
      ]
    }}
  ]
}}
"""

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    data = json.loads(resp.choices[0].message.content)
    topics = data.get("topics", [])
    if not isinstance(topics, list):
        topics = []
    return topics


# ================= 无额度降级（本地精修） =================
def local_refine_topics(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    简单规则精修：
    - 去重
    - 保留高频高分
    - 生成模板描述
    - 子主题用包含关系构建
    """
    # 先拿前40
    base = candidates[:40]
    names = [c["name"] for c in base]

    # 构建包含型子主题
    sub_map = {n: [] for n in names}
    for p in names:
        for ch in names:
            if p == ch:
                continue
            if p.lower() in ch.lower() and len(ch) > len(p):
                sub_map[p].append(ch)

    # 去重并截断
    for k in sub_map:
        uniq, seen = [], set()
        for x in sorted(sub_map[k], key=lambda z: len(z)):
            lx = x.lower()
            if lx not in seen:
                seen.add(lx)
                uniq.append(x)
        sub_map[k] = uniq[:2]

    topics = []
    for c in base:
        name = c["name"]
        topics.append({
            "name": name,
            "description": f"Auto-refined from KeyBERT candidates (freq={c['frequency']}, score={c['avg_score']}).",
            "sub_topics": [{"name": s, "description": f"Sub concept of {name}"} for s in sub_map.get(name, [])]
        })
    return topics


def dedup_topics(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for t in topics:
        name = (t.get("name") or "").strip()
        if not name:
            continue
        k = name.lower()
        if k in seen:
            continue
        seen.add(k)

        desc = (t.get("description") or "").strip()
        subs = t.get("sub_topics", [])
        if not isinstance(subs, list):
            subs = []

        clean_subs, sub_seen = [], set()
        for s in subs:
            sn = (s.get("name") or "").strip()
            if not sn:
                continue
            sk = sn.lower()
            if sk in sub_seen:
                continue
            sub_seen.add(sk)
            clean_subs.append({
                "name": sn,
                "description": (s.get("description") or "").strip()
            })

        out.append({
            "name": name,
            "description": desc,
            "sub_topics": clean_subs
        })
    return out


def main():
    print("=== Stage 2a 真正混合版：KeyBERT召回 + LLM精修 ===")
    in_path = ask_input_path()
    out_path = ask_output_path()

    chunks = load_chunks(in_path)
    print(f"[1] 读取chunks成功：{len(chunks)}")

    # Step A: KeyBERT召回
    candidates = keybert_recall(chunks)
    print(f"[2] KeyBERT候选数：{len(candidates)}")

    # Step B: LLM精修（失败则本地降级）
    method = "hybrid_keybert_llm"
    topics = []
    try:
        client = get_openai_client()
        topics = llm_refine_topics(client, candidates)
        time.sleep(SLEEP_BETWEEN_CALLS)
        print("[3] LLM精修完成")
    except Exception as e:
        msg = str(e)
        if ("insufficient_quota" in msg) or ("429" in msg) or ("RateLimitError" in msg):
            print("[Warn] LLM额度不足/限流，自动降级为本地精修")
            method = "hybrid_keybert_local_fallback"
            topics = local_refine_topics(candidates)
        else:
            print(f"[Warn] LLM调用失败，自动降级。原因: {e}")
            method = "hybrid_keybert_local_fallback"
            topics = local_refine_topics(candidates)

    topics = dedup_topics(topics)
    print(f"[4] 最终Topic数：{len(topics)}，method={method}")

    output = {
        "stage": "2a",
        "method": method,
        "input_chunks": len(chunks),
        "candidate_count": len(candidates),
        "topics_count": len(topics),
        "candidates": candidates,   # 保留候选，便于你做对比分析
        "topics": topics
    }

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[Saved] {out_path}")

    print("\n--- Top 15 Final Topics Preview ---")
    for i, t in enumerate(topics[:15], 1):
        print(f"{i:02d}. {t['name']}")

    print("\n✅ Stage 2a 混合版完成")


if __name__ == "__main__":
    main()
