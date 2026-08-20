# CHANGELOG

## 2026-07-07

### Added

- 新增 Neo4j Knowledge Graph Layer 迁移与验收基础设施：
  - `KG_construction/infra/neo4j_importer.py`
  - `KG_construction/infra/neo4j_repository.py`
  - `KG_construction/infra/neo4j_schema.cypher`
  - `KG_construction/infra/neo4j_verify.py`
  - `KG_construction/infra/neo4j_diagnostics.py`
  - `KG_construction/infra/neo4j_migration_acceptance.py`
- 新增 `KG_construction/infra/neo4j_resource_batch_importer.py`，用于批量从 `web_data/runs` 中识别 run-level PDF Resource，并写入 `(:Concept)-[:HAS_RESOURCE]->(:Resource)`。
- 新增 Content/Adaptation 结构上下文基础服务：
  - `KG_construction/agents/content_context_service.py`
  - `KG_construction/agents/adaptation_candidate_service.py`
- 新增 Neo4j / JSON backend 切换能力，Planning Agent 可通过 `KG_BACKEND=json` 或 `KG_BACKEND=neo4j` 读取知识图谱。
- 新增 Resource-aware live verify 能力，支持验证 `Resource` 数量、`HAS_RESOURCE` 数量和 Resource 必填字段完整性。

### Changed

- 将 Knowledge Graph Layer 职责边界固定为 Neo4j 只存结构化领域知识，不存 learner profile、mastery、progress、deadline，也不存 chunk 正文和 embedding。
- 将当前 KG 节点和边统一为：
  - Nodes：`Concept`、`Topic`、`Resource`
  - Edges：`PREREQUISITE_OF`、`SIMILAR_TO`、`BELONGS_TO`、`HAS_RESOURCE`
- 增强 `neo4j_resource_batch_importer.py`，支持两种 run 目录结构：
  - 旧结构：`web_data/runs/<doc_name>/knowledge_graph.json`
  - 新结构：`web_data/runs/<doc_name>/<sha12>/knowledge_graph.json`
- 增强 RAG metadata 对齐：`stage1_chunks.json` ingestion 行中增加 `resource_id` 和 `resource_filename`，并与 Neo4j `Resource.id` 对齐。
- 更新 `KG_construction/NEO4J_MIGRATION.md`，补充 Neo4j/Cypher 架构、Resource 批量导入、Resource-aware verify、RAG metadata 对齐和复现命令。
- 新增本地 Streamlit 启动辅助脚本：
  - `KG_construction/run_streamlit_app.ps1`
  - `KG_construction/run_streamlit_app.cmd`
  - `KG_construction/run_streamlit_app_logged.cmd`

### Verified

- 已将当前 `global_knowledge_graph.json` 同步到 live Neo4j。
- 当前 live Neo4j 验收通过：

```text
Concept = 84
PREREQUISITE_OF = 61
SIMILAR_TO = 12
Resource = 10
HAS_RESOURCE = 96
forbidden learner dynamic fields = 0
Resource required fields = complete
```

- 已验证 app 新上传文档 `cs224n-2026-lecture01-history.pdf` 可生成标准 run 目录：

```text
KG_construction/web_data/runs/cs224n-2026-lecture01-history/5845dce2ddc2/
```

- 已验证该新上传文档被写入 Neo4j Resource，并建立 9 条 `HAS_RESOURCE` 关系。
- 已验证 Planning Agent JSON / Neo4j backend 核心输出一致。
- 已验证 Content/Adaptation context smoke：
  - `Neural Networks` 可以从 Neo4j 返回 prerequisites。
  - `Neural Networks` 可以返回 Resource 列表。
  - Resource 列表包含新上传的 `cs224n-2026-lecture01-history.pdf`。
  - Adaptation candidate retrieval 可返回 prerequisite bridge candidates。
- 全量测试通过：

```text
67 tests OK
```

### Known Issues

- Codex in-app browser 访问 Windows 本机 `localhost:8501` 不稳定；系统浏览器访问 `http://localhost:8501` 更可靠。
- app 上传后当前仍需要 importer 同步 Neo4j；尚未在页面内自动完成 Neo4j 写入和验收展示。
- RAG chunk 入库与 Content Agent 生成闭环尚未完成；当前结构上下文已通，但 `rag_chunks` 仍可能为 0。
- Resource 与 Concept 的关系当前是 run-level 粒度；更细粒度的 concept-to-chunk 对齐仍需后续补强。
- GPU 仍未形成真实 CUDA runtime 验证证据，当前只能写成 CPU fallback 已验证。

### Next

- 第一优先级：把 app 上传后的 Neo4j 同步产品化，在页面中显示 KG JSON、Neo4j Resource、HAS_RESOURCE 和验收结果。
- 第二优先级：给 `rag_ingestion.py` 增加非交互 CLI 参数，并把 app run 的 `stage1_chunks.json` 入库到 ChromaDB。
- 第三优先级：实现第一版 Content Agent，要求输出必须引用 `resource_id/chunk_id`。
- 第四优先级：实现规则版 Adaptation Agent，完成 quiz/self-feedback -> Profile Store 更新 -> remediation candidates -> plan adjustment。
- 第五优先级：整理论文实验复现路径，固定代表性 PDF、Neo4j 验收命令、Planning JSON/Neo4j 对比、RAG/Content 输出样例。

## 2026-06-29

### Fixed

- 修复 `KG_construction/app.py` 在非虚拟环境 `streamlit` 启动时的导入失败问题：应用启动前会优先把 `KG_construction/.venv/Lib/site-packages` 注入 `sys.path`，避免 `PlanningAgent` 导入链因为缺少 `networkx` 而直接崩溃。
- 修复 `KG_construction/app.py` 的环境初始化问题：启动时自动加载根目录 `.env`，让规划模块和后续流水线脚本更稳定地读取 `OPENAI_API_KEY`。
- 修复 `KG_construction/app.py` 的路径与解释器脆弱性：项目目录改为基于 `app.py` 动态解析，子进程解释器优先使用 `KG_construction/.venv/Scripts/python.exe`，否则回退到当前 `sys.executable`。

## 2026-06-22

### Added

- 新增 `KG_construction/infra/baseline_snapshot.py`，用于盘点当前 `web_data/runs` 与 `web_data/global`，并冻结当前可用 KG baseline。
- 新增 `KG_construction/freeze_kg_baseline.py`，提供一键生成 baseline 快照的入口脚本。
- 新增 `KG_construction/web_data/baselines/current_kg_baseline/`，保存当前 baseline 的结构化产物与代表样本快照。

### Structured Outputs

- 新增 `baseline_manifest.json`，记录 baseline 目录、代表样本、关键输出和回滚/复现证明。
- 新增 `dependencies.json`，记录 `requirements.txt`、Python 版本与当前环境 `pip freeze` 结果。
- 新增 `run_status_summary.json`，汇总当前 `runs` 目录的完成度、阶段状态和代表样本选择结果。
- 新增 `artifacts_index.json`、`restore_plan.json`、`reproduction_recipe.json`，分别用于产物索引、回滚操作说明和按阶段复现配方。

### Snapshot

- 冻结了 `web_data/global` 下的 `global_knowledge_graph.json`、`processed_files.json`、`upload_history.json`。
- 冻结了 `Security and Privacy in ML`、`Dreamer`、`Crime` 三份最近成功且具备 Stage1-Stage4 核心产物的代表样本目录。
- 为代表样本保留了输入 PDF、`stage1_chunks.json`、`stage2a_topics_hybrid.json`、`stage2b_prerequisites.json`、`stage2c_similarity_edges.json`、`stage3_topics_with_summary.json`、`knowledge_graph.json`、`knowledge_graph.gexf` 及可视化图片。

### Verified

- 已执行 `KG_construction/freeze_kg_baseline.py`，确认 baseline 生成位置为 `KG_construction/web_data/baselines/current_kg_baseline`。
- 复现配方已写入 `reproduction_recipe.json`，可针对主代表样本逐阶段重跑，并用 `sha256` 校验输出是否与 baseline 一致。

### Updated

- 更新 `KG_construction/infra/device_manager.py`，统一收口本地模型设备请求逻辑，支持 `KG_FORCE_DEVICE`、CUDA 真实运行时探测、结构化失败原因与稳定 CPU 回退。
- 更新 `KG_construction/stage2a_hybrid_keybert_llm.py`，让 `stage2a` 通过统一设备管理加载 `SentenceTransformer`，并把请求设备/实际设备/回退原因写入输出 `benchmark.device_info`。
- 更新 `KG_construction/stage2c_similarity.py`，让 `stage2c` 与 `stage2a` 使用同一套 GPU 优先 / CPU 回退逻辑，并输出统一 `device_info`。
- 更新 `KG_construction/infra/rag_repository.py` 与 `infra/rag_ingestion.py`，让 RAG 向量化链路共用统一设备管理并可输出结构化运行时信息。
- 更新 `.trae/specs/upgrade-kg-engineering-pipeline/tasks.md`，勾选完成 Task 2 及其全部子任务。

### Added

- 新增 `KG_construction/evaluation/task2_gpu_runtime_validation.py`，用于一次性产出 Task 2 的设备验证日志、阶段输出物和 benchmark 对比结果。
- 新增 `KG_construction/tests/test_device_manager.py`，覆盖 CUDA 请求失败回退和加载失败回退行为。

### Runtime Validation

- 已执行 `KG_construction/evaluation/task2_gpu_runtime_validation.py`，产物输出到 `KG_construction/web_data/benchmarks/task2_gpu_priority/20260622_220403`。
- 新增 `device_validation.json`，记录 `torch 2.12.0+cpu`、`torch_cuda_build=null`、`torch.cuda.is_available()=False` 与 `nvidia-smi` 探测结果。
- 新增 `gpu_validation.log`，汇总环境探测、CPU 运行和 `cuda_requested` 运行的结构化日志。
- 新增 `benchmark_comparison.json`，沉淀 `stage2a`、`stage2c`、RAG 向量化三段链路的 CPU 与请求 CUDA 对比结果。
- 新增 CPU / `cuda_requested` 两套阶段输出物目录，分别保存 `stage2a_topics_hybrid.json`、`stage2c_similarity_edges.json`、`rag_ingestion_report.json`。

### Findings

- 当前机器可被 `nvidia-smi` 识别为 `NVIDIA GeForce RTX 5060 Laptop GPU`。
- 当前 `.venv` 中的 `torch` 仍为 CPU-only build，因此 Task 2 已完成“GPU 优先 + 稳定回退 + 证据沉淀”，但未完成真实 CUDA 打通。

### Batch Stability

- 新增 `KG_construction/infra/pipeline_runtime.py`，集中提供批量稳定性运行时能力，包括 `manifest` 初始化、结构化运行事件、失败恢复状态和按 `sha256` 的文档输出目录规划。
- `KG_construction/app.py` 现已为单文档运行写出 `manifest.json`、`run_log.json`、`recovery_state.json`、`logs/<stage>.json`、`logs/<stage>.log`，并把各 stage 的输入输出路径、状态、耗时、返回码和校验结果落盘。
- `KG_construction/app.py` 现已按 `web_data/runs/<doc_name>/<sha12>/` 隔离文档运行目录，避免不同版本同名文档互相覆盖。
- 批量执行现已支持失败隔离：单个文档失败后写入 `manifest`、恢复状态和 `web_data/global/batch_run_log.json`，同批次其他文档继续执行。
- 批量执行现已支持断点续跑：再次上传相同 `filename + sha256` 的文档时，会复用已完成 stage 的现有产物，并从首个失败或产物失效的 stage 继续执行。
- 现已为每个 stage 增加统一输入输出检查，至少校验输入文件存在、关键 JSON 产物可解析且包含预期根字段。

### Structured Outputs

- 新增文档级 `manifest.json`，记录输入 PDF、`sha256`、stage 状态、耗时、输出路径、恢复入口和运行摘要。
- 新增文档级 `run_log.json`，以 JSON 事件流方式记录开始、复用、执行完成和失败信息。
- 新增文档级 `recovery_state.json`，记录 `completed_stages`、`last_failed_stage`、`next_resume_stage` 与 `can_resume`。
- 新增全局 `KG_construction/web_data/global/batch_run_log.json`，保存每次文档级处理的结构化批量记录。

### Verified

- 已通过 `GetDiagnostics` 检查 `KG_construction/app.py` 与 `KG_construction/infra/pipeline_runtime.py`，当前无新增诊断错误。

### Added

- 新增 `KG_construction/evaluation/task4_evaluable_release.py`，作为 Task 4 的统一评测入口，固定 benchmark 样本、quality eval gold 标注、输出目录和论文表格底稿生成方式。
- 新增 `KG_construction/evaluation/task4_experiment_manifest.json`，集中声明固定 PDF 输入、gold 标注路径、运行方式和产物位置。
- 新增 `KG_construction/evaluation/annotations/task4_security_privacy_topics_gold.json`、`task4_security_privacy_prerequisites_gold.json`、`task4_security_privacy_similarity_gold.json`，用于 Task 4 小样本质量评测。
- 新增 `KG_construction/tests/test_kg_quality_eval.py`，覆盖质量评测的规范化与 `precision/recall/f1` 计算逻辑。

### Updated

- 更新 `KG_construction/evaluation/kg_benchmark.py`，支持非交互 CLI、固定 stage 子集执行、清理旧输出目录并同时导出 `kg_benchmark.json` 与 `kg_benchmark_summary.csv`。
- 更新 `KG_construction/evaluation/kg_quality_eval.py`，支持非交互 CLI、固定指标协议 `set_precision_recall_f1`，并同时导出 JSON 结果与 CSV 汇总。
- 更新 `.trae/specs/upgrade-kg-engineering-pipeline/tasks.md`，勾选完成 Task 4 及其全部子任务。

### Evaluation Outputs

- 已执行 `KG_construction/evaluation/task4_evaluable_release.py`，产物输出到 `KG_construction/web_data/benchmarks/task4_evaluable_release/paper_ready_v1`。
- 新增 `benchmark/kg_benchmark.json` 与 `benchmark/kg_benchmark_summary.csv`，固定记录 `Security and Privacy in ML.pdf` 在 `stage1-stage2c` 子链路上的 benchmark 结果。
- 新增 `quality_eval/kg_quality_eval.json` 与 `quality_eval/kg_quality_eval_summary.csv`，固定记录 Task 4 小样本 gold 标注下的 topic / prerequisite / similarity 指标结果。
- 新增 `paper_tables/benchmark_table.csv`、`paper_tables/quality_table.csv`、`paper_tables/experiment_table_draft.csv` 和 `paper_tables/task4_run_report.json`，作为论文实验表格底稿与运行摘要。
- 新增 `artifacts_index.json`，统一索引 benchmark、quality eval 与论文表格底稿路径。

### Findings

- 当前固定 benchmark 结果为 `stage1=7.214s`、`stage2a=60.916s`、`stage2b=8.221s`、`stage2c=27.501s`，`total_seconds=103.852s`。
- 当前固定小样本质量评测结果为：`topics precision=0.3333 recall=0.5 f1=0.4`，`prerequisites precision=0 recall=0 f1=0`，`similarity precision=0.5 recall=0.3333 f1=0.4`。

### Documentation

- 更新 `PRD.md`，新增 “Task 1-4 阶段状态总览” 章节，统一同步 baseline、GPU、批量稳定和可评测四块状态、当前可写结论以及对应阶段输出物目录。
- 更新 `PRD.md`，明确当前仓库的状态边界为“`KG` 主链路已进入工程版本，上层学习产品体验仍以原型版本为主”。
- 更新 `PRD.md`，明确 Task 5 只做文档与项目状态同步，不包含 Task 6 的最终验收逻辑。

### Project Status

- baseline 当前状态更新为“已完成工程版冻结并可作为回滚、复现锚点”，对应输出物为 `current_kg_baseline/` 下的 manifest、依赖快照、回滚计划、复现配方和代表样本分阶段产物。
- GPU 当前状态更新为“已完成 GPU 优先执行链路与验证留痕，但未完成真实 CUDA 运行时打通”，对应输出物为 `task2_gpu_priority/20260622_220403/` 下的设备验证、benchmark 对比和 CPU / `cuda_requested` 阶段产物。
- 批量稳定当前状态更新为“已完成工程版失败隔离、断点续跑、结构化日志和恢复状态沉淀”，对应输出物为文档级 `manifest.json`、`run_log.json`、`recovery_state.json`、`logs/` 与全局 `batch_run_log.json`。
- 可评测版本当前状态更新为“已形成固定输入、固定协议、固定输出目录的可复现实验版本”，对应输出物为 benchmark、quality eval、论文表格底稿和 `artifacts_index.json`。

### Updated

- 更新 `.trae/specs/upgrade-kg-engineering-pipeline/tasks.md`，勾选完成 Task 5 及其全部子任务。

### Final Acceptance

- 执行 Task 6 最终验收，按 `.trae/specs/upgrade-kg-engineering-pipeline/checklist.md` 逐项独立核查 baseline、GPU、批量稳定性、评测产物与文档状态。
- 更新 `.trae/specs/upgrade-kg-engineering-pipeline/checklist.md`，仅勾选已被真实证据证明通过的项，未通过项保持未勾选。
- 更新 `.trae/specs/upgrade-kg-engineering-pipeline/tasks.md`，保留 Task 6 未完成状态，并新增 Task 7 作为最终验收失败项修复任务集合。
- 更新 `PRD.md`，新增 Task 6 最终验收结论，明确哪些能力已具备、哪些能力仍不得宣称“最终通过”。

### Re-verified

- 实际重跑 `KG_construction/evaluation/task4_evaluable_release.py`，确认固定评测入口可以再次生成 `benchmark`、`quality_eval`、`paper_tables` 产物。
- 根据 `reproduction_recipe.json` 对 baseline 代表样本做复现实跑抽查，确认 `stage1` 哈希可对齐，但 `stage2a` 与 `stage2b` 哈希未对齐 baseline 配方。

### Findings

- GPU 相关结论维持不变：当前仅验证了“请求 CUDA 后稳定回退 CPU”，未形成真实 `device_info.device = cuda` 的运行时证据。
- 批量稳定性当前只有代码实现，没有足够的真实运行目录证据支撑最终验收；`web_data/runs/` 中尚未看到 `manifest.json`、`run_log.json`、`recovery_state.json`，`web_data/global/batch_run_log.json` 也不存在。
- Task 4 结果当前不满足“稳定复现”：重跑后 benchmark `total_seconds` 由 `103.852s` 变为 `130.432s`，质量评测 `similarity` 指标也发生变化，因此当前更适合作为论文实验草稿，而非正式定稿结果。

## 2026-06-21

### Added

- 新增 `PRD.md`，统一记录当前毕设项目的目标、范围、基础设施现状、优先级和已知限制。
- 新增 `.trae/specs/establish-foundation-docs-and-api-gpu-audit/checklist.md`，作为本次文档任务的验收清单。
- 将基础设施现状明确沉淀为“仓库已存在 `KG / RAG / 用户画像 / Planning Agent` 底座代码”的统一口径。
- 新增项目根目录 `.env`，用于存放 `OPENAI_API_KEY`。
- 新增 `KG_construction/env_loader.py`，统一加载项目 `.env`。
- 在 `KG_construction/app.py` 中新增 `Planning Agent` 最小界面，支持输入学习目标、选择用户画像和输出课程计划。

### Documented

- `KG` 已具备 Stage1-4 流水线、图谱导出、`app.py` 多文档运行入口和 `KGRepository` 查询抽象层。
- `RAG` 已具备 `rag_ingestion.py` 与 `rag_repository.py`，并使用 `ChromaDB` 作为本地向量库。
- 用户画像已具备 `LearnerProfile` schema、`ProfileStore` 持久化层和本地 `SQLite` 数据路径。
- `Planning Agent` 已具备 `GoalParser`、`TopicMapper`、`PathPlanner`、`TimeAllocator`、`planning_agent.py` 和 demo 入口。
- `tests/` 目录已存在 `Planning Agent` 相关测试文件。
- `evaluation/kg_benchmark.py` 与 `kg_quality_eval.py` 已作为评测与审计入口存在。
- `requirements.txt` 已包含 `openai`、`sentence-transformers`、`keybert`、`chromadb`、`streamlit` 等基础依赖。
- `test_openai.py` 已在 `.env` 自动加载方式下复验成功，返回 `API OK`。
- `app.py` 已具备最小的课程规划交互入口，后端链路已通过脚本方式验证可生成 day-by-day 计划。

### API Audit

- 明确当前项目统一配置方式为根目录 `.env` + `env_loader.py` 自动加载。
- 保留 PowerShell 环境变量作为临时覆盖方案。
- 明确可通过 `KG_construction/test_openai.py` 复验 OpenAI API 连通性。
- 按当前事实记录为“OpenAI API 已配置成功且已实测通过”。

### GPU Audit

- 机器层面已确认存在 NVIDIA GPU，`nvidia-smi` 可识别 `NVIDIA GeForce RTX 5060`。
- Python 虚拟环境当前仍是 `torch 2.12.0+cpu`，`torch.cuda.is_available()` 为 `False`。
- 明确 `infra/device_manager.py` 已提供统一 `cpu/cuda` 切换逻辑。
- 明确 `stage2a_hybrid_keybert_llm.py`、`stage2c_similarity.py` 与 `rag_repository.py` 已接入设备选择能力。
- 明确 Stage2a/Stage2c 已输出 `benchmark` 字段，可记录 `device_info`、`batch_size`、耗时。
- 明确 `evaluation/kg_benchmark.py` 已存在，但仓库尚未沉淀可证明 `cuda` 实际运行的 benchmark 结果。
- 当前正式结论为“已具备迁移入口，且机器上有 GPU，但 Python 运行时尚未切换到 CUDA”。

### Known Issues

- `Content Agent` 与 `Adaptation Agent` 仍未落地为正式代码模块。
- `Planning Agent` 已接入 `app.py`，但仍是基础版入口，尚未覆盖画像编辑、计划反馈与内容生成联动。
- CUDA 版 `torch` 安装仍在处理中，当前网络下载较慢，GPU 相关结论仍不能写成“迁移完成”。

### Maintenance Rules

- 后续每次修改后，同步更新 `PRD.md` 与 `CHANGELOG.md`。
- 文档表述必须区分“已实现”“已配置”“已验证”“已形成证据”。
