# 知识图谱构建 Pipeline 使用指南

本项目用于从 PDF 教材/幻灯片中构建知识图谱，包含文档分块、知识点提取、关系推断和节点摘要生成。

## 📋 环境准备

### 1. 激活虚拟环境
你已经有了 `.venv` 虚拟环境，直接激活即可：

**Windows PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

### 2. 安装依赖
如果还没安装依赖，运行：
```bash
pip install -r requirements.txt
```

### 3. 下载 NLTK 数据
```bash
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"
```

### 4. 设置 OpenAI API Key
**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY = "你的API密钥"
```

（注意：这个设置只在当前终端窗口有效，关闭后需要重新设置。如果你想永久设置，可以使用 `setx` 命令，但需要重启终端。）

---

## 🚀 开始使用

### 步骤 1：测试 OpenAI API
首先验证 API 是否可用：
```bash
python test_openai.py
```

如果看到 `✅ API 测试成功！响应：API OK`，说明 API 正常工作。

### 步骤 2：准备 PDF 文件
将你的机器学习 slides 或教材 PDF 放到这个文件夹，命名为 `ml_slides.pdf`（或者修改 `kg_pipeline.py` 中的 `PDF_PATH`）。

### 步骤 3：运行知识图谱构建
```bash
python kg_pipeline.py
```

---

## 📊 预期输出

运行成功后，会生成以下文件：
- `knowledge_graph.gexf` - 可用 Gephi 软件打开查看和可视化
- `topics.json` - 所有知识点的详细信息（包括摘要）
- `knowledge_graph_vis.png` - 简单的 matplotlib 可视化图

---

## 💡 调试技巧

如果想先快速测试，可以修改 `kg_pipeline.py` 顶部的配置：

```python
TOPIC_CHUNK_LIMIT = 3  # 只处理前3个块，快速看效果
```

---

## 📚 依赖说明

- `openai`: OpenAI API 调用
- `pdfplumber`: PDF 文本提取
- `nltk`: 自然语言处理（TextTiling 分块）
- `sentence-transformers`: 句子嵌入（计算相似关系）
- `networkx`: 图数据结构
- `numpy`: 数值计算
- `matplotlib`: 可视化
