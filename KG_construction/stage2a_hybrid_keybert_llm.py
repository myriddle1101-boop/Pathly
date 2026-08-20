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
from infra.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_LLM_MODEL
from infra.device_manager import get_embedding_batch_size, load_with_device_fallback

load_project_env()


# ================= 配置 =================
MODEL_NAME = DEFAULT_LLM_MODEL
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


def build_keybert(force_device: str | None = None):
    def _loader(device: str) -> SentenceTransformer:
        return SentenceTransformer(DEFAULT_EMBEDDING_MODEL, device=device)

    sbert, runtime_info = load_with_device_fallback(
        _loader,
        component="stage2a.keybert",
        force_device=force_device,
    )
    print(
        "[Info] "
        f"torch={runtime_info['torch_version']}, "
        f"requested={runtime_info['requested_device']}, "
        f"selected={runtime_info['selected_device']}, "
        f"cuda_available={runtime_info['cuda_available']}, "
        f"fallback={runtime_info['fallback_applied']}"
    )
    if runtime_info.get("gpu_name"):
        print(f"[Info] GPU: {runtime_info['gpu_name']}")
    if runtime_info.get("fallback_reason"):
        print(f"[Warn] {runtime_info['fallback_reason']}")
    return KeyBERT(model=sbert), runtime_info


def keybert_recall(chunks: List[Dict[str, Any]], force_device: str | None = None):
    kw_model, runtime_info = build_keybert(force_device=force_device)
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
    return cands, runtime_info


# ================= LLM精修 =================
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("未检测到 OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def llm_refine_topics(client: OpenAI, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidate_lines = []
    for c in candidates:
        candidate_lines.append(f"- {c['name']} (freq={c['frequency']}, score={c['avg_score']})")
    cand_text = "\n".join(candidate_lines)

    prompt = f"""
You are refining candidate concepts for a university Machine Learning course knowledge graph.

Candidate phrases:
{cand_text}

Task:
Convert candidates into a practical Topic/Sub-Topic structure for learning graph construction.

Hard constraints:
1) Output between 8 and 15 topics (unless candidates are truly insufficient).
2) Prefer specific technical concepts over overly broad labels.
3) Do NOT keep only generic topics such as "Machine Learning" unless needed as one parent topic.
4) Remove header/footer/institution noise.
5) Merge obvious duplicates/synonyms, but DO NOT over-merge distinct concepts.
6) Topic names must be short noun phrases (1-4 words preferred).
7) Each topic should have 1-3 sub_topics when possible.

Coverage requirements (very important):
- Preserve major concepts that appear in candidates related to:
  neuron, artificial neural network, activation function, loss function,
  backpropagation, linear separation/separability, regression/classification, training.
- If a concept appears in candidates with reasonable frequency/score, try to keep it.

Output JSON only:
{{
  "topics": [
    {{
      "name": "...",
      "description": "1 concise sentence",
      "sub_topics": [
        {{"name": "...", "description": "1 concise sentence"}}
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

    # 二次补充请求：防止topic过少
    if len(topics) < 8:
        repair_prompt = f"""
You previously returned too few topics ({len(topics)}).
Please expand to 8-15 topics using the same candidates below.
Keep technical granularity and avoid only broad labels.

Candidates:
{cand_text}

Return JSON with key "topics" only.
"""
        resp2 = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": repair_prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )
        data2 = json.loads(resp2.choices[0].message.content)
        topics2 = data2.get("topics", [])
        if isinstance(topics2, list) and len(topics2) > len(topics):
            topics = topics2

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


def dedup_topics(topics):
    out, seen = [], set()

    for t in topics:
        # 1) 如果是字符串，自动转成标准topic对象
        if isinstance(t, str):
            name = t.strip()
            if not name:
                continue
            t = {
                "name": name,
                "description": "",
                "sub_topics": []
            }

        # 2) 如果不是dict也不是str，跳过
        if not isinstance(t, dict):
            continue

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
            if isinstance(s, str):
                sn = s.strip()
                if not sn:
                    continue
                s = {"name": sn, "description": ""}
            if not isinstance(s, dict):
                continue

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


def run_stage2a(in_path: str, out_path: str, force_device: str | None = None) -> dict[str, Any]:
    chunks = load_chunks(in_path)
    print(f"[1] 读取chunks成功：{len(chunks)}")

    # Step A: KeyBERT召回
    benchmark_start = time.perf_counter()
    candidates, runtime_info = keybert_recall(chunks, force_device=force_device)
    benchmark_duration = time.perf_counter() - benchmark_start
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
        "topics": topics,
        "benchmark": {
            "duration_seconds": round(benchmark_duration, 4),
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

    print("\n--- Top 15 Final Topics Preview ---")
    for i, t in enumerate(topics[:15], 1):
        print(f"{i:02d}. {t['name']}")

    print("\n Stage 2a 混合版完成")
    return output


def main():
    print("=== Stage 2a 真正混合版：KeyBERT召回 + LLM精修 ===")
    in_path = ask_input_path()
    out_path = ask_output_path()
    run_stage2a(in_path, out_path)


if __name__ == "__main__":
    main()
