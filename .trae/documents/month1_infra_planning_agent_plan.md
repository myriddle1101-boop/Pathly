# Month 1 基础设施与 Planning Agent 实施计划

## Summary

本计划只细化 `Month 1`，目标是在当前已跑通的 `KG_construction` 基础上，补齐三块基础设施 `KG / RAG / 用户画像`，并完成第一版 `Planning Agent` 后端模块，使系统能够：

1. 复用现有 KG 产物生成稳定的结构化图数据。
2. 新增基于 `ChromaDB` 的本地向量库，为后续 `Content Agent` 预留检索接口。
3. 新增基于 `SQLite` 的双维细粒度用户画像存储。
4. 新增 `Planning Agent`，支持自然语言目标解析、KG 节点映射、先修路径搜索、时间分配，并输出 `day-by-day` JSON 课程表。
5. 新增小样本 KG 评测流程，用人工标注方式评估 `topic / prerequisite / similarity` 的效果。

本次计划不实现 `Content Agent`、`Adaptation Agent`、小测系统和完整前端交互，只为它们把基础设施和接口准备好。

## Current State Analysis

### 已完成部分

- `KG_construction/stage1_adaptive_chunking.py`
  - 已实现自适应分块，能区分 `slides / lecture_notes / paper_book`。
  - 已包含清洗、噪声块过滤、分块结果导出。
- `KG_construction/stage2a_hybrid_keybert_llm.py`
  - 已实现 `KeyBERT + SentenceTransformer + OpenAI` 的 Topic 提取。
  - 已具备本地嵌入模型能力，当前代码里已存在 `cuda` 检测逻辑。
- `KG_construction/stage2b_prerequisites_hybrid.py`
  - 已实现 LLM 优先、规则回退的先修边抽取。
- `KG_construction/stage2c_similarity.py`
  - 已实现 SBERT 相似边生成。
- `KG_construction/stage3_node_summary_hybrid.py`
  - 已实现节点摘要生成及 fallback。
- `KG_construction/stage4_build_and_visualize_kg.py`
  - 已实现 `knowledge_graph.json / .gexf / .png` 导出。
- `KG_construction/app.py`
  - 已实现 Streamlit 上传与多文档流水线调度。
  - 已支持按 PDF 批量运行 Stage1-4，并合并全局图谱。
- `KG_construction/web_data/global/upload_history.json`
  - 已确认至少 6 份 PDF 已成功跑通完整 KG pipeline。
- `KG_construction/web_data/global/global_knowledge_graph.json`
  - 已确认当前全局图谱已累计到 76 个节点、68 条边以上。

### 当前缺失部分

- 仓库中没有 `RAG` 代码实现。
- 仓库中没有 `ChromaDB`、向量索引、chunk embedding 持久化代码。
- 仓库中没有 `用户画像` schema、存储层、读写接口。
- 仓库中没有 `Planning Agent` 代码，包括：
  - 自然语言目标解析
  - 目标节点映射
  - 先修路径搜索
  - 时间分配
  - day-by-day JSON 输出
- 仓库中没有 `KG` 效果评测脚本和人工标注模板。
- 仓库中没有 `PRD.md` 和 `CHANGELOG.md`。

### 现有实现的关键约束

- 当前 Stage 脚本以“命令行问答输入路径”的方式组织，适合 pipeline 串联，但不适合后续 agent 复用。
- 当前 `app.py` 直接调用 Stage 脚本，说明现在的业务逻辑是“脚本驱动”，不是“模块/服务驱动”。
- 当前 Stage2a 已经具备 GPU 入口，但 Stage2c 和整体设备管理仍未统一。
- 当前全局图谱是 JSON 合并结果，但没有统一的“图查询抽象层”，后续 Planning Agent 若直接读散落 JSON，维护成本会高。

## Assumptions & Decisions

### 已确认决策

- 计划范围：只细化 `Month 1`，`Month 2-3` 只保留路线图。
- 向量数据库：使用本地 `ChromaDB`。
- Planning Agent 落地形式：先做后端模块，再决定何时接入 `app.py`。
- 用户画像存储：使用 `SQLite`。
- 用户画像复杂度：第一版直接做“认知-情感双维细粒度画像”。
- KG 评测方式：优先做人工作业量可控的小样本人工标注评测。
- Planning Agent 输出粒度：按天 `day-by-day` 输出。

### 本计划替你做出的技术决策

- GPU 迁移策略：采用“`先做可切换架构，再优先加速最慢模块`”。
  - 原因：你目前并未明确 GPU 型号与显存条件，直接规划“全链路 GPU 化”风险过高。
  - 第一优先级：统一 `SentenceTransformer / KeyBERT / similarity` 的设备管理、批处理和缓存。
  - 第二优先级：对 Stage2a 和 Stage2c 做基准测试后，再决定是否替换模型或增加批量嵌入流程。
- 图数据访问方式：第一版仍基于 `knowledge_graph.json` + Python 图查询层，不迁移到 Neo4j。
  - 原因：Month 1 的目标是 Planning Agent，可用 `NetworkX + 统一加载器` 足够支持 BFS/A*。
- Planning Agent 第一版输出：只输出结构化 JSON，不强制在本月接 UI。
- 起点知识状态表示：第一版不做复杂知识追踪，用“用户已有知识节点 + 目标节点集合 + 画像权重”建模。

## Proposed Changes

### 1. 重构基础设施目录，建立可复用模块层

#### 新增目录

- `KG_construction/infra/`
- `KG_construction/agents/`
- `KG_construction/evaluation/`
- `KG_construction/data/`

#### 新增文件

- `KG_construction/infra/kg_repository.py`
  - 作用：统一加载 `knowledge_graph.json`、构建 `NetworkX` 图、提供节点查找、邻居查询、先修链查询、相似节点查询接口。
  - 为什么：当前 `app.py` 和 Stage4 只产出图，不提供查询抽象，Planning Agent 不应直接解析原始 JSON。
  - 怎么做：
    - 读取单文档图或全局图。
    - 提供 `load_graph(path)`、`get_topic(name)`、`search_topics(query)`、`get_prerequisites(node)`、`get_similar(node)`。
    - 对节点属性中的 JSON 字符串做反序列化兜底。

- `KG_construction/infra/device_manager.py`
  - 作用：统一管理 `cpu/cuda` 设备选择、模型加载配置、批大小、缓存目录。
  - 为什么：当前 Stage2a 自己判断 GPU，Stage2c 没有统一设备层，无法稳定做性能优化。
  - 怎么做：
    - 提供 `resolve_torch_device()`、`get_embedding_batch_size()`。
    - 暴露统一配置常量给 Stage2a / Stage2c / RAG embedding 使用。

- `KG_construction/infra/config.py`
  - 作用：集中管理路径、数据库位置、默认模型、阈值、输出目录。
  - 为什么：现在脚本里路径和参数散落，后续基础设施和 agent 模块会越来越多。
  - 怎么做：
    - 放置 `PROJECT_DIR`、`WEB_DATA_DIR`、`GLOBAL_KG_JSON`、`SQLITE_PATH`、`CHROMA_PATH` 等。

### 2. 为 KG 增加统一评测与性能优化入口

#### 调整现有文件

- `KG_construction/stage2a_hybrid_keybert_llm.py`
  - 改动目标：
    - 接入统一设备管理。
    - 为 GPU/CPU 运行记录耗时、模型设备、chunk 数量。
    - 支持批量嵌入与中间缓存，避免重复算 embedding。
  - 关键实现：
    - 将本地模型初始化抽到可复用函数。
    - 把按 chunk 提取的计时信息保存为 JSON benchmark 元数据。

- `KG_construction/stage2c_similarity.py`
  - 改动目标：
    - 接入统一设备管理。
    - 明确使用批量编码。
    - 输出计算耗时和阈值信息，方便调参。
  - 关键实现：
    - 将 `SentenceTransformer(MODEL_NAME)` 加载路径统一。
    - 增加 `benchmark` 字段。

#### 新增文件

- `KG_construction/evaluation/kg_benchmark.py`
  - 作用：跑 Stage1-4 的性能基准，输出 CPU/GPU 对比。
  - 为什么：你明确提出“KG 迁移到 GPU”和“CPU 太慢”，需要先有定量证据。
  - 怎么做：
    - 统计每个 stage 的耗时。
    - 输出每个 PDF 的 `topic_count / prereq_count / similarity_count / total_time`。
    - 在支持 GPU 时对比 `cpu vs cuda`。

- `KG_construction/evaluation/kg_quality_eval.py`
  - 作用：对单份或多份样本进行 KG 质量评测。
  - 为什么：Month 1 需要为毕设建立方法有效性证据。
  - 怎么做：
    - 读入人工标注文件。
    - 分别评估：
      - topic precision / coverage
      - prerequisite precision
      - similarity usefulness precision
    - 输出汇总 JSON 与可写进论文的表格草稿。

- `KG_construction/evaluation/annotations/`
  - 目录下预期包含：
    - `sample_topics_gold.json`
    - `sample_prerequisites_gold.json`
    - `sample_similarity_gold.json`
  - 作用：保存 1-2 份课程材料的小样本人工标注真值。

### 3. 建立 RAG 基础设施（ChromaDB）

#### 新增文件

- `KG_construction/infra/rag_ingestion.py`
  - 作用：把 Stage1 清洗文本和 chunk 写入 `ChromaDB`。
  - 为什么：当前只有 KG，没有独立可检索的 chunk 存储，Content Agent 无法开始。
  - 怎么做：
    - 输入 `stage1_chunks.json` 或 `web_data/runs/*/stage1_chunks.json`
    - 以文档名、chunk_id、doc_type、word_count 为 metadata。
    - 使用与 Stage2a/2c 一致的 embedding 模型，保证语义空间一致。

- `KG_construction/infra/rag_repository.py`
  - 作用：封装 Chroma 查询接口。
  - 为什么：后续 Content Agent 不能直接写 Chroma 原生调用。
  - 怎么做：
    - 提供 `upsert_chunks()`、`query_chunks(query, filters, top_k)`、`get_chunks_by_topic()`。
    - 支持按文档、难度、主题过滤。

- `KG_construction/infra/rag_schema.md` 不创建。
  - 说明：不额外建文档文件，schema 直接内嵌在代码注释和 dataclass 中，避免增加无必要文档文件。

### 4. 建立用户画像基础设施（SQLite，双维细粒度）

#### 新增文件

- `KG_construction/infra/profile_store.py`
  - 作用：管理 `SQLite` 中的用户画像读写。
  - 为什么：用户画像是 Planning Agent 的核心输入，目前完全不存在。
  - 怎么做：
    - 提供初始化建表逻辑。
    - 表建议：
      - `users`
      - `learner_profiles`
      - `learner_goal_history`
    - 支持按用户读取当前 profile、更新画像、记录版本。

- `KG_construction/infra/profile_schema.py`
  - 作用：定义 Python 层 schema/dataclass。
  - 第一版画像字段建议：
    - 基本信息：`user_id`, `name`, `academic_level`, `domain`
    - 目标相关：`goal_text`, `target_days`, `daily_minutes`
    - 认知维度：`prior_knowledge_level`, `math_foundation`, `programming_foundation`, `self_regulation`
    - 情感维度：`interest_tags`, `preferred_style`, `motivation_level`, `confidence_level`, `anxiety_level`
    - 规划辅助：`known_topics`, `preferred_examples`, `pace_preference`
  - 为什么：你要求第一版直接做双维细粒度画像，这些字段已经足以支撑 Planning Agent。

- `KG_construction/infra/profile_seed.py`
  - 作用：插入 demo 用户画像，方便 Month 1 做端到端测试。

### 5. 实现 Planning Agent 后端模块

#### 新增文件

- `KG_construction/agents/planning_agent.py`
  - 作用：Month 1 的主入口，封装完整课程规划流程。
  - 输入：
    - 用户自然语言学习目标
    - 用户画像对象
    - KG repository
  - 输出：
    - day-by-day JSON schedule
  - 内部子流程：
    1. goal parsing
    2. KG node mapping
    3. start-state estimation
    4. prerequisite path search
    5. time allocation
    6. curriculum JSON assembly

- `KG_construction/agents/goal_parser.py`
  - 作用：将自然语言目标解析成结构化 planning request。
  - 输出字段建议：
    - `goal_text`
    - `target_concepts`
    - `requested_days`
    - `daily_minutes`
    - `constraints`
    - `learning_style_hints`
  - 实现方式：
    - 优先 LLM 解析。
    - 若 LLM 不可用，回退到规则提取 `天数 / 时间 / 目标短语`。

- `KG_construction/agents/topic_mapper.py`
  - 作用：将 `goal_parser` 输出的目标概念映射到 KG 节点。
  - 实现方式：
    - 先 exact match / case-insensitive match
    - 再 embedding similarity match
    - 最后输出候选节点及置信度
  - 输出：
    - `matched_targets`
    - `unmatched_terms`
    - `mapping_explanations`

- `KG_construction/agents/path_planner.py`
  - 作用：实现 BFS/A* 路径搜索。
  - 具体决策：
    - 第一版同时支持：
      - `BFS`：作为基线最短先修路径
      - `A*`：作为带启发式的优化版本
    - 默认输出用 `A*`，基线评测保留 `BFS`
  - 启发式设计：
    - 使用目标节点距离、难度等级、估计学习时长做启发值。
  - 输出：
    - `ordered_topics`
    - `prerequisite_paths`
    - `covered_prerequisites`

- `KG_construction/agents/time_allocator.py`
  - 作用：把路径结果按用户画像和时间约束分配到每天。
  - 分配逻辑：
    - 以 `estimated_learning_time + difficulty_level + profile pace_preference` 作为权重。
    - 控制每日不超过 `daily_minutes`。
    - 若目标过大，输出 `overflow_topics` 和 `feasibility_warning`。

- `KG_construction/agents/planning_schema.py`
  - 作用：定义规划输出 schema。
  - 第一版 JSON 建议结构：
    - `plan_id`
    - `goal`
    - `profile_snapshot`
    - `planning_method`
    - `days`
    - `feasibility`
    - `target_topics`
    - `uncovered_constraints`
  - `days[i]` 内字段：
    - `day`
    - `focus_topics`
    - `prerequisite_bridge`
    - `estimated_minutes`
    - `difficulty_mix`
    - `reason`

- `KG_construction/agents/demo_generate_plan.py`
  - 作用：命令行/脚本方式跑 Planning Agent demo，用于 Week 3-4 验证和论文截图。

### 6. 为 Planning Agent 做测试与验收

#### 新增文件

- `KG_construction/tests/test_goal_parser.py`
- `KG_construction/tests/test_topic_mapper.py`
- `KG_construction/tests/test_path_planner.py`
- `KG_construction/tests/test_time_allocator.py`

#### 验收标准

- 目标句子如：
  - “我想在 7 天内学完机器学习里的神经网络基础，每天 90 分钟，我数学一般但有 Python 基础”
- 能稳定输出：
  - 目标主题映射结果
  - 先修主题链
  - 每日课程安排 JSON
  - 不可行时的 warning

### 7. `app.py` 的 Month 1 处理策略

- `KG_construction/app.py`
  - Month 1 不直接大改前端结构。
  - 仅在基础设施和 Planning Agent 后端稳定后，再追加一个最小入口：
    - 输入目标
    - 选择已有文档图或全局图
    - 选择用户画像
    - 展示 day-by-day JSON
- 原因：
  - 当前 `app.py` 已稳定承担 KG 构建任务。
  - 如果在基础设施未稳定前直接塞进 Planning UI，会让调试面过大。

## Implementation Order

### Week 1

1. 抽出 `config.py`、`device_manager.py`、`kg_repository.py`
2. 统一 Stage2a / Stage2c 的设备管理与 benchmark 输出
3. 用现有 `web_data/runs/*` 数据验证 repository 层是否可稳定加载

### Week 2

1. 建立 `ChromaDB` ingest/query 基础设施
2. 建立 `SQLite` 用户画像 schema 和 store
3. 产出 1-2 个 demo 用户画像
4. 产出 KG benchmark 与小样本标注模板

### Week 3

1. 实现 `goal_parser.py`
2. 实现 `topic_mapper.py`
3. 完成自然语言目标到 KG 节点的可解释映射

### Week 4

1. 实现 `path_planner.py`
2. 实现 `time_allocator.py`
3. 实现 `planning_agent.py` 主入口
4. 输出 day-by-day JSON 课程表
5. 用 1-2 个目标案例做端到端验证

## Interfaces and Data Flow

### KG -> Planning Agent

- 输入源：
  - `KG_construction/web_data/global/global_knowledge_graph.json`
  - 或某个 `web_data/runs/<doc>/knowledge_graph.json`
- 中间层：
  - `infra/kg_repository.py`
- 输出给 Planning Agent：
  - 节点属性
  - 先修边
  - 相似边

### Stage1 -> RAG

- 输入：
  - `stage1_chunks.json`
- 中间层：
  - `infra/rag_ingestion.py`
- 输出：
  - Chroma collection，最小 metadata 包括：
    - `doc_name`
    - `chunk_id`
    - `doc_type`
    - `word_count`

### User Profile -> Planning Agent

- 输入：
  - `profile_store.py` 从 SQLite 读取的 profile
- 输出给 Planning Agent：
  - 认知维度权重
  - 情感维度偏好
  - 时间约束
  - 已有知识节点

### Planning Agent 输出

- 输出文件或对象：
  - 先生成 JSON 对象
  - 后续可接入 `app.py` 展示

## Edge Cases and Failure Modes

- 目标无法映射到任何 KG 节点
  - 返回候选节点与未匹配术语，不直接报错崩溃。
- 用户目标时间不足
  - 返回 `feasibility_warning`，并给出裁剪建议。
- KG 中 prerequisite 图不连通
  - 允许只规划可达部分，并报告缺失链路。
- 相似边噪声过多
  - Month 1 先不把相似边用于主路径规划，只用于候选补充和后续 Adaptation Agent 预留。
- OpenAI 不可用
  - goal parsing 退化为规则抽取。
- GPU 不可用
  - `device_manager` 自动回落 CPU，不影响功能正确性。

## Verification Steps

### 基础设施验证

1. 用现有 `global_knowledge_graph.json` 能正常查询指定 topic 的先修链。
2. 用任意一个 `stage1_chunks.json` 能成功写入并从 ChromaDB 召回相关 chunk。
3. SQLite 中能成功创建、读取、更新 demo 用户画像。

### GPU 与 KG 验证

1. 对同一 PDF 跑一次 CPU benchmark。
2. 在可用 GPU 环境下再跑一次 GPU benchmark。
3. 比较 Stage2a、Stage2c 和总耗时。

### KG 质量验证

1. 选 1-2 份课程材料做人工 gold 标注。
2. 统计：
  - topic precision / coverage
  - prerequisite precision
  - similarity useful precision
3. 形成可直接进论文实验部分的小表格。

### Planning Agent 验证

1. 输入 demo 用户画像 + 自然语言目标。
2. 检查是否输出：
  - 目标节点映射
  - 路径顺序正确
  - 每天不超时
  - JSON schema 完整
3. 使用 7-day case 做一次端到端样例。

## Month 2-3 Roadmap (Only High-Level)

### Month 2

- 基于已完成的 `ChromaDB + 用户画像 + Planning JSON` 开始做 `Content Agent`
- 将 KG context、RAG chunks、profile 三路信息融合进 prompt
- 引入 quiz trigger 和 Adaptation Agent

### Month 3

- 做 ablation、plan quality、content coherence、quiz 前后测和用户研究
- 完成论文写作和导师反馈迭代

## Success Criteria for Month 1

- 现有 KG pipeline 保持可运行。
- KG 查询层、RAG、用户画像三块基础设施落地。
- Planning Agent 能从自然语言目标输出可解释的 day-by-day JSON 课程。
- 至少完成一轮 KG 小样本人工评测。
- 至少完成一轮 CPU/GPU 性能对比，证明基础设施优化方向有效。
