# PRD

## 1. 文档目的

本文件用于沉淀当前毕设项目在 `Month 1` 阶段的基础建设事实、模块边界、近期优先级和已知限制，作为后续开发、汇报与答辩的统一口径。

## 2. 项目目标

项目目标是构建一个面向个性化学习规划的智能学习系统，当前以 `KG_construction` 为底座，先完成知识图谱、检索底座、用户画像与课程规划能力，再为后续 `Content Agent`、`Adaptation Agent`、小测与前端交互预留接口。

当前阶段的直接目标如下：

- 复用现有 PDF -> KG 流水线，持续产出可查询的知识图谱数据。
- 建立本地 `RAG` 基础设施，支持后续内容生成时进行 chunk 检索。
- 建立细粒度用户画像存储，支持规划时按认知和情感特征做差异化分配。
- 建立第一版 `Planning Agent`，从自然语言目标生成可解释的逐日学习计划。
- 明确 OpenAI API 配置与 GPU 审计结论，避免把“代码支持”误写成“运行时已验证”。

## 3. 目标用户

- 毕设项目开发者：需要统一掌握当前底座能力、限制和下一步优先级。
- 导师与评审：需要快速理解当前系统范围、已完成模块和尚未闭环部分。
- 后续使用者：需要基于现有 KG、RAG、画像和规划能力继续实现内容生成与自适应学习。

## 4. 系统范围

### 4.1 已纳入范围

- `KG`：从 PDF 材料中抽取 topic、prerequisite、similarity，并导出图谱结果。
- `RAG`：把 `stage1_chunks.json` 写入 `ChromaDB`，提供 chunk 入库与查询接口。
- 用户画像：以 `SQLite` 保存学习者画像，并提供 schema 与读写层。
- `Planning Agent`：基于学习目标、知识图谱和用户画像生成课程规划 JSON。
- API/GPU 审计文档：记录 API 使用方式、验证方式与 GPU 迁移状态。

### 4.2 暂不纳入范围

- `Content Agent` 正式实现。
- `Adaptation Agent` 正式实现。
- 小测、反馈闭环、完整前端规划交互。
- “GPU 迁移已完成”的结论性声明。

## 5. 当前模块现状

### 5.1 KG 基础设施

当前仓库已经具备较完整的知识图谱构建链路：

- `stage1_adaptive_chunking.py` 负责分块与清洗。
- `stage2a_hybrid_keybert_llm.py` 负责 `KeyBERT + SentenceTransformer + OpenAI` 的 topic 提取与精修。
- `stage2b_prerequisites_hybrid.py` 负责先修关系抽取。
- `stage2c_similarity.py` 负责相似关系计算。
- `stage3_node_summary_hybrid.py` 负责节点摘要。
- `stage4_build_and_visualize_kg.py` 负责图谱导出。
- `app.py` 已支持多 PDF 上传、运行 Stage1-4、汇总全局图谱。
- `app.py` 已补上运行时环境自举逻辑：启动时优先把 `KG_construction/.venv/Lib/site-packages` 注入 `sys.path`，并自动加载根目录 `.env`，降低因为错误使用系统 `streamlit` 而导致 `networkx` 等依赖缺失的风险。
- `app.py` 当前不再依赖写死的绝对项目路径，且子进程解释器会优先使用 `KG_construction/.venv/Scripts/python.exe`，找不到时回退到当前 `sys.executable`。
- `infra/kg_repository.py` 已提供图查询抽象层，供上层 agent 复用。
- `infra/baseline_snapshot.py` 与 `freeze_kg_baseline.py` 已提供 baseline 冻结能力，可基于当前 `web_data/global` 与代表性成功运行目录生成结构化快照。
- 当前 baseline 已冻结在 `KG_construction/web_data/baselines/current_kg_baseline`，其中保留了依赖快照、运行状态汇总、回滚计划、复现配方，以及 `Security and Privacy in ML`、`Dreamer`、`Crime` 三份代表样本的分阶段产物。
- 当前 `app.py` 已接入批量稳定性编排层：单文档输出目录改为 `web_data/runs/<doc_name>/<sha12>/`，并在目录内保留 `manifest.json`、`run_log.json`、`recovery_state.json`、`logs/<stage>.json`、`logs/<stage>.log` 与各 stage 原始输出。
- 当前批量运行已支持失败隔离：任一文档在 `stage1-stage4` 失败时，只会将失败状态写入该文档目录与全局批量日志，不会阻断同批次其他 PDF 继续执行。
- 当前批量运行已支持断点续跑：再次上传同一 `filename + sha256` 的失败文档时，会根据 `manifest.json` 校验已有 stage 输出，只从首个未完成或产物失效的 stage 继续执行，并保留之前成功 stage 的产物。
- 当前评测入口已固定为 `KG_construction/evaluation/task4_evaluable_release.py`，默认读取 `evaluation/task4_experiment_manifest.json`，将性能 benchmark 固定到基线快照中的 `Security and Privacy in ML.pdf`，按 `stage1-stage2c` 统一命令和统一输出格式生成正式产物。
- 当前质量评测已固定使用 `evaluation/annotations/task4_security_privacy_*.json` 作为小样本 gold 标注，统一输出 `kg_quality_eval.json` 与 `kg_quality_eval_summary.csv`，指标协议为 `set_precision_recall_f1`。
- 当前论文实验底稿已固定输出到 `KG_construction/web_data/benchmarks/task4_evaluable_release/paper_ready_v1/paper_tables/`，其中保留 `benchmark_table.csv`、`quality_table.csv` 与 `experiment_table_draft.csv`，可直接作为论文实验表格填报底稿。

结论：`KG` 不是规划中的空壳，而是已实现、可复用且已有 baseline 锚点的现有基础设施。

### 5.2 RAG 基础设施

当前仓库已存在 `RAG` 底座代码，不应再按“尚未开始”描述：

- `infra/rag_ingestion.py` 可把 `stage1_chunks.json` 转成结构化 chunk 行并写入向量库。
- `infra/rag_repository.py` 已封装 `ChromaDB` 持久化客户端、embedding、`upsert_chunks()`、`query_chunks()`、`get_chunks_by_topic()`。
- `requirements.txt` 已包含 `chromadb` 依赖。

当前状态：

- 已实现基础设施层。
- 尚未看到 `Content Agent` 直接接入该仓库层的业务闭环。

### 5.3 用户画像基础设施

当前仓库已存在用户画像底座：

- `infra/profile_schema.py` 已定义 `LearnerProfile`，覆盖基本信息、目标约束、认知维度、情感维度、偏好与已知知识。
- `infra/profile_store.py` 已实现 `SQLite` 建表、画像写入、读取与列表查询。
- 仓库内已有 `data/learner_profiles.db`，说明本地画像存储路径已经建立。

当前状态：

- 已实现 schema 与持久化层。
- 尚未看到前端或更完整的画像采集交互。

### 5.4 Planning Agent

当前仓库已存在 `Planning Agent` 主链路代码：

- `agents/planning_agent.py` 已串联 `GoalParser`、`TopicMapper`、`PathPlanner`、`TimeAllocator`。
- `agents/goal_parser.py` 负责自然语言目标解析。
- `agents/topic_mapper.py` 负责目标概念到 KG 节点映射。
- `agents/path_planner.py` 负责先修路径搜索。
- `agents/time_allocator.py` 负责按时间约束和画像权重分配。
- `agents/demo_generate_plan.py` 已提供命令行 demo 入口。
- `tests/` 下已有对应测试文件。

当前状态：

- 已实现后端基础能力与 demo 入口。
- 已接入 `app.py` 的最小交互界面，支持“输入目标 -> 选择用户画像 -> 输出课程计划”。
- 当前前端入口仍属于基础版，只覆盖课程规划结果展示，尚未扩展到完整反馈闭环。

### 5.5 Content Agent 与 Adaptation Agent

当前仓库没有证据表明 `Content Agent` 或 `Adaptation Agent` 已落地为正式代码模块。

当前状态：

- 在规划层面已有明确方向。
- 在实现层面仍属于后续工作，不应写成“已完成”。

## 6. OpenAI API 配置与验证

### 6.1 当前结论

- OpenAI API 已完成项目内配置，并已通过 `KG_construction/test_openai.py` 实测返回 `API OK`。
- 仓库中多个模块通过 `os.getenv("OPENAI_API_KEY")` 读取密钥。
- 项目根目录现已新增 `.env`，并通过 `KG_construction/env_loader.py` 自动加载，因此后续运行不再依赖每次手动在终端里注入环境变量。

### 6.2 当前项目配置方式

当前项目推荐方式为：

- 在项目根目录维护 `.env`
- 通过 `KG_construction/env_loader.py` 自动加载到 Python 进程

说明：

- 该方式适用于 `test_openai.py`、KG pipeline、Planning Agent 等当前已接入的脚本和模块。
- 如需在某些独立终端会话中临时覆盖，也仍可继续使用 PowerShell 环境变量方式。

### 6.3 验证方式

进入 `KG_construction` 后运行：

```powershell
python test_openai.py
```

成功判据：

- 终端输出 `正在测试 OpenAI API...`
- 随后输出 `API 测试成功`
- 响应文本包含 `API OK`

当前状态：

- 该验证已经通过，说明 `.env` 自动加载链路可用。

## 7. GPU 迁移审计

### 7.1 当前已确认事实

- 机器层面已检测到 NVIDIA GPU，可通过 `nvidia-smi` 看到 `NVIDIA GeForce RTX 5060`。
- 当前 Python 虚拟环境中的 `torch` 版本为 `2.12.0+cpu`。
- 当前 `torch.cuda.is_available()` 返回 `False`，说明现有运行时仍未进入 GPU 模式。
- `infra/device_manager.py` 已统一封装 `resolve_torch_device()`、`get_embedding_batch_size()`、`get_device_info()`。
- `infra/device_manager.py` 已支持 `KG_FORCE_DEVICE` 强制设备请求、CUDA 真实运行时探测、结构化失败原因记录，以及统一的模型加载回退辅助逻辑。
- `stage2a_hybrid_keybert_llm.py` 已接入设备管理，并将 `device_info`、`batch_size`、`duration_seconds` 写入 `benchmark` 字段。
- `stage2c_similarity.py` 已接入设备管理，并输出同类 `benchmark` 信息。
- `infra/rag_repository.py` 与 `infra/rag_ingestion.py` 已接入同一套设备解析与回退逻辑，并可输出结构化 `device_info`。
- `evaluation/kg_benchmark.py` 已提供阶段级 benchmark 入口。
- `evaluation/task2_gpu_runtime_validation.py` 已提供 Task 2 专用验证入口，可同时产出 GPU 探测日志、CPU 基线和“请求 CUDA 后的实际运行结果”对比产物。

### 7.2 当前不能下的结论

以下结论当前仍不能写入文档：

- “系统已经完成 GPU 迁移”
- “Stage2a/Stage2c 已在生产运行中稳定使用 CUDA”
- “GPU 相对 CPU 已有明确加速收益”

原因：

- 当前环境虽然已经完成正式验证，但验证结果显示 `.venv` 中的 `torch` 仍是 `2.12.0+cpu`，并非 CUDA build。
- `nvidia-smi` 已能识别 `NVIDIA GeForce RTX 5060 Laptop GPU`，但 `torch.version.cuda is None` 且 `torch.cuda.is_available()` 为 `False`，因此无法形成真实 CUDA 运行证据。

### 7.3 当前审计结论

当前最准确的表达是：

- 已完成 Task 2 代码层改造：`stage2a`、`stage2c`、RAG 向量化均已统一为“优先请求 GPU，失败后稳定回退 CPU”的执行链路。
- 已完成运行时验证与阶段输出物沉淀，验证目录位于 `KG_construction/web_data/benchmarks/task2_gpu_priority/20260622_220403`。
- 已留下 `device_validation.json`、`gpu_validation.log`、`benchmark_comparison.json` 以及 CPU / `cuda_requested` 两套阶段输出物，能清楚说明请求设备、实际设备、回退原因和耗时。
- 机器上存在可用 NVIDIA GPU，但当前 Python 虚拟环境仍是 CPU 版 `torch`，所以本次未能真正打通 CUDA 运行时。

### 7.4 如何确认实际运行在 CUDA

至少满足以下任一证据后，才可对外写“已完成运行时确认”：

- `stage2a_hybrid_keybert_llm.py` 输出中的 `benchmark.device_info.device` 为 `cuda`。
- `stage2c_similarity.py` 输出中的 `benchmark.device_info.device` 为 `cuda`。
- `evaluation/kg_benchmark.py` 产出正式 benchmark 结果，并能展示 CPU/GPU 对比数据。

当前最新验证结果：

- `evaluation/task2_gpu_runtime_validation.py` 已实际运行完成。
- `device_validation.json` 明确记录 `torch_version=2.12.0+cpu`、`torch_cuda_build=null`、`cuda_available=false`。
- 同一份验证中 `nvidia-smi` 返回 `NVIDIA GeForce RTX 5060 Laptop GPU`，说明问题在 Python 运行时而不是机器无显卡。
- `benchmark_comparison.json` 中 `true_gpu_verified=false`，说明当前仅验证了“请求 CUDA 后会稳定回退 CPU”，尚未验证真实 CUDA 执行。

## 8. Task 1-4 阶段状态总览

### 8.1 四块状态与阶段输出物

#### baseline 冻结

- 当前状态：已完成工程版 baseline 冻结，可作为后续升级、回滚和复现锚点。
- 状态口径：这里的“完成”是指 baseline 快照机制、代表样本选择、依赖快照与复现配方均已沉淀；不等于整个项目已经完成最终验收。
- 阶段输出物：`KG_construction/web_data/baselines/current_kg_baseline/` 下的 `baseline_manifest.json`、`dependencies.json`、`run_status_summary.json`、`artifacts_index.json`、`restore_plan.json`、`reproduction_recipe.json`，以及 `Security and Privacy in ML`、`Dreamer`、`Crime` 三份代表样本的分阶段产物。

#### GPU 优先执行链路

- 当前状态：已完成工程版“GPU 优先请求 + CPU 稳定回退 + 结构化验证产物”链路；未完成真实 CUDA 运行时打通。
- 状态口径：当前可以写“已完成 Task 2 工程改造与验证留痕”，不能写“已完成 GPU 迁移”或“已确认 CUDA 正式运行”。
- 阶段输出物：`KG_construction/web_data/benchmarks/task2_gpu_priority/20260622_220403/` 下的 `device_validation.json`、`gpu_validation.log`、`benchmark_comparison.json`，以及 CPU / `cuda_requested` 两套阶段输出目录。

#### 批量稳定性

- 当前状态：已完成工程版批量稳定性增强，支持运行隔离、断点续跑、结构化日志和文档级恢复状态。
- 状态口径：当前可以写“批量链路具备稳定运行所需的工程约束”；不能跳写成“所有异常场景都已完成最终验收”。
- 阶段输出物：单文档目录 `web_data/runs/<doc_name>/<sha12>/` 下的 `manifest.json`、`run_log.json`、`recovery_state.json`、`logs/<stage>.json`、`logs/<stage>.log`，以及全局 `KG_construction/web_data/global/batch_run_log.json`。

#### 可评测版本

- 当前状态：已完成工程版可评测发布面，benchmark、质量评测和论文表格底稿已固定输入、固定协议和固定输出目录。
- 状态口径：当前可以写“已形成可复现实验版本”；不能写“所有指标已达标”或“评测阶段已完成最终验收”。
- 阶段输出物：`KG_construction/web_data/benchmarks/task4_evaluable_release/paper_ready_v1/` 下的 `benchmark/kg_benchmark.json`、`benchmark/kg_benchmark_summary.csv`、`quality_eval/kg_quality_eval.json`、`quality_eval/kg_quality_eval_summary.csv`、`paper_tables/benchmark_table.csv`、`paper_tables/quality_table.csv`、`paper_tables/experiment_table_draft.csv`、`paper_tables/task4_run_report.json`、`artifacts_index.json`。

### 8.2 工程版本与原型版本的状态边界

- 当前仓库中，`KG` 主链路已经进入工程版本：baseline、GPU 优先执行链路、批量稳定性和可评测发布面都已有固定目录、结构化输出物、复现或恢复入口，以及明确的状态口径。
- 当前仓库中，`Planning Agent`、`RAG`、用户画像与主应用交互仍主要处于原型版本到早期工程化过渡阶段：它们已经可运行、可演示，但尚未形成完整产品闭环。
- 工程版本的判定标准是：不仅“代码存在”，还要求“运行路径固定”“输出物结构化”“结果可追踪”“失败可恢复或可审计”“文档口径明确”。
- 原型版本的判定标准是：已经证明方向可行并具备最小可用入口，但在完整交互、规模化验证、最终验收、长期运维约束方面仍不充分。
- 因此当前最准确的整体表述应为：仓库已具备工程版 `KG` 流水线底座和可评测发布面，但上层学习产品体验仍以原型能力为主。
- Task 5 只负责同步文档与项目状态，不包含 Task 6 的最终验收逻辑；诸如 baseline 回滚复现验收、真实 CUDA 运行时验收、批量失败隔离验收和评测稳定产出验收，仍属于后续 Task 6 范围。

## 9. Month 1 优先级与依赖关系

### 9.1 优先级排序

1. 保持 KG 主链路稳定可运行。
2. 以 `current_kg_baseline` 作为后续升级的回滚与复现锚点。
3. 继续以已实现的 API 配置方式作为统一环境前提。
4. 对 GPU 做一次正式运行时 benchmark，补齐证据。
5. 继续在 `app.py` 中稳定现有 `Planning Agent` 入口，并验证真实用户目标的输出质量。
6. 复用现有 `RAG`、用户画像和规划结果推进 `Content Agent`。
7. 之后再推进 `Adaptation Agent`。

## 10. Task 6 最终验收结论

### 10.1 验收时间与方法

- 验收时间：`2026-06-22`
- 验收方法：逐项核对 `.trae/specs/upgrade-kg-engineering-pipeline/checklist.md`，并结合代码、现存产物、固定评测入口重跑结果与 baseline 复现实跑结果独立判定。
- 本节结论用于覆盖 Task 5 阶段性文档口径；凡未在本节通过的项，均不得对外写成“最终验收通过”。

### 10.2 已通过项

- baseline 冻结产物已存在：`current_kg_baseline/` 下已保留 `baseline_manifest.json`、`dependencies.json`、`run_status_summary.json`、`restore_plan.json`、`reproduction_recipe.json` 和代表样本快照。
- baseline 与工程升级版本已可区分：baseline 固定在 `KG_construction/web_data/baselines/current_kg_baseline/`，工程升级产物位于 `task2_gpu_priority/`、`task4_evaluable_release/` 等独立目录。
- 设备管理代码已统一接入：`device_manager.py` 已被 `stage2a`、`stage2c` 与 RAG 向量化链路复用；在当前 CPU-only `torch` 环境中，CPU 回退证据真实存在。
- Task 4 的 benchmark/quality eval 固定入口、固定输入、固定输出目录已经形成，且 `evaluation/task4_evaluable_release.py` 可以再次实际运行并产出结果。

### 10.3 未通过项

- baseline 可复现未通过：按 `reproduction_recipe.json` 实跑代表样本后，`stage1` 哈希一致，但 `stage2a` 与 `stage2b` 输出哈希均与 baseline 配方不一致，当前不能写“baseline 可回滚、可复现已验收通过”。
- GPU 运行时确认未通过：`device_validation.json`、`benchmark_comparison.json` 以及重跑产物都显示 `requested_device = cuda` 但 `selected_device/device = cpu`，仅证明“请求 GPU 后稳定回退 CPU”，不能证明真实 CUDA 已进入运行时。
- 批量稳定性验收未通过：`app.py` 已实现 `manifest/run_log/recovery_state/batch_run_log` 写出逻辑，但当前 `web_data/runs/` 真实运行目录仍主要是旧结构，缺少可供验收的 `manifest.json`、`run_log.json`、`recovery_state.json`，`web_data/global/batch_run_log.json` 也不存在。
- 评测稳定性未通过：同一固定入口 `evaluation/task4_evaluable_release.py` 重跑后，benchmark `total_seconds` 从 `103.852s` 变为 `130.432s`；质量评测中 `similarity` 指标也从旧结果 `precision=0.3333 / recall=0.3333 / f1=0.3333` 变为新结果 `precision=1.0 / recall=0.3333 / f1=0.5`，说明当前结果尚未达到“稳定复现”。
- 论文实验可直接使用未通过：虽然表格底稿与 JSON/CSV 产物可生成，但在 GPU 运行时未确认、批量稳定性无真实验收证据、评测结果重跑波动明显的前提下，当前更准确的口径应是“论文实验草稿可用”，而不是“论文实验正式结果已就绪”。

### 10.4 当前对外口径

- 可以写：baseline 冻结机制、GPU 优先请求与 CPU 回退链路、批量稳定性代码框架、固定评测入口与论文表格底稿均已具备。
- 不可以写：baseline 已完成复现验收、CUDA 已完成运行时确认、批量失败隔离已完成最终验收、benchmark/quality eval 结果已稳定到可直接作为论文正式实验结果。

### 10.5 后续修复方向

- 优先修复 baseline 中 `stage2a-stage4` 的非确定性来源，并重新沉淀代表样本的复现实验哈希。
- 优先确认 CUDA 版 `torch` 与依赖环境，补齐 `stage2a`/`stage2c` 的真实 `device_info.device = cuda` 证据；若近期无法打通，则文档统一降级为 CPU-only 已验证。
- 使用至少一组真实批量样本补跑 `app.py` 新链路，产出文档级 `manifest/run_log/recovery_state` 和全局 `batch_run_log.json`，再做失败隔离与断点续跑验收。
- 为 Task 4 增加稳定性约束，明确 benchmark 波动阈值、固定随机性来源，并重新校准论文实验使用口径。

## 11. 依赖关系

- `Planning Agent` 依赖 `KGRepository` 与用户画像输入，当前已在 `app.py` 中形成最小可用入口。
- 后续 `Content Agent` 依赖 `RAGRepository` 与规划结果。
- GPU 优化依赖 CUDA 版 `torch` 安装成功，以及实际运行日志与 benchmark 产物，而不只是代码中存在 `cuda` 分支。
- 批量稳定性当前依赖 `web_data/runs/<doc_name>/<sha12>/manifest.json` 中记录的 stage 状态与产物路径来判断是否可恢复，因此恢复时应保留对应目录下的 `manifest`、`run_log`、`recovery_state`、`logs/` 和 stage 输出文件。
- 正式论文评测当前依赖 `evaluation/task4_experiment_manifest.json` 中固定的样本路径、gold 标注路径与输出目录；若调整样本或指标协议，应同步更新该 manifest 和 `paper_tables/` 底稿。

## 12. 已知限制

- `Content Agent` 与 `Adaptation Agent` 仍未落地。
- `Planning Agent` 已接入主应用的最小界面，但还没有扩展到更完整的画像编辑、计划反馈和内容生成联动。
- API 已通过 `.env` 自动加载接入项目，但协作时仍需要统一密钥管理方式。
- GPU 当前处于“机器有显卡、Task 2 代码链路已完成、且失败回退已验证，但 Python 运行时仍未切到 CUDA”的状态。
- baseline 冻结当前仅覆盖全局状态和 3 份代表样本，后续 GPU、批量稳定和评测阶段仍需在此基础上继续沉淀独立输出物。
- 断点续跑当前以“同一 `filename + sha256` 对应同一运行目录”为前提，若手动删除某个文档目录下的 `manifest.json` 或关键 stage 输出，将触发从更早 stage 重跑。
- Task 4 当前已沉淀可复现实验目录与结果文件，但质量评测的小样本 gold 仍是论文实验用的人工子集，不能替代更大规模人工标注集。

## 13. 文档维护规则

- 后续每次基础设施或阶段性改动，都应同步更新 `PRD.md` 与 `CHANGELOG.md`。
- 文档必须区分“已实现”“已配置”“已验证”“已沉淀证据”四种状态。

## 14. 2026-07-07 当前最新进展：Neo4j 三层架构与 Resource 闭环

项目当前已经推进到“Neo4j Knowledge Graph Layer 可复现构建”阶段。最终架构边界已经明确为三层：Knowledge Graph Layer 使用 Neo4j/Cypher 存结构化领域知识；Profile Store 使用 SQLite/JSON 存 learner profile、mastery、progress、deadline 等用户动态状态；RAG Layer 使用 ChromaDB 存 resource chunks、embeddings 和文本证据。

当前已经完成的是 Knowledge Graph Layer 的 Neo4j 化，以及 Content/Adaptation 所需的结构上下文接口；Content Agent 和 Adaptation Agent 的完整业务闭环仍属于下一阶段。

### 14.1 Neo4j 已完成内容

已新增并验证以下 Neo4j 基础设施：

- `KG_construction/infra/neo4j_importer.py`
- `KG_construction/infra/neo4j_repository.py`
- `KG_construction/infra/neo4j_schema.cypher`
- `KG_construction/infra/neo4j_verify.py`
- `KG_construction/infra/neo4j_diagnostics.py`
- `KG_construction/infra/neo4j_migration_acceptance.py`
- `KG_construction/infra/neo4j_resource_batch_importer.py`

当前 Neo4j 节点和关系设计：`Concept`、`Topic`、`Resource`；`PREREQUISITE_OF`、`SIMILAR_TO`、`BELONGS_TO`、`HAS_RESOURCE`。Neo4j 不存 learner 动态状态，也不存 chunk 正文和 embedding。Resource 节点只存资源身份字段，ChromaDB 通过 `resource_id` 与 Neo4j `Resource.id` 对齐。

### 14.2 当前 live 验收数据

截至 2026-07-07，当前 live Neo4j 验收结果为：

```text
Concept = 84
PREREQUISITE_OF = 61
SIMILAR_TO = 12
Resource = 10
HAS_RESOURCE = 96
forbidden learner dynamic fields = 0
Resource required fields = complete
```

其中 app 新上传文档 `cs224n-2026-lecture01-history.pdf` 已经生成完整 run 目录，并已写入 Neo4j：

```text
web_data/runs/cs224n-2026-lecture01-history/5845dce2ddc2/
```

该目录包含 `knowledge_graph.json`、`stage1_chunks.json`、`manifest.json`、`run_log.json`、`recovery_state.json`、stage 输出文件与 logs。对应 Neo4j Resource 已建立，Resource count 从 9 增至 10，HAS_RESOURCE count 从 87 增至 96。

### 14.3 Agent 当前状态

Planning Agent 当前已经支持 JSON / Neo4j backend 切换：`KG_BACKEND=json` 与 `KG_BACKEND=neo4j`。已验证 JSON 与 Neo4j 在 Planning 核心输出上的一致性，包括 target mapping、prerequisite paths、ordered topics、day-by-day plan、prerequisite bridge 和 overflow topics。

Content Agent 当前不是完整生成型 Agent，但已经有 `agents/content_context_service.py`，可从 Neo4j 获取 concept、prerequisites、similar concepts、resources。当前 smoke test 显示 `Neural Networks` 可以返回相关 Resource，其中包括新上传的 `cs224n-2026-lecture01-history.pdf`。

Adaptation Agent 当前不是完整闭环 Agent，但已经有 `agents/adaptation_candidate_service.py`。它优先查 `SIMILAR_TO`，不足时回退到 prerequisite bridge；当前不写 Profile Store，也不重排正式学习日历。

### 14.4 RAG 当前状态

RAG 基础设施已经存在：`infra/rag_ingestion.py` 与 `infra/rag_repository.py`。当前 metadata 对齐规则为：`stage1_chunks.json` ingestion 时 metadata 包含 `resource_id` 和 `resource_filename`；`resource_id` 与 Neo4j `Resource.id` 使用同一值；chunk 正文和 embedding 仍只进入 ChromaDB，不写入 Neo4j。

尚未完成的是 KG-constrained RAG 生成闭环。当前 smoke test 中 `rag_chunks=0`，说明结构上下文已通，但内容生成所需的 chunk 检索闭环仍需下一阶段补齐。

### 14.5 App 上传与 Neo4j 复现链路

当前 app 上传后的标准 run 结构是：

```text
web_data/runs/<doc_name>/<sha12>/
```

已修复 `neo4j_resource_batch_importer.py`，使其同时支持旧结构 `web_data/runs/<doc_name>/knowledge_graph.json` 和新结构 `web_data/runs/<doc_name>/<sha12>/knowledge_graph.json`。因此后续 app 上传新 PDF 后，可以继续使用同一个批量命令补 Resource。

建议从项目根目录运行复现命令：

```powershell
cd "D:\ic\master project\project_code"

.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_importer.py --graph KG_construction\web_data\global\global_knowledge_graph.json

.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_resource_batch_importer.py --runs-dir KG_construction\web_data\runs

.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\neo4j_verify.py --graph KG_construction\web_data\global\global_knowledge_graph.json --live --include-resources --min-resources 10 --min-has-resource-edges 96

.\KG_construction\.venv\Scripts\python.exe KG_construction\infra\agent_context_smoke.py --backend neo4j --graph KG_construction\web_data\global\global_knowledge_graph.json --concept "Neural Networks"
```

当前测试状态：

```text
67 tests OK
Neo4j live verify passed
Content/Adaptation context smoke passed
```

### 14.6 当前已知问题

- Codex in-app browser 访问 Windows 本机 `localhost:8501` 不稳定；系统浏览器访问 `http://localhost:8501` 更可靠。
- app 上传只会生成 run 目录和全局 JSON，不应假设它自动写入 Neo4j；Neo4j 写入仍通过 importer 完成。
- Content Agent 尚未完整落地为“检索 chunk -> 引用证据 -> 生成讲义”的闭环。
- Adaptation Agent 尚未完整落地为“quiz/self-feedback -> 更新 profile -> 重新分配剩余时间”的闭环。
- RAG chunks 与 concept 的细粒度对齐仍偏弱，目前 Resource 关系是 run-level 粒度。
- GPU 仍未形成真实 CUDA runtime 验证证据，不能写成 GPU 迁移完成。

## 15. 下一阶段建议路线

### 15.1 第一优先级：把上传到 Neo4j 的链路产品化

目标：用户上传 PDF 后，系统能清楚显示“KG JSON 已生成 / Neo4j 已同步 / Resource 已写入 / RAG chunks 已入库”四个状态。

建议任务：

1. 在 app 中增加 Neo4j 同步按钮或自动同步选项。
2. 上传完成后显示 run 目录、Concept 数量、关系数量、Resource id。
3. 将 `neo4j_importer.py` 和 `neo4j_resource_batch_importer.py` 的结果展示到前端。
4. 如果 Neo4j 未启动，给出明确提示，并允许继续使用 JSON backend。

验收标准：新上传 1 个 PDF 后 Neo4j `Resource` 和 `HAS_RESOURCE` 数量增长，`neo4j_verify.py --include-resources` 通过，页面能显示同步结果。

### 15.2 第二优先级：打通 RAG ingestion 与 Resource metadata

目标：让 Content Agent 能真正拿到文本证据，而不是只有 KG 结构上下文。

建议任务：

1. 修复或补充 `rag_ingestion.py` 的非交互 CLI 参数，例如 `--stage1-path`。
2. 对 app 新上传 run 自动或手动执行 RAG ingestion。
3. ChromaDB metadata 固定包含 `resource_id/resource_filename/doc_name/chunk_id/concept_name`。
4. 在 `ContentContextService` 中按 Resource 和 Concept 查询 chunks。

验收标准：对 `cs224n-2026-lecture01-history` 执行 RAG ingestion 后，ChromaDB 能查到 chunks，`agent_context_smoke.py` 中 `rag_chunks > 0`。

### 15.3 第三优先级：实现第一版 Content Agent

目标：从 Planning Agent 的某一天 topics 出发，生成一份有证据来源的个性化讲义。

建议任务：输入 `user_id + day_topics + profile`；查询 KG prerequisites、similar concepts、resources；限定 Resource / Concept 查询 RAG chunks；输出讲义、关键概念、例子、练习题和引用 chunk id；根据 profile 调整深度、语气和例子。

验收标准：生成内容必须包含引用到的 `resource_id/chunk_id`，不允许在没有 chunks 时假装有证据。

### 15.4 第四优先级：实现规则版 Adaptation Agent

目标：先不做强化学习，先实现可解释的规则闭环。

建议任务：输入 quiz/self-feedback；更新 Profile Store 中 mastery/progress；对 weak concept 查询 `SIMILAR_TO` 和 prerequisite neighbors；插入补救 concept 或辅助 concept；重新分配剩余学习时间，尽量不改 deadline。

验收标准：Profile Store 被更新，Neo4j 不写入 learner state；weak concept 能返回补救建议；调整后的计划保留 deadline，无法保留时给 warning。

### 15.5 第五优先级：论文实验与最终验收

目标：把毕业设计需要的“可复现证据”整理成实验章节可用材料。

建议任务：固定代表性 PDF、Neo4j 复现命令、RAG ingestion、Content Agent 输出样例、Planning JSON/Neo4j 一致性对比结果，并明确 GPU 仍是 CPU fallback。

验收标准：一键或少量命令可重建 Neo4j KG；Resource / RAG / Profile 三层边界清楚；有至少 1 条完整用户故事：上传文档 -> 生成 KG -> Neo4j 同步 -> 规划 -> 内容生成 -> 反馈调整。

## 16. 2026-07-08 Runtime Infrastructure and Node Details QA

Runtime Infrastructure v1 is now implemented as the reproducibility and quality-control layer for the KG system. It does not replace Planning / Content / Adaptation logic. Its responsibility is to audit KG node details, calibrate difficulty deterministically, benchmark KG readiness, run reproducibility checks, and record structured harness manifests.

New scripts:

```text
KG_construction/infra/node_details_audit.py
KG_construction/infra/difficulty_calibration.py
KG_construction/infra/benchmark_kg.py
KG_construction/infra/reproducibility_check.py
KG_construction/infra/harness.py
```

New outputs:

```text
KG_construction/web_data/manifests/harness_*.json
KG_construction/web_data/global/global_knowledge_graph_calibrated.json
```

Current Runtime validation:

```text
Node details audit:
  total_concepts = 183
  description coverage = 0.918
  difficulty coverage = 1.0
  estimated learning time coverage = 1.0
  difficulty distribution = {1: 0.0492, 2: 0.918, 3: 0.0328}
  warning = difficulty_level is overly concentrated at level 2

Difficulty calibration:
  deterministic = true
  updated_concepts = 117
  unchanged_concepts = 66
  original global_knowledge_graph.json is not overwritten

KG benchmark:
  concept_count = 183
  edge_count = 178
  prerequisite_edges = 152
  similarity_edges = 26
  isolated_concept_count = 24
  duplicate_concept_count = 0

Live Neo4j harness:
  Concept = 183
  Topic = 8
  Resource = 27
  PREREQUISITE_OF = 152
  SIMILAR_TO = 26
  HAS_RESOURCE = 248
  BELONGS_TO = 183
  forbidden learner state nodes = 0
```

Runtime commands:

```powershell
cd KG_construction
.\.venv\Scripts\python.exe infra\node_details_audit.py --graph web_data\global\global_knowledge_graph.json
.\.venv\Scripts\python.exe infra\difficulty_calibration.py --graph web_data\global\global_knowledge_graph.json --output web_data\global\global_knowledge_graph_calibrated.json
.\.venv\Scripts\python.exe infra\benchmark_kg.py --graph web_data\global\global_knowledge_graph.json
.\.venv\Scripts\python.exe infra\reproducibility_check.py --graph web_data\global\global_knowledge_graph.json
.\.venv\Scripts\python.exe infra\harness.py --stage all --graph web_data\global\global_knowledge_graph.json
.\.venv\Scripts\python.exe infra\harness.py --stage neo4j --graph web_data\global\global_knowledge_graph.json --live-neo4j
```

App status: a `Check Runtime Infrastructure` button now exposes Node details audit, KG benchmark, Profile Store verify, and latest harness manifest. Runtime warning is allowed when it represents a detected quality issue rather than execution failure.

## 17. 2026-07-08 Runtime Harness App Tab and Full Infra Checks

Runtime Harness has been extended from KG-only checks into a safer multi-stage infra validation harness. The harness now supports:

```text
audit
calibrate
kg_benchmark
profile
rag
planning
reproducibility
neo4j
all
```

The `rag` stage verifies ChromaDB chunk availability without running ingestion. Current validation:

```text
collection = kg_chunks
total_count = 424
status = success
```

The `planning` stage uses deterministic Planning backend comparison and avoids LLM goal parsing / embedding target mapping by passing a stable target concept. Current validation:

```text
goal = learn neural networks
target_concept = Neural Networks
json_neo4j_parity = true
status = success
```

The full harness command now records each stage result in a manifest:

```powershell
cd KG_construction
.\.venv\Scripts\python.exe infra\harness.py --stage all --graph web_data\global\global_knowledge_graph.json
```

Latest full harness validation:

```text
manifest = web_data/manifests/harness_2026-07-08_140156.json
overall status = warning
audit = warning
calibrate = success
kg_benchmark = success
profile = success
rag = success
planning = success
reproducibility = success
neo4j = success
```

The warning is expected and useful: difficulty_level remains overly concentrated at level 2. It is treated as a quality-control signal rather than an execution failure.

The app now has a `Runtime Harness` tab. This tab shows the current Runtime Infrastructure status and allows the user to run a selected harness stage or the full harness. Each stage is shown as a row and can be expanded to inspect the exact JSON result.
