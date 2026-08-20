import os
import json
from typing import List, Dict, Any
from openai import OpenAI

from env_loader import load_project_env

load_project_env()

MODEL_NAME = "gpt-4o-mini"

def ask_input_path():
    p = input("请输入 stage2a_topics_hybrid.json 路径：\n> ").strip().strip('"').strip("'")
    return p

def ask_output_path(default_name="stage3_topics_with_summary.json"):
    p = input(f"请输入输出路径（回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p

def load_topics(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    topics = data.get("topics", data if isinstance(data, list) else [])
    clean = []
    for t in topics:
        name = (t.get("name") or "").strip()
        if not name:
            continue
        clean.append({
            "name": name,
            "description": (t.get("description") or "").strip(),
            "sub_topics": t.get("sub_topics", [])
        })
    return clean

def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("未检测到 OPENAI_API_KEY")
    return OpenAI(api_key=api_key)

def llm_summary(client: OpenAI, topic: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""
You are generating a structured learning summary for a machine learning concept.

Concept name: {topic['name']}
Description: {topic.get('description','')}

Return JSON only:
{{
  "difficulty_level": 1,
  "target_audience": "Undergraduate",
  "estimated_learning_time": "1-2 hours",
  "prerequisites_summary": "...",
  "key_sub_concepts": ["...", "..."],
  "common_misconceptions": ["...", "..."],
  "practical_applications": ["...", "..."]
}}

Constraints:
- difficulty_level must be integer 1-5
- concise and educational
"""
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    return json.loads(resp.choices[0].message.content)

def fallback_summary(topic: Dict[str, Any]) -> Dict[str, Any]:
    name = topic["name"].lower()
    hard_kw = ["markov", "eigen", "reinforcement", "bayesian", "optimization", "backpropagation"]
    diff = 3
    if any(k in name for k in hard_kw):
        diff = 4
    return {
        "difficulty_level": diff,
        "target_audience": "Undergraduate",
        "estimated_learning_time": "1-2 hours",
        "prerequisites_summary": "Basic probability, linear algebra, and introductory ML are recommended.",
        "key_sub_concepts": [s.get("name","") for s in topic.get("sub_topics", [])[:3] if s.get("name")],
        "common_misconceptions": ["Memorizing definitions without understanding assumptions."],
        "practical_applications": ["Course assignments", "Model analysis tasks"]
    }

def main():
    print("=== Stage 3: Node Summary (LLM + Fallback) ===")
    in_path = ask_input_path()
    out_path = ask_output_path()

    topics = load_topics(in_path)
    print(f"[1] 读取Topic数量: {len(topics)}")

    method = "llm"
    try:
        client = get_client()
        for i, t in enumerate(topics, 1):
            print(f"[LLM] {i}/{len(topics)} {t['name']}")
            try:
                t["summary"] = llm_summary(client, t)
            except Exception as e:
                print(f"[Warn] 单节点LLM失败，回退: {t['name']} | {e}")
                t["summary"] = fallback_summary(t)
                method = "hybrid_partial_fallback"
    except Exception as e:
        print(f"[Warn] LLM不可用，全部回退: {e}")
        method = "rules_fallback"
        for t in topics:
            t["summary"] = fallback_summary(t)

    output = {
        "stage": "3",
        "method": method,
        "topics_count": len(topics),
        "topics": topics
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[Saved] {out_path}")
    print(" Stage 3 完成")

if __name__ == "__main__":
    main()

#python "d:/ic/master project/project_code/KG_construction/stage3_node_summary_hybrid.py"
