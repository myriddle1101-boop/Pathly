#!/usr/bin/env python
"""Convert all Markdown files in rag-tutorial directory to PDF."""

import os
import glob
import markdown
from xhtml2pdf import pisa

BASE_DIR = r"D:\ic\master project\project_code\KG_construction\resource\rag-tutorial"

CSS_STYLE = """
<style>
body {
    font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
    max-width: 700px;
    margin: 0 auto;
    padding: 20px;
}
h1 {
    color: #1a1a2e;
    font-size: 22pt;
    border-bottom: 2px solid #16213e;
    padding-bottom: 8px;
    margin-top: 30px;
}
h2 {
    color: #16213e;
    font-size: 16pt;
    margin-top: 25px;
    border-bottom: 1px solid #ccc;
    padding-bottom: 5px;
}
h3 {
    color: #0f3460;
    font-size: 13pt;
    margin-top: 20px;
}
h4 {
    color: #533483;
    font-size: 11pt;
    margin-top: 15px;
}
p {
    margin: 8px 0;
}
code {
    font-family: "Consolas", "Courier New", monospace;
    background-color: #f4f4f4;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 10pt;
    color: #c7254e;
}
pre {
    background-color: #f8f8f8;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 12px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.4;
}
pre code {
    background-color: transparent;
    padding: 0;
    color: #333;
}
blockquote {
    border-left: 4px solid #4a90d9;
    margin: 10px 0;
    padding: 8px 15px;
    background-color: #f0f7ff;
    color: #555;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 10pt;
}
th, td {
    border: 1px solid #ddd;
    padding: 6px 10px;
    text-align: left;
}
th {
    background-color: #16213e;
    color: white;
    font-weight: bold;
}
tr:nth-child(even) {
    background-color: #f9f9f9;
}
ul, ol {
    margin: 8px 0;
    padding-left: 25px;
}
li {
    margin: 4px 0;
}
a {
    color: #4a90d9;
    text-decoration: none;
}
hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 20px 0;
}
img {
    max-width: 100%;
    height: auto;
}
</style>
"""

def convert_md_to_pdf(md_path, pdf_path):
    """Convert a single Markdown file to PDF."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert markdown to HTML with extensions
    html_body = markdown.markdown(
        md_content,
        extensions=["extra", "codehilite", "tables", "fenced_code", "toc"]
    )

    # Build full HTML document
    filename = os.path.basename(md_path)
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{filename}</title>
{CSS_STYLE}
</head>
<body>
{html_body}
</body>
</html>
"""

    # Convert HTML to PDF
    with open(pdf_path, "wb") as out_file:
        result = pisa.CreatePDF(html, dest=out_file)

    return result.err == 0


def main():
    # Find all MD files
    md_files = []
    for root, dirs, files in os.walk(BASE_DIR):
        for f in files:
            if f.endswith(".md") and f != "convert_md_to_pdf.py":
                md_files.append(os.path.join(root, f))

    md_files.sort()
    print(f"Found {len(md_files)} Markdown files to convert.\n")

    success = 0
    failed = 0

    for md_path in md_files:
        pdf_path = md_path.replace(".md", ".pdf")
        filename = os.path.basename(md_path)
        rel_dir = os.path.relpath(os.path.dirname(md_path), BASE_DIR)

        try:
            ok = convert_md_to_pdf(md_path, pdf_path)
            if ok:
                size_kb = os.path.getsize(pdf_path) / 1024
                print(f"OK: [{rel_dir}] {filename} -> {os.path.basename(pdf_path)} ({size_kb:.1f}KB)")
                success += 1
            else:
                print(f"FAIL: [{rel_dir}] {filename} - conversion error")
                failed += 1
        except Exception as e:
            print(f"FAIL: [{rel_dir}] {filename} - {e}")
            failed += 1

    print(f"\n=== Conversion Complete ===")
    print(f"Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
