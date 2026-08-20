import os
import re
import json
import time
import numpy as np
import pdfplumber
import networkx as nx
import matplotlib.pyplot as plt

from openai import OpenAI
from nltk.tokenize import TextTilingTokenizer
from sentence_transformers import SentenceTransformer
import nltk

from env_loader import load_project_env

load_project_env()


# ========= 配置区 =========
PDF_PATH = "ml_slides.pdf"          # 你的PDF文件名
MODEL_NAME = "gpt-4o-mini"          # 先用mini省钱
MAX_WORDS_PER_CHUNK = 800           # 块长度上限（近似token）
MIN_WORDS_PER_CHUNK = 50            # 太短块过滤
TOPIC_CHUNK_LIMIT = None            # 调试时可设为3（只跑前3块）
SIM_THRESHOLD = 0.75                # 相似关系阈值
SLEEP_BETWEEN_CALLS = 0.3           # API调用间隔，减少限流风险


# ========= 初始化 =========
nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sbert = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def extract_text_from_pdf(pdf_path: str) -> str:
    """从PDF逐页提取文本"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"找不到PDF文件: {pdf_path}")

    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            if t and t.strip():
                texts.append(t.strip())
    return "\n\n".join(texts)


def safe_sentence_split(text: str):
    """简单句子切分（中英文兼容基础版）"""
    text = text.replace("\n", " ")
    sents = re.split(r'(?<=[。！？.!?])\s+', text)
    return [s.strip() for s in sents if s.strip()]


def chunk_document(text: str, max_words: int = 800, min_words: int = 50):
    """
    Stage 1:
    先TextTiling语义分块，再对超长块做句级二次切分
    """
    tiler = TextTilingTokenizer(w=20, k=10)
    try:
        tiles = tiler.tokenize(text)
    except Exception as e:
        print(f"[Warn] TextTiling失败，回退到段落分块: {e}")
        tiles = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    for tile in tiles:
        words = tile.split()
        if len(words) <= max_words:
            chunks.append(tile.strip())
        else:
            # 超长块：句子级切分
            sents = safe_sentence_split(tile)
            cur, cur_len = [], 0
            for s in sents:
                wl = len(s.split())
                if cur and cur_len + wl > max_words:
                    chunks.append(" ".join(cur).strip())
                    cur, cur_len = [s], wl
                else:
                    cur.append(s)
                    cur_len += wl
            if cur:
                chunks.append(" ".join(cur).strip())

    # 过滤太短块
    chunks = [c for c in chunks if len(c.split()) >= min_words]
    return chunks


def call_json_llm(prompt: str, model: str = MODEL_NAME):
    """统一的JSON调用"""
    time.sleep(SLEEP_BETWEEN_CALLS)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    content = resp.choices[0].message.content
    return json.loads(content)


def extract_topics_from_chunk(chunk: str):
    """
    Stage 2a: 从单个chunk提取 Topic + Sub-Topic
    """
    prompt = f"""
你是机器学习课程知识图谱助手。请从材料中提取知识结构。

材料：
{chunk[:4000]}

规则：
1) Topic 是相对抽象的知识点（例如：梯度下降）
2) Sub-Topic 是更具体子概念（例如：学习率选择）
3) 如果材料没有明确知识点，返回空列表
4) 严格输出JSON，不要额外文本

输出格式：
{{
  "topics": [
    {{
      "name": "topic名称",
      "description": "一句话描述",
      "sub_topics": [
        {{"name": "sub1", "description": "一句话描述"}}
      ]
    }}
  ]
}}
"""
    try:
        result = call_json_llm(prompt)
        topics = result.get("topics", [])
        if not isinstance(topics, list):
            return {"topics": []}
        return {"topics": topics}
    except Exception as e:
        print(f"[Warn] extract_topics失败: {e}")
        return {"topics": []}


def deduplicate_topics(topics):
    """按topic name去重（保留首个）"""
    seen = set()
    unique = []
    for t in topics:
        name = t.get("name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        # 补齐字段
        t.setdefault("description", "")
        t.setdefault("sub_topics", [])
        unique.append(t)
    return unique


def extract_prerequisites(topics):
    """
    Stage 2b: 推断先修关系
    """
    if len(topics) < 2:
        return {"prerequisites": []}

    topic_lines = "\n".join([f"- {t['name']}: {t.get('description','')}" for t in topics])

    prompt = f"""
下面是机器学习课程知识点列表：
{topic_lines}

任务：找出"强先修关系"。
定义：学习B之前必须先掌握A（A -> B）。
只输出强依赖，不要弱相关。

输出JSON：
{{
  "prerequisites": [
    {{
      "from": "A",
      "to": "B",
      "reason": "简短原因"
    }}
  ]
}}
"""
    try:
        result = call_json_llm(prompt)
        rels = result.get("prerequisites", [])
        if not isinstance(rels, list):
            rels = []
        return {"prerequisites": rels}
    except Exception as e:
        print(f"[Warn] extract_prerequisites失败: {e}")
        return {"prerequisites": []}


def compute_similarity_edges(topics, threshold=0.75):
    """
    Stage 2c: SBERT计算topic相似关系
    """
    if len(topics) < 2:
        return []

    names = [t["name"] for t in topics]
    texts = [f"{t['name']}: {t.get('description','')}" for t in topics]
    embs = sbert.encode(texts, normalize_embeddings=True)

    edges = []
    n = len(names)
    for i in range(n):
        for j in range(i + 1, n):
            sim = float(np.dot(embs[i], embs[j]))  # 已归一化，点积=余弦相似度
            if sim >= threshold:
                edges.append({
                    "from": names[i],
                    "to": names[j],
                    "similarity": sim
                })
    return edges


def generate_node_summary(topic):
    """
    Stage 3: 节点结构化摘要
    """
    prompt = f"""
请为以下机器学习知识点生成结构化学习摘要。

知识点：{topic['name']}
描述：{topic.get('description','')}

输出JSON：
{{
  "difficulty_level": 1,
  "target_audience": "本科生",
  "estimated_learning_time": "2小时",
  "prerequisites_summary": "需要先掌握...",
  "key_sub_concepts": ["概念1", "概念2"],
  "common_misconceptions": ["误解1", "误解2"],
  "practical_applications": ["应用1", "应用2"]
}}

要求：
- difficulty_level范围1-5
- 内容简洁、可执行
"""
    try:
        result = call_json_llm(prompt)
        return result
    except Exception as e:
        print(f"[Warn] generate_node_summary失败({topic['name']}): {e}")
        return {}


def build_graph(topics, prerequisites, similarity_edges):
    """
    构建NetworkX有向图
    """
    G = nx.DiGraph()

    # 节点
    for t in topics:
        G.add_node(
            t["name"],
            description=t.get("description", ""),
            sub_topics=t.get("sub_topics", []),
            summary=t.get("summary", {})
        )

    # 先修边
    for r in prerequisites:
        a, b = r.get("from"), r.get("to")
        if a in G.nodes and b in G.nodes and a != b:
            G.add_edge(a, b, relation="prerequisite", reason=r.get("reason", ""))

    # 相似边
    for e in similarity_edges:
        a, b = e["from"], e["to"]
        if a in G.nodes and b in G.nodes and a != b:
            if G.has_edge(a, b):
                G[a][b]["similarity"] = e["similarity"]
            else:
                G.add_edge(a, b, relation="similarity", similarity=e["similarity"])

    return G


def visualize_graph(G):
    """
    简单可视化（可选，用matplotlib）
    """
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, k=0.5, seed=42)

    # 节点
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color="lightblue")
    nx.draw_networkx_labels(G, pos, font_size=8)

    # 边：先修关系用实线，相似关系用虚线
    prereq_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "prerequisite"]
    sim_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "similarity"]

    nx.draw_networkx_edges(G, pos, edgelist=prereq_edges, edge_color="blue", arrows=True, width=2)
    nx.draw_networkx_edges(G, pos, edgelist=sim_edges, edge_color="gray", style="dashed")

    plt.title("知识图谱（先修关系+相似关系）")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig("knowledge_graph_vis.png", dpi=150, bbox_inches="tight")
    print("✅ 可视化图已保存到 knowledge_graph_vis.png")


def build_knowledge_graph(pdf_path):
    """主Pipeline"""
    print("=" * 60)
    print("知识图谱构建 Pipeline 启动")
    print("=" * 60)

    # Stage 1
    print("\n📄 Stage 1: 文档分块...")
    text = extract_text_from_pdf(pdf_path)
    chunks = chunk_document(text, MAX_WORDS_PER_CHUNK, MIN_WORDS_PER_CHUNK)
    print(f"✅ 生成 {len(chunks)} 个语义块")

    # Stage 2a
    print("\n🔍 Stage 2a: 提取知识点...")
    all_topics = []
    chunks_to_process = chunks[:TOPIC_CHUNK_LIMIT] if TOPIC_CHUNK_LIMIT else chunks
    for i, chunk in enumerate(chunks_to_process):
        print(f"  处理块 {i+1}/{len(chunks_to_process)}...", end="\r")
        result = extract_topics_from_chunk(chunk)
        all_topics.extend(result.get("topics", []))
    
    unique_topics = deduplicate_topics(all_topics)
    print(f"\n✅ 提取到 {len(unique_topics)} 个知识点")

    # Stage 2b
    print("\n🔗 Stage 2b: 提取先修关系...")
    prereq_result = extract_prerequisites(unique_topics)
    prerequisites = prereq_result.get("prerequisites", [])
    print(f"✅ 发现 {len(prerequisites)} 条先修关系")

    # Stage 2c
    print("\n🔄 Stage 2c: 计算相似关系...")
    similarity_edges = compute_similarity_edges(unique_topics, SIM_THRESHOLD)
    print(f"✅ 发现 {len(similarity_edges)} 条相似关系")

    # Stage 3
    print("\n📝 Stage 3: 生成节点摘要...")
    for i, topic in enumerate(unique_topics):
        print(f"  处理节点 {i+1}/{len(unique_topics)}...", end="\r")
        topic["summary"] = generate_node_summary(topic)
    print(f"\n✅ 节点摘要生成完毕")

    # 构建图
    print("\n🏗️ 构建知识图谱...")
    G = build_graph(unique_topics, prerequisites, similarity_edges)

    print(f"\n{'='*60}")
    print(f"🎉 知识图谱构建完成！")
    print(f"   节点数：{G.number_of_nodes()}")
    print(f"   边数：  {G.number_of_edges()}")
    print(f"{'='*60}")

    # 保存结果
    nx.write_gexf(G, "knowledge_graph.gexf")
    with open("topics.json", "w", encoding="utf-8") as f:
        json.dump(unique_topics, f, ensure_ascii=False, indent=2)

    print("\n📁 已保存：")
    print("   knowledge_graph.gexf（可用Gephi可视化）")
    print("   topics.json（知识点详情）")

    # 尝试可视化
    try:
        visualize_graph(G)
    except Exception as e:
        print(f"[Warn] 可视化跳过: {e}")

    return G, unique_topics


if __name__ == "__main__":
    # 运行！
    try:
        G, topics = build_knowledge_graph(PDF_PATH)
        
        # 打印前5个知识点预览
        print("\n📋 知识点预览（前5个）：")
        for topic in topics[:5]:
            print(f"\n  [{topic['name']}]")
            print(f"  描述：{topic['description'][:50]}...")
            if topic.get('summary'):
                print(f"  难度：{topic['summary'].get('difficulty_level', '?')}/5")
                print(f"  学习时间：{topic['summary'].get('estimated_learning_time', '?')}")
    except Exception as e:
        print(f"\n❌ 运行失败：{e}")
