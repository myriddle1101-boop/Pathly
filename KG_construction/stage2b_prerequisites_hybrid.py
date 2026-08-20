import os
import json
from typing import List, Dict, Any
from openai import OpenAI

from env_loader import load_project_env

load_project_env()

# ========= 配置 =========
MODEL_NAME = os.getenv("KG_RELATION_MODEL", "gpt-4o-mini")

# 规则回退用（可按你的课程补充）
RULES = [
    ("Linear Algebra", "Gradient Descent", "Gradient updates rely on vector/matrix operations."),
    ("Calculus", "Gradient Descent", "Gradients and derivatives come from calculus."),
    ("Probability", "Bayesian Methods", "Bayesian inference is built on probability theory."),
    ("Neurons", "Artificial Neural Networks", "Neural networks are compositions of neurons."),
    ("Activation Function", "Backpropagation", "Backprop depends on activation derivatives."),
    ("Loss Function", "Backpropagation", "Backprop computes gradients of the loss."),
    ("Backpropagation", "Training", "Training neural nets typically uses backprop."),
]


def ask_input_path():
    p = input("请输入 stage2a_topics_hybrid.json 完整路径：\n> ").strip().strip('"').strip("'")
    return p


def ask_output_path(default_name="stage2b_prerequisites.json"):
    p = input(f"请输入输出JSON路径（回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p


def load_topics(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到输入文件: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 兼容结构：{"topics":[...]} 或直接 [...]
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


def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("未检测到 OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def extract_prereq_with_llm(client: OpenAI, topics: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    topic_lines = "\n".join([f"- {t['name']}: {t['description']}" for t in topics])

    prompt = f"""
You are building a knowledge graph for a machine learning course.

Given topics:
{topic_lines}

Task:
Infer ONLY strong prerequisite relations and classify every candidate relation.
Definition:
A -> B means mastering A is necessary before learning B.

Rules:
1) A relation_type must be one of: strong_prerequisite, hierarchy, related, application_or_sequence, no_relation.
2) Only output strong_prerequisite relations in the final prerequisites list.
3) Do not treat parent-to-child taxonomy as a prerequisite.
4) Do not treat course presentation order or co-occurrence as a prerequisite.
5) Do not treat an application/result as a prerequisite for the method that produced it.
6) Avoid cycles and use exact topic names from the list.
7) If uncertain, skip the relation.

Output JSON only:
{{
  "prerequisites": [
    {{
      "from": "Topic A",
      "to": "Topic B",
      "relation_type": "strong_prerequisite",
      "reason": "short reason"
    }}
  ]
}}
"""

    request = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    # GPT-5.5 currently rejects an explicit temperature=0 in Chat Completions.
    # Keep the legacy deterministic setting for older models, while allowing the
    # GPT-5.5 default and preserving structured JSON output.
    if not MODEL_NAME.startswith("gpt-5.5"):
        request["temperature"] = 0
    resp = client.chat.completions.create(**request)
    data = json.loads(resp.choices[0].message.content)
    rels = data.get("prerequisites", [])
    if not isinstance(rels, list):
        rels = []
    return rels


def extract_prereq_with_rules(topics: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    names = {t["name"] for t in topics}
    rels = []

    # 简单大小写宽松匹配
    def has_topic(target):
        target_low = target.lower()
        for n in names:
            if n.lower() == target_low:
                return n
        return None

    for a, b, reason in RULES:
        aa = has_topic(a)
        bb = has_topic(b)
        if aa and bb and aa != bb:
            rels.append({"from": aa, "to": bb, "reason": reason})

    return rels


def normalize_and_filter(rels: List[Dict[str, str]], valid_names: set) -> List[Dict[str, str]]:
    out = []
    seen = set()

    for r in rels:
        a = (r.get("from") or "").strip()
        b = (r.get("to") or "").strip()
        reason = (r.get("reason") or "").strip()

        if not a or not b or a == b:
            continue
        if a not in valid_names or b not in valid_names:
            continue

        key = (a.lower(), b.lower())
        if key in seen:
            continue
        seen.add(key)

        relation_type = (r.get("relation_type") or "strong_prerequisite").strip().lower()
        if relation_type != "strong_prerequisite":
            continue
        out.append({
            "from": a,
            "to": b,
            "relation_type": relation_type,
            "reason": reason if reason else "Prerequisite relation inferred."
        })

    return out


def main():
    print("=== Stage 2b: 先修关系（LLM优先 + 规则回退）===")

    in_path = ask_input_path()
    out_path = ask_output_path()

    topics = load_topics(in_path)
    print(f"[1] 读取Topic数量: {len(topics)}")
    if len(topics) < 2:
        raise ValueError("Topic数量不足，无法推断先修关系。")

    names = {t["name"] for t in topics}

    method = "llm"
    rels = []
    try:
        client = get_client()
        rels = extract_prereq_with_llm(client, topics)
        print("[2] LLM先修关系提取完成")
    except Exception as e:
        msg = str(e)
        if ("insufficient_quota" in msg) or ("429" in msg) or ("RateLimitError" in msg):
            print("[Warn] LLM额度不足/限流，回退规则法")
        else:
            print(f"[Warn] LLM调用失败，回退规则法: {e}")
        method = "rules_fallback"
        rels = extract_prereq_with_rules(topics)

    rels = normalize_and_filter(rels, names)
    print(f"[3] 最终先修关系数量: {len(rels)} | method={method}")

    output = {
        "stage": "2b",
        "method": method,
        "topic_count": len(topics),
        "prerequisite_count": len(rels),
        "prerequisites": rels
    }

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[Saved] {out_path}")

    print("\n--- Prerequisite Preview (Top 15) ---")
    for i, r in enumerate(rels[:15], 1):
        print(f"{i:02d}. {r['from']} -> {r['to']} | {r['reason']}")

    print("\n Stage 2b 完成")


if __name__ == "__main__":
    main()

#运行方式：python "d:/ic/master project/project_code/KG_construction/stage2b_prerequisites_hybrid.py"
