import os
import re
import json
import pdfplumber
from nltk.tokenize import TextTilingTokenizer

# ========= 可调参数 =========
MAX_WORDS_PER_CHUNK = 800
MIN_WORDS_PER_CHUNK = 60


def ask_pdf_path() -> str:
    """
    交互式获取PDF路径
    - 允许带引号粘贴
    - 自动去掉首尾空格和引号
    """
    p = input("请输入PDF文件完整路径（例如 D:\\data\\ml_slides.pdf）：\n> ").strip()
    p = p.strip('"').strip("'")  # 去引号
    return p


def extract_text_from_pdf(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"找不到PDF文件: {pdf_path}")

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())

    if not pages_text:
        raise ValueError("PDF提取不到文本（可能是扫描版PDF）")

    return "\n\n".join(pages_text)

NOISE_PATTERNS = [
    r"Imperial College London",
    r"Machine Learning for Design Engineers",
    r"Week\s*\d+",
    r"Table of Content[s]?"
]

def clean_raw_text(text: str) -> str:
    """
    轻量文本清洗：
    - 去页眉页脚噪声行
    - 修复小写->大写粘连
    - 字母数字边界加空格
    - 空白归一化
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned_lines = []

    for ln in lines:
        if any(re.search(p, ln, flags=re.IGNORECASE) for p in NOISE_PATTERNS):
            continue
        cleaned_lines.append(ln)

    text = "\n".join(cleaned_lines)

    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def is_noisy_chunk(chunk: str) -> bool:
    """
    分块后噪声过滤：
    - 太短
    - 字母比例过低（常见符号/图注块）
    """
    words = chunk.split()
    if len(words) < 60:
        return True

    chars = "".join(words)
    alpha_ratio = sum(ch.isalpha() for ch in chars) / max(len(chars), 1)
    if alpha_ratio < 0.6:
        return True

    return False

def split_sentences(text: str):
    text = text.replace("\n", " ")
    sents = re.split(r'(?<=[。！？.!?])\s+', text)
    return [s.strip() for s in sents if s.strip()]


def chunk_with_texttiling(text: str, max_words=800, min_words=40):
    tokenizer = TextTilingTokenizer(w=20, k=10)

    try:
        tiles = tokenizer.tokenize(text)
    except Exception as e:
        print(f"[Warn] TextTiling失败，回退到段落分块: {e}")
        tiles = [p.strip() for p in text.split("\n\n") if p.strip()]

    final_chunks = []
    for tile in tiles:
        words = tile.split()

        if len(words) <= max_words:
            final_chunks.append(tile.strip())
        else:
            sents = split_sentences(tile)
            current, cur_len = [], 0

            for s in sents:
                wl = len(s.split())
                if current and (cur_len + wl > max_words):
                    final_chunks.append(" ".join(current).strip())
                    current, cur_len = [s], wl
                else:
                    current.append(s)
                    cur_len += wl

            if current:
                final_chunks.append(" ".join(current).strip())

    final_chunks = [c for c in final_chunks if len(c.split()) >= min_words]
    return final_chunks


def main():
    print("=== Stage 1: 文件选择版（PDF提取 + 语义分块）===")

    pdf_path = ask_pdf_path()
    print(f"\n你选择的文件：{pdf_path}")

    # 输出目录：默认放在脚本当前目录下
    out_dir = os.getcwd()
    print(f"输出目录：{out_dir}")

    # 1) 提取文本
    text = extract_text_from_pdf(pdf_path)
    print(f"[1] 原始文本词数估算: {len(text.split())}")
    
    text = clean_raw_text(text)
    total_words = len(text.split())
    print(f"[1.1] 清洗后文本词数估算: {total_words}")

    text_out = os.path.join(out_dir, "stage1_text.txt")
    with open(text_out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[Saved] {text_out}")

    # 2) 分块
    chunks = chunk_with_texttiling(
        text,
        max_words=MAX_WORDS_PER_CHUNK,
        min_words=MIN_WORDS_PER_CHUNK
    )
    print(f"[2] 分块完成，语义块数量: {len(chunks)}")

    chunks = [c for c in chunks if not is_noisy_chunk(c)]
    print(f"[2.1] 分块完成（过滤后）: {len(chunks)}")

    chunk_data = []
    for i, c in enumerate(chunks, 1):
        chunk_data.append({
            "chunk_id": i,
            "word_count": len(c.split()),
            "text": c
        })

    chunks_out = os.path.join(out_dir, "stage1_chunks.json")
    with open(chunks_out, "w", encoding="utf-8") as f:
        json.dump(chunk_data, f, ensure_ascii=False, indent=2)
    print(f"[Saved] {chunks_out}")

    # 预览
    n = min(3, len(chunks))
    print(f"\n--- 前{n}块预览 ---")
    for i in range(n):
        snippet = chunks[i][:250].replace("\n", " ")
        print(f"\n[Chunk {i+1}] words={len(chunks[i].split())}")
        print(snippet + ("..." if len(chunks[i]) > 250 else ""))

    print("\n✅ Stage 1 完成")


if __name__ == "__main__":
    main()