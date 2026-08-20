import os
import re
import json
import pdfplumber
from collections import Counter
try:
    from nltk.tokenize import TextTilingTokenizer
except ImportError:  # Pathly keeps paragraph chunking available in its minimal runtime.
    TextTilingTokenizer = None

# ========= 全局参数 =========
MIN_WORDS_PER_CHUNK = 40
MAX_WORDS_SLIDES = 280
MAX_WORDS_PAPER = 800
MAX_WORDS_NOTES = 450

def safe_print_text(s: str):
    """
    Windows GBK 终端安全打印，避免 UnicodeEncodeError
    """
    try:
        print(s)
    except UnicodeEncodeError:
        s2 = s.encode("gbk", errors="ignore").decode("gbk", errors="ignore")
        print(s2)

def ask_pdf_path() -> str:
    p = input("请输入PDF完整路径：\n> ").strip().strip('"').strip("'")
    return p


def ask_output_path(default_name="stage1_chunks.json") -> str:
    p = input(f"请输入输出JSON路径（回车=当前目录/{default_name}）：\n> ").strip().strip('"').strip("'")
    if not p:
        p = os.path.join(os.getcwd(), default_name)
    return p


def extract_pages_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text with page provenance for later KG evidence review."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"找不到PDF: {pdf_path}")

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            t = page.extract_text()
            if t and t.strip():
                pages.append({"page_number": page_number, "text": t.strip()})

    if not pages:
        raise ValueError("PDF提取不到文本（可能是扫描版）")

    return pages


def extract_text_from_pdf(pdf_path: str) -> str:
    """Backward-compatible plain-text extraction."""
    return "\n\n".join(page["text"] for page in extract_pages_from_pdf(pdf_path))


def _content_terms(text: str) -> set[str]:
    """Lightweight lexical evidence used only to attach candidate pages."""
    stop_words = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "into", "of", "to", "in", "a", "an"}
    return {term for term in re.findall(r"[a-z0-9]+", text.lower()) if len(term) > 2 and term not in stop_words}


def attach_page_provenance(chunks: list[str], pages: list[dict]) -> list[list[int]]:
    """Associate each semantic chunk with its strongest-overlap PDF pages.

    This is provenance metadata, not a claim that a page alone proves an
    extracted concept or prerequisite relation.
    """
    page_terms = [(int(page["page_number"]), _content_terms(clean_raw_text(page["text"]))) for page in pages]
    page_lists = []
    for chunk in chunks:
        terms = _content_terms(chunk)
        scores = [(number, len(terms & source_terms)) for number, source_terms in page_terms]
        best = max((score for _, score in scores), default=0)
        page_lists.append([number for number, score in scores if best and score >= max(2, best * 0.55)])
    return page_lists


def clean_raw_text(text: str) -> str:
    # 空白归一化
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 粘连修复：aB / a1 / 1a
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)

    return text.strip()


def estimate_doc_type(text: str) -> str:
    """
    粗粒度文档类型识别：
    - slides: 短行多、标题词多、重复头尾词多
    - paper_book: 长段多、句子更完整
    - lecture_notes: 介于两者，常含definition/example等教学词
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "paper_book"

    avg_line_len = sum(len(x.split()) for x in lines) / len(lines)
    short_line_ratio = sum(1 for x in lines if len(x.split()) <= 8) / len(lines)

    lower_text = text.lower()
    slide_markers = ["table of", "overview", "contents", "week", "lecture", "imperial", "slide"]
    notes_markers = ["definition", "example", "exercise", "theorem", "proof"]

    slide_score = sum(1 for m in slide_markers if m in lower_text) + (2 if short_line_ratio > 0.45 else 0)
    notes_score = sum(1 for m in notes_markers if m in lower_text)

    if slide_score >= 3:
        return "slides"
    if notes_score >= 2:
        return "lecture_notes"
    return "paper_book"


def split_sentences(text: str):
    text = text.replace("\n", " ")
    sents = re.split(r'(?<=[。！？.!?])\s+', text)
    return [s.strip() for s in sents if s.strip()]


def pack_by_word_limit(units, max_words):
    chunks = []
    cur, cur_len = [], 0
    for u in units:
        wl = len(u.split())
        if wl == 0:
            continue
        if cur and (cur_len + wl > max_words):
            chunks.append(" ".join(cur).strip())
            cur, cur_len = [u], wl
        else:
            cur.append(u)
            cur_len += wl
    if cur:
        chunks.append(" ".join(cur).strip())
    return chunks


def chunk_slides(text: str):
    """
    Slides策略：
    段落优先 + 词数窗口，避免TextTiling在幻灯片上失效
    """
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = pack_by_word_limit(paras, MAX_WORDS_SLIDES)

    # 超长块再句切
    final = []
    for c in chunks:
        if len(c.split()) <= MAX_WORDS_SLIDES:
            final.append(c)
        else:
            final.extend(pack_by_word_limit(split_sentences(c), MAX_WORDS_SLIDES))
    return final


def chunk_paper_book(text: str):
    """
    书/论文策略：
    TextTiling + 超长句切
    """
    try:
        if TextTilingTokenizer is None:
            raise RuntimeError("NLTK TextTiling is unavailable")
        tiles = TextTilingTokenizer(w=20, k=10).tokenize(text)
    except Exception:
        tiles = [p.strip() for p in text.split("\n\n") if p.strip()]

    final = []
    for t in tiles:
        if len(t.split()) <= MAX_WORDS_PAPER:
            final.append(t.strip())
        else:
            final.extend(pack_by_word_limit(split_sentences(t), MAX_WORDS_PAPER))
    return final


def chunk_lecture_notes(text: str):
    """
    讲义策略：
    段落 + 句子混合，粒度中等
    """
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = pack_by_word_limit(paras, MAX_WORDS_NOTES)

    final = []
    for c in chunks:
        if len(c.split()) <= MAX_WORDS_NOTES:
            final.append(c)
        else:
            final.extend(pack_by_word_limit(split_sentences(c), MAX_WORDS_NOTES))
    return final


def is_noisy_chunk(chunk: str):
    words = chunk.split()
    if len(words) < MIN_WORDS_PER_CHUNK:
        return True
    chars = "".join(words)
    alpha_ratio = sum(ch.isalpha() for ch in chars) / max(len(chars), 1)
    if alpha_ratio < 0.6:
        return True
    return False


def main():
    print("=== Stage1 自适应分块 ===")
    pdf_path = ask_pdf_path()
    out_path = ask_output_path()

    # 1) 提取文本
    pages = extract_pages_from_pdf(pdf_path)
    raw_text = "\n\n".join(page["text"] for page in pages)
    print(f"[1] 原始词数: {len(raw_text.split())}")

    # 2) 清洗
    text = clean_raw_text(raw_text)
    print(f"[2] 清洗后词数: {len(text.split())}")

    # 3) 类型识别
    doc_type = estimate_doc_type(text)
    print(f"[3] 文档类型识别: {doc_type}")

    # 4) 分块
    if doc_type == "slides":
        chunks = chunk_slides(text)
    elif doc_type == "lecture_notes":
        chunks = chunk_lecture_notes(text)
    else:
        chunks = chunk_paper_book(text)

    before_filter = len(chunks)
    chunks = [c for c in chunks if not is_noisy_chunk(c)]
    after_filter = len(chunks)

    print(f"[4] 分块数（过滤前）: {before_filter}")
    print(f"[5] 分块数（过滤后）: {after_filter}")

    # 5) 输出
    out = []
    page_lists = attach_page_provenance(chunks, pages)
    for i, (c, page_numbers) in enumerate(zip(chunks, page_lists), 1):
        row = {
            "chunk_id": i,
            "word_count": len(c.split()),
            "doc_type": doc_type,
            "text": c,
            "page_numbers": page_numbers,
        }
        if len(page_numbers) == 1:
            row["page_number"] = page_numbers[0]
        elif page_numbers:
            row["page_start"] = min(page_numbers)
            row["page_end"] = max(page_numbers)
        out.append(row)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 另存清洗文本
    text_out = os.path.join(os.path.dirname(out_path) if os.path.dirname(out_path) else os.getcwd(), "stage1_text_cleaned.txt")
    with open(text_out, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"[Saved] {out_path}")
    print(f"[Saved] {text_out}")

    # 预览
    n = min(3, len(chunks))
    print(f"\n--- 前{n}块预览 ---")
    for i in range(n):
        snippet = chunks[i][:220].replace("\n", " ")
        safe_print_text(f"\n[Chunk {i+1}] words={len(chunks[i].split())}")
        safe_print_text(snippet + ("..." if len(chunks[i]) > 220 else ""))
       

    print("\n Stage1 完成，可进入 Stage2")


if __name__ == "__main__":
    main()
