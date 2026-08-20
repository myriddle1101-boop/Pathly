# Pathly Implementation Log

## 产品目标与边界

Pathly 是面向学习者的个性化学习产品，负责 Onboarding、学习路径、每日内容、答疑、Quiz 与自适应确认。

端口 `8501` 的 Streamlit 应用是独立的开发者后台，只负责 KG、Neo4j、ChromaDB、Profile Store 和 Runtime Harness。Pathly 的实施不得向 8501 加入用户产品功能，也不得依赖 8501 页面提供 API。

## 整体进度

| 里程碑 | 状态 | 用户确认 |
|---|---|---|
| 1. FastAPI 服务骨架 | 已确认 | 2026-07-21 用户验收完成 |
| 2. Profile 与 Planning 闭环 | 待确认（返工完成） | 待确认 |
| 3. 每日内容、资源与答疑 | 待开始 | — |
| 4. Quiz、学习状态与 Adaptation | 待开始 | — |
| 5. 稳定性、部署与最终验收 | 待开始 | — |

## Milestone 1：FastAPI 服务骨架

### 状态

- 当前状态：已确认
- 开始日期：2026-07-21
- 完成日期：2026-07-21

### 目标

用单一 FastAPI 服务托管 Pathly 静态页面和系统 API，同时保持 8501 开发者后台完全独立。

### 计划改动

- 新增 Pathly FastAPI 服务。
- 新增健康检查与能力接口。
- 新增统一响应、错误和 request ID。
- 新增本地启动脚本和依赖清单。
- 增加接口及静态页面测试。
- 修复静态资源缓存导致旧脚本继续加载的问题。

### 新增接口

- `GET /api/health`
- `GET /api/capabilities`

### 数据库变更

- 无。本阶段只读检查 SQLite、KG、ChromaDB 和 Neo4j 配置状态。

### 已完成改动

- 新增 `pathly_server.py`，以 FastAPI 同时提供 Pathly 页面和 `/api` 系统接口。
- 新增统一成功响应、错误响应、`request_id` 与 `X-Request-ID` 响应头。
- 新增 Pathly 数据路径和 `DEMO_MODE` 配置入口。
- 新增 `requirements-pathly.txt`、`start_pathly.ps1` 和接口测试。
- 首页、CSS 与 JavaScript 使用独立静态路由；后端源码和 `LOG.md` 不可经 HTTP 下载。
- 对前端资源返回 `Cache-Control: no-store`，避免旧脚本缓存再次造成白屏。
- 未修改 `KG_construction/app.py` 或 8501 页面。

### 测试与结果

- Python 语法检查：通过。
- 自动测试：`5 passed`。
- 首页真实 HTTP：`200`。
- `/api/health`：`ok=true`、`service_ready=true`。
- SQLite：可读取且当前文件可写。
- 校准 KG JSON：可用。
- ChromaDB 持久化文件：可用。
- Neo4j：当前 Pathly 进程未读取到完整连接环境变量，标记为不可用；不影响页面启动。
- `/LOG.md`：`404`，私有实施日志未暴露。
- 首页缓存头：`no-store`。
- 自动浏览器控制受当前 Windows `CreateProcessWithLogonW 1385` 权限错误阻止；HTTP、静态资源和 API 已完成真实服务验收。
- 存在一个第三方 TestClient 弃用警告，不影响功能与测试结果。

### 人工验收步骤

1. 打开 `http://127.0.0.1:4173/`，确认 Pathly Onboarding 正常显示。
2. 打开 `http://127.0.0.1:4173/api/health`，确认返回统一 JSON 和各依赖状态。
3. 打开 `http://127.0.0.1:4173/api/capabilities`，确认不包含路径、密码或密钥。
4. 访问 `http://127.0.0.1:4173/LOG.md`，确认返回 404。
5. 在终端运行 `.\start_pathly.ps1`，确认一个命令可以启动服务。

### 真实模式与 fallback

- Pathly 静态 UI 不依赖 Neo4j、ChromaDB 或 OpenAI 才能打开。
- `/api/health` 会分别报告依赖状态，不因单个外部依赖不可用返回服务失败。

### 已知问题

- Neo4j 当前报告“未完整配置”；Milestone 2 需统一加载项目根 `.env` 并验证真实连接。
- 当前前端仍使用预设交互数据，将在 Milestone 2 开始替换。
- 浏览器自动化权限问题属于 Codex 本地工具环境限制，不是 Pathly 服务错误。

### 用户确认记录

- 2026-07-21：用户回复“验收完成”，Milestone 1 已确认。

### 下一步

用户确认后才进入 Milestone 2；确认前不得实现 Profile 或 Planning API。


## Milestone 2：真实 Profile 与 Planning 闭环

### 状态

- 当前状态：待确认（正式产品返工完成）
- 开始日期：2026-07-21
- 完成日期：2026-07-21

### 目标

将 Onboarding 画像真实写入 SQLite，调用现有 Planning Agent，并用真实计划动态绘制 Pathly 学习路径。

### 计划接口

- `POST /api/profiles`
- `GET /api/profiles/{user_id}`
- `PATCH /api/profiles/{user_id}`
- `POST /api/plans`
- `GET /api/plans/{plan_id}`
- `GET /api/users/{user_id}/plans`

### 当前进度

- 已新增 `pathly_backend.py`，复用现有 ProfileStore、PlanningAgent、Neo4j/JSON KG repository。
- 已新增 `pathly_learning.db`，保存计划 JSON、用户、版本、模式、来源和时间。
- 已实现 Profile 创建、读取和局部更新接口。
- 已实现 Planning 创建、读取和用户计划列表接口。
- 已实现 Neo4j → JSON KG 的真实数据回退；两者全部失败时返回可重试错误，不生成计划。
- 已将 Onboarding 接入 Profile API，将 Planning 页面接入真实 Planning API。
- 已根据真实 `days[].focus_topics` 动态生成路径节点、时间线、理由和模式标识。
- 前端 API 失败时明确显示错误和重试，不生成固定节点或伪成功路径。
- 原演示控制已在正式产品返工中完全删除。

### 数据库变更

- 复用 `learner_profiles.db` 保存真实 Pathly 画像。
- 新增 `pathly_learning.db` 与 `learning_plans` 表。
- 写入两个有明确名称的验收用户：`pathly-m2-acceptance`、`pathly-m2-low-time`。

### 测试与结果

- 全部自动测试：`9 passed`。
- JavaScript 语法检查：通过。
- 首页与 `app.js`：HTTP 200，`Cache-Control: no-store`。
- Profile HTTP 创建、读取、更新：通过。
- Planning HTTP 创建、读取和按用户列出：通过。
- 真实 Planning：`mode=live`，来源 `sqlite_profile + neo4j`，生成 7 天非空计划并持久化为版本 2。
- 30 分钟约束差异：返回 5 个 overflow topics 和明确 feasibility warning，证明时间约束参与规划。
- 强制 Planning 全部失败：抛出 `PlanningUnavailableError`，API 返回 `503 planning_unavailable`。
- 前端资源包含 Profile API 调用和 `nodesFromPlan` 动态节点转换。

### 已知问题

- 真实 Planning 首次运行可能需要加载 embedding 模型，测试中约 10–48 秒；前端会展示规划进度。
- 当前每日讲义、资源、答疑和 Quiz 仍为预设内容，属于 Milestone 3–4 范围。
- 自动浏览器点击仍受 Codex Windows 权限错误限制；HTTP、API、脚本和持久化均已真实验收。

### 人工验收步骤

1. 首次打开 Pathly，从空白画像开始填写真实信息。
2. 完成五步 Onboarding 并确认生成计划。
3. 等待 Planning 页面显示“真实规划”和数据来源。
4. 进入工作台，切换知识关系图与时间线，确认节点来自新计划。
5. 刷新页面，确认用户 ID、计划和动态节点仍保留。

### 用户确认记录

- 待用户验收 Milestone 2。

### 下一步

用户确认后才进入 Milestone 3；确认前不实现 Content、Resource 或 Chat API。
### 返工记录

- 2026-07-21：用户指出当前仍是“真实后端 + 演示外壳”，拒绝按完成验收。
- 原因：固定用户和目标、演示控制、黄金案例伪成功、浏览器固定节点回退仍存在。
- 修正标准：所有 Onboarding 输入来自真实用户；只展示真实持久化计划；KG 全部不可用时明确失败并允许重试。
### 正式产品返工最终结果

- Onboarding 从空白画像开始，不默认姓名、目标、天数或知识基础。
- 真实采集姓名、任意学习目标、目标天数、每日时间、基础、偏好和信心。
- 删除演示控制、快速跳转、固定用户、固定神经网络案例和旧 `pathly-demo` 状态。
- 删除前端固定七节点；工作台仅接受 API 返回的 `days[].focus_topics`。
- 删除后端黄金案例与 `golden_demo` 来源。
- Neo4j 正常路径重启后 HTTP 实测：`mode=live`、来源 `sqlite_profile + neo4j`、版本 3、7 天动态计划。
- Neo4j 失败时允许使用真实 JSON KG，并标记 `mode=fallback`、来源 `kg_json`。
- Neo4j 和 JSON KG 全部失败时返回 503，前端显示原因和重试按钮。
- 正式服务资源检查：演示控制=False、固定用户=False、固定节点=False。
- 自动测试：9 passed；JavaScript 语法检查通过。
## Milestone 2 Quality Repair — Stage 1

### 状态

- 当前状态：待用户确认
- 完成日期：2026-07-21
- 正式计划：`documents/milestone2_planning_quality_fix_plan.md`

### 已完成

- 增加通用术语规范化与中英文/缩写 alias。
- `RAG` 规范化为 `Retrieval-Augmented Generation`。
- 精确与 alias 精确匹配可直接接受。
- fuzzy/embedding `>= 0.78` 才能自动接受。
- `0.60–0.78` 进入 `confirmation_required`，不进入计划节点。
- `< 0.60` 进入 `unmatched_terms`。
- 包含 RAG 的复合目标必须保留 Retrieval-Augmented Generation 的语义锚点；高分的 `AI Applications`、`Training Methods` 等通用候选也会被拒绝。
- PathlyBackend 检测 unmatched/confirmation 后不保存部分计划。
- API 对不可靠目标返回 `409 planning_clarification_required`；全部后端故障仍返回 `503 planning_unavailable`。

### 测试与证据

- Topic Mapper 测试：7 passed。
- Pathly API 测试：10 passed。
- 真实用户 RAG 目标重跑：`CLARIFICATION_REQUIRED`。
- Neo4j：RAG architecture、RAG applications、RAG training methods 全部 unmatched。
- JSON KG：同样全部 unmatched。
- 未再映射到 `Latent Dynamics Models`、`AI Applications` 或 `Training Methods`。
- 本次重跑没有保存新的错误学习计划。

### Stage 2 依赖与用户操作

Stage 2 需要用户通过 8501 开发者后台触发 KG 构建，因为 KG 上传、构建和 Neo4j 同步属于开发者后台职责，不属于 Pathly。

建议首个构建文件：

- `KG_construction/resource/slides/cs224n-2026-lecture10-rag-agents.pdf`

用户确认 Stage 1 后，再提供逐步的 8501 构建操作和构建后 Neo4j 验收；在用户实际完成构建前不进入 Stage 3。
### Stage 1 补充修复：多学习路径与再次 Onboarding（2026-07-22）

#### 状态

- 当前状态：待用户确认
- 触发原因：用户在验收场景 2 时无法回到 Onboarding，并发现单用户只能看到最后一条路径。

#### 产品与数据模型修正

- 将“长期个人画像”与“单次学习目标/时间约束”在页面语义上分离。
- 工作台右上角及路径列表新增“新建学习路径”入口。
- 非首次 Onboarding 只询问：新学习目标、目标天数、每日投入。
- 姓名、已有基础、学习偏好与信心直接沿用，不重复提问；可在个人画像页修改。
- 一个 `user_id` 可拥有多个独立 `path_id`；新目标创建新路径，不覆盖旧路径。
- `version` 改为同一 `path_id` 内的版本号，供后续 Adaptation 生成 v2；不再把用户的第二个目标误称为第一条路径 v2。
- 每个计划保存 `goal_text` 与 `profile_snapshot`，保证切换旧路径时恢复当时的目标和时间约束。
- 旧 SQLite 数据库使用增量字段迁移，不要求清空已有画像或路径。
- 刷新页面后从 `GET /api/users/{user_id}/plans` 恢复各路径最新版本；路径切换区不会把同一路径的历史版本重复显示。

#### 接口调整

- `POST /api/plans` 新增可选 `path_id`：不传表示创建独立新路径；传入表示在同一路径中创建后续版本。
- `GET /api/plans/{plan_id}` 与 `GET /api/users/{user_id}/plans` 返回新增的 `path_id`、`goal_text`、`profile_snapshot`。

#### 验证结果

- JavaScript 语法：`node --check app.js` 通过。
- Pathly API 与服务测试：`10 passed`。
- Topic Mapper 阶段 1 测试：`7 passed`。
- 多路径测试覆盖：两个新目标分别为独立 `path_id` 且均为 v1；向第一条路径传入原 `path_id` 后生成 v2；三条记录均可查询。
- 更新后的 FastAPI 已重启，`/api/health` 返回 200，SQLite、KG JSON、ChromaDB 与 Neo4j 能力状态可读取。

#### 已知限制

- 当前 Windows 浏览器自动控制连接仍被系统会话权限拒绝，因此视觉点击验收需由用户按下述步骤完成；接口、脚本语法和持久化已自动验证。
- Stage 2 的 RAG KG 尚未构建，因此 RAG 目标仍应进入“需要澄清/无法可靠映射”，不应生成错误路径。

#### 人工验收步骤

1. 刷新 Pathly，右上角应看到“＋ 新建学习路径”。
2. 点击后应进入“新建学习路径”，第一问直接是新学习目标，不再询问姓名、基础、偏好和信心。
3. 右侧应显示上述个人信息为“已沿用”，只需填写目标、天数和每日分钟。
4. 用 RAG 场景验收阶段 1：应被可靠拦截，不能出现 Latent Dynamics Models、AI Applications 或 Training Methods。
5. 返回原路径后，旧路径仍存在且可以切换；刷新页面后路径列表仍保留。
6. 若用知识图谱中已存在的精确主题创建第二条可生成路径，两条路径应分别显示为 v1，而不是同一路径 v1/v2。

#### 用户确认记录

- 待用户确认 Stage 1（含本次多路径补充修复）。
### Stage 1 补充修复：规划失败后的可恢复导航（2026-07-22）

- 状态：待用户确认。
- 问题：创建新路径前错误地清空了当前 `planNodes`；当新目标无法可靠映射时，旧计划仍在但工作台渲染条件不成立，用户看起来无法返回。
- 修复：提交新目标时保留当前路径及节点，新目标失败不修改已有路径。
- 修复：错误页提供“返回修改目标”和“返回当前学习路径”两个明确入口。
- 修复：“返回当前学习路径”会根据已保存的当前计划重新生成节点，可恢复已经进入错误状态的本地页面。
- 验证：`node --check app.js` 通过；FastAPI 静态资源为 `no-store`，刷新后加载本次修改。
- 人工验收：触发 RAG 无法映射后点击“返回当前学习路径”，应回到原路径；再次进入新建路径时草稿失败不应覆盖原路径。
### Stage 1 紧急修复：刷新后白屏（2026-07-22）

- 状态：待用户确认。
- 复现背景：用户在 Planning 无法生成后刷新，页面保持空白。
- 根因 1：启动时先等待路径恢复接口，完成前没有首次渲染。
- 根因 2：旧 localStorage 可能保存首次 Onboarding 的 step 位置；切换为精简再次 Onboarding 后，该 step 超出新问题列表范围。
- 根因 3：首页长期使用固定 app.js?v=2，内嵌浏览器可能继续保留旧脚本。
- 修复：页面启动时立即 render，再在后台 hydrate 路径数据。
- 修复：localStorage JSON 损坏时自动清除；profile 使用字段级默认值合并。
- 修复：Onboarding step 越界时自动回到当前流程第一问，不再抛出运行时异常。
- 修复：静态资源版本升级到 v4，强制浏览器获取新脚本。
- 验证：JavaScript 语法检查通过；HTTP 实测首页引用 v4；v4 脚本包含立即渲染、安全状态解析、step 修复及错误返回按钮。
- 自动检查结果：AssetV4=true、ImmediateRender=true、SafeStoredState=true、SafeStep=true、ErrorReturn=true。
### Stage 1 修复：自然语言目标普遍规划失败（2026-07-22）

#### 状态

- 当前状态：待用户确认。
- 触发原因：Machine Learning、Transformer、RAG 等常见自然语言目标均返回规划失败。

#### 根因证据

- Machine Learning 被 LLM 扩展为五个课程子概念，任一子概念未匹配会否决整条计划。
- Transformer 被扩展为 architecture、self-attention、positional encoding、BERT、GPT。
- 中文 RAG 曾被错误解析为 programming languages 与 applications of programming。
- RAG alias 与 Neo4j 节点 Retrieval-Augmented Generation (RAG) 不一致。
- 前端丢弃候选详情，confirmation_required 在产品上等同于失败。
- Topic Mapper 构造时计算整张 KG embedding，精确目标也承担模型加载成本。
- 空知识基础曾被错误写入 Python。

#### 已完成修复

- Goal Parser 在 LLM 前识别 RAG、Transformer、Machine Learning、Neural Networks 与 LLM。
- 已知概念只输出一个 canonical 核心目标，不再扩展成课程大纲。
- LLM fallback 限制为一个用户明确提出的 primary concept，不再编造约束或偏好。
- 增加中文“我想学/想学”清洗规则。
- RAG canonical 对齐为 Retrieval-Augmented Generation (RAG)；Transformer 对齐为 Transformers。
- canonical 精确名称在 alias 前优先查询，避免 RAG 重复展开。
- Topic embedding 改为按需加载，并按模型和 KG 文本跨请求缓存。
- POST /api/plans 新增 confirmed_mappings。
- Planning Agent 与 Topic Mapper 支持经过 KG 校验的 user_confirmed 映射。
- 前端展示候选主题、匹配度和“选择并重新规划”。
- 空 known_topics 保持为空，不再自动添加 Python。
- 前端资源升级到 v5，FastAPI 已重启。

#### 测试结果

- Goal Parser、Topic Mapper、Planning Agent：12 passed。
- Pathly API 与静态服务：10 passed。
- JavaScript 语法检查通过。
- 在线检查：Health、AssetV5、CandidateUI、ConfirmedMappings、ErrorDetails 均为 true。
- 真实 Neo4j 强制禁用 embedding 验证：
  - Machine Learning → Machine Learning，exact_match，unmatched 为空，生成 2 个非空学习日。
  - 中文 Transformer → Transformers，exact_match，unmatched 为空，生成 3 个非空学习日。
  - 中文 RAG → Retrieval-Augmented Generation (RAG)，exact_match，unmatched 为空，生成 3 个非空学习日。

#### 已知限制

- “可以生成”已经修复，但 7/30 天计划仍可能只有 2–3 个非空学习日。这属于后续概念拆分、活动层和按天分配阶段，本次不假装完成。
- JSON KG 尚无 RAG 节点；Neo4j 可用时 RAG 正常，Neo4j 不可用时 JSON fallback 会明确报告未覆盖。
- 完全未知且低于 confirmation threshold 的目标仍会被拒绝，这是预期防错误行为。

#### 人工验收

1. 打开 http://127.0.0.1:4173/?v=5。
2. 分别新建 Machine Learning、Transformer 和 RAG 目标，应进入工作台而不是统一失败。
3. 模糊概念进入 confirmation_required 时，应显示候选与匹配度；选择后重新规划。
4. 选择“完全从零开始”后，画像不应自动出现 Python。
5. 原有路径不应被新目标或失败草稿覆盖。

#### 用户确认记录

- 待用户确认 Stage 1（包含本次自然语言目标与确认映射修复）。
## Milestone 2 Stage 4 Planning — Concept Decomposition and Daily Activity Scheduling

### 状态

- 当前状态：计划待用户确认，尚未实施功能代码。
- 计划日期：2026-07-24。
- 计划文档：documents/milestone2_stage4_activity_scheduling_plan.md。

### 计划结论

- 直接根因是现有 TimeAllocator 将一个 KG topic 作为不可拆分活动，排完 topic 后用 0 分钟 buffer 补齐剩余天数。
- 修复将概念路径与每日活动计划分离，不通过复制节点或虚构 KG 概念填充日历。
- Stage 4 分为 4.1 概念拆分、4.2 活动与偏好、4.3 按天调度、4.4 Pathly 可视化四个独立确认点。
- 新计划使用 schema version 2；旧计划保持只读兼容。
- 默认使用 paced consolidation 填满用户请求的学习周期，同时展示 honest minimum duration 和 early completion 选项。

### 实施边界

- 本次仅完成计划文档，没有修改 Planning、API、数据库或前端功能。
- 用户确认后从 Stage 4.1 开始；完成后更新本日志并停止等待确认。
## Milestone 2 Stage 4.1 — Concept Decomposition and Capacity-first Estimate

### 状态

- 当前状态：待用户确认。
- 开始与完成日期：2026-07-24。
- 本阶段完成后暂停，不进入 Stage 4.2。

### 用户确认后的逻辑修订

- 用户设定的学习天数不是固定 7/14/30，可使用当前 API 支持的任意 1–90 天。
- Planning 先估算达到目标所需总分钟，再计算 recommended_daily_minutes = ceil(total_required_minutes / requested_days)。
- 用户每日时间表示可用容量；不足时返回精确缺口，不再通过删除内容强行满足约束。
- 未来 Onboarding 顺序调整为：目标与基础 → 工作量估算 → 目标天数/截止日期 → 推荐每日时间 → 每日可用时间 → 可行性确认。
- 本阶段暂不修改 Onboarding UI，先稳定后端估算数据。

### 已完成代码

- 新增 agents/concept_expander.py。
- 从真实 ordered_topics 生成 concept_path，不创建伪 KG 节点。
- 每个概念拆成不超过 30 分钟的 concept_segment，unit_id 仍关联原 canonical concept_id。
- 根据 KG learning time、难度、pace、基础、信心、mastery 和 skill tree 估算概念分钟。
- Planning 输出升级为 schema_version=2。
- 新增 concept_path、concept_units、workload_estimate、coverage_warnings。
- feasibility 新增 total_required_minutes、recommended_daily_minutes、minimum_recommended_days、available_capacity_minutes、capacity_gap_minutes、capacity_status 和 estimate_is_final。
- 稀疏 KG 路径返回 coverage warning，不虚构缺失节点。
- 旧 days 与 focus_topics 字段继续保留，前端和旧计划保持兼容。

### 容量公式

- available_capacity_minutes = requested_days × available_daily_minutes。
- recommended_daily_minutes = ceil(total_required_minutes / requested_days)。
- minimum_recommended_days = ceil(total_required_minutes / available_daily_minutes)。
- capacity_gap_minutes = available_capacity_minutes - total_required_minutes。
- gap 小于 0 为 insufficient；至少多出一个每日容量为 excess；其余为 feasible。

### 测试结果

- Stage 4.1 容量和集成测试：5 passed。
- 完整 Planning 回归：16 passed。
- Pathly API 与持久化回归：10 passed。
- FastAPI 重启后 /api/health 返回 True。
- 1000 分钟、10 天、每天可用 60 分钟测试：推荐 100 分钟/天，容量 600，缺口 -400，minimum days 17，状态 insufficient。
- 所有概念单元均不超过 30 分钟且不超过用户每日容量；每天仅 15 分钟时，单元会继续拆分到不超过 15 分钟。分钟总和与概念估算一致。

### 真实 Neo4j 只读验证

同一个 Machine Learning 目标、每天可用 90 分钟：

- 7 天：总概念分钟 204，推荐 30 分钟/天，容量 630。
- 10 天：总概念分钟 204，推荐 21 分钟/天，容量 900。
- 30 天：总概念分钟 204，推荐 7 分钟/天，容量 2700。
- 三种天数总工作量保持 204，不再由 requested_days 反向删减内容。
- schema=2，concept count=2，concept units=8。

### 数据与接口

- 没有数据库结构变更。
- 新字段保存在现有 plan_json 中，旧记录不迁移。
- Neo4j 仍为主来源，JSON KG 仍为 fallback。

### 已知限制

- 当前 204 分钟只包含概念学习，因此明确标记 estimate_scope=concept_path_only、is_final=false。
- Stage 4.2 加入实践、复习、Quiz、反思和项目后，total_required_minutes 才成为真正的达标总时间。
- 当前 days 仍使用旧 TimeAllocator，可能包含空白日；Stage 4.3 才替换为 activity-level scheduler。
- 当前 Pathly UI 尚未展示 concept_path、workload_estimate 和容量差；Stage 4.4 处理可视化。

### 人工验收建议

1. 通过 POST /api/plans 创建新计划。
2. 检查 plan.schema_version 等于 2。
3. 检查 workload_estimate 中总分钟、推荐每日分钟、容量和缺口。
4. 用相同目标改变 target_days，总分钟应保持稳定，recommended_daily_minutes 应变化。
5. 检查 concept_units 每项不超过 30 分钟且 concept_id 来自真实 concept_path。

### 用户确认记录

- 待用户确认 Stage 4.1。
## Pathly Onboarding V2 与用户私有文档改造计划（2026-07-24）

### 状态

- 当前状态：计划待用户确认，尚未实施功能代码。
- 计划文档：`documents/pathly_onboarding_v2_personal_documents_plan.md`
- 当前 Stage 4.1 保持待确认；其概念拆分和概念级容量估算将作为新方案基础。

### 本次产品结论

- 长期 `LearnerProfile`、单次 `LearningPathContext`、计划 `ProfileSnapshot` 和动态 `LearningState` 必须分离。
- `daily_time_minutes` 是单条路径的容量约束，不再作为情感偏好字段。
- 用户上传文档属于 Pathly 学习者私有资料，不进入 8501 管理的全局 KG 构建流程。
- 私有文档映射 canonical KG，并把未可靠映射的内容保存在私有知识覆盖层；不得自动写入全局 Neo4j。
- 上传文档不是用户已经掌握内容的证据。
- Onboarding 应先确认目标、文档范围和画像，再计算最终总工作量；随后由用户输入任意目标天数，系统计算建议每日时间并进行容量协商。
- 文档作为参考来源时不重复增加概念学习时间；只有必读范围、考试范围或私有新概念才形成独立阅读工作量。

### 新阶段顺序

1. O0：契约、边界与兼容迁移。
2. O1：私有 PDF 上传与异步解析。
3. O2：文档范围、目标解释与私有知识覆盖层。
4. O3：认知—情感画像 V2 与重复 Onboarding。
5. O4：最终活动工作量模型。
6. O5：容量优先的可行性协商。
7. O6：全周期活动排程。
8. O7：Onboarding UI、资料库与路径可视化。
9. O8：端到端、隐私与降级验收。

### 现有能力复用与边界

- 可复用现有 PDF 解析、adaptive chunking、Chroma ingestion 和 KG 映射思想，但需要从 Streamlit 操作封装为 Pathly 服务。
- 8501 继续负责管理员上传权威资料并更新公共 KG/公共 RAG。
- Pathly 私有上传必须使用用户隔离的文件、元数据、chunk collection 和访问校验，不能复用公共 `kg_chunks` 作为无隔离存储。

### 本轮修改

- 新增完整 Onboarding V2 与私有文档实施计划。
- 未修改 API、数据库、Planning、前端或 8501。

### 下一步

等待用户确认新方案。确认后只实施 Stage O0，完成测试、更新本日志并暂停等待下一次确认。

## Stage O0：契约、边界与兼容迁移（2026-07-24）

### 状态

- 当前状态：待用户确认。
- 开始与完成日期：2026-07-24。
- 本阶段完成后已暂停；未开始 Stage O1 私有 PDF 上传。

### 完成内容

- 新增 `pathly_contracts.py`，定义版本化的 `LearnerProfileV2`、`LearningPathContext`、`UserDocument`、`PathDocumentLink` 和 `WorkloadEstimate`。
- 新增 `pathly_contract_store.py`，在 Pathly 自己的 SQLite 中提供增量 V2 扩展层，不重写 8501 使用的 legacy `LearnerProfile` 表。
- Profile API 现在同时保留旧扁平字段，并返回 `profile_version=2`、`basic_info`、`cognitive_traits`、`affective_defaults` 和 `inference_records`。
- 认知维度兼容映射数学基础、编程基础、抽象思维、逻辑推理和通用学习基础。
- 情感默认值包含讲解方式、示例偏好、节奏、兴趣、动机、信心、焦虑和自我调节。
- `daily_minutes` 继续作为 legacy 兼容字段，但会从 `affective_defaults` 中强制移除；新模型把它写入路径上下文的 `max_daily_minutes`。
- Profile PATCH 对 V2 嵌套字段执行增量合并，不会因只修改一项认知或偏好而清空其余项目。
- 新计划保存完整 V2 `profile_snapshot`，并建立独立 `LearningPathContext`。
- 旧计划通过新增 `path_context_json` 和 `learning_path_contexts` 自动增量回填；旧 plan JSON、版本和 path_id 不被重写或删除。
- 建立未来阶段使用的空契约表：`user_documents`、`path_document_links` 和 `workload_estimates`；本阶段没有上传、解析或写入文档。
- Pathly 继续使用自身 FastAPI/SQLite 扩展；8501 全局 KG 与公共 RAG 页面和代码未修改。

### 数据库变更

Pathly `pathly_learning.db` 增量新增：

- `learning_plans.path_context_json`
- `learner_profile_extensions`
- `learning_path_contexts`
- `user_documents`
- `path_document_links`
- `workload_estimates`

迁移只增加列和表，没有删除、清空或覆盖现有记录。

### API 调整

现有接口保持不变：

- `POST /api/profiles`
- `GET /api/profiles/{user_id}`
- `PATCH /api/profiles/{user_id}`
- `POST /api/plans`
- `GET /api/plans/{plan_id}`
- `GET /api/users/{user_id}/plans`

Profile 接口新增可选字段：

- `cognitive_traits`
- `affective_defaults`
- `inference_records`
- `profile_version`

Plan 查询响应新增 `path_context`。没有新增文档上传 API。

### 测试与结果

使用 Pathly 项目虚拟环境执行：

- Python 语法检查：通过。
- Pathly V2 契约、Profile API、计划 API 与静态服务：`13 passed`。
- Goal Parser、Planning Agent、Stage 4.1 ConceptExpander 与 TimeAllocator 回归：`10 passed`。
- 总计：`23 passed`。
- 已知第三方警告：FastAPI TestClient 提示未来改用 httpx2；不影响当前功能或结果。

真实 SQLite 只读验证：

- 现有计划：8 条。
- `path_context_json` 列存在。
- V2 profile、path context 和未来 document 契约表存在。
- 未完成 path context 回填的旧计划：0 条。
- 用户文档记录：0 条，证明本阶段没有提前写入假文档。

真实服务验证：

- 已用项目虚拟环境重启 `127.0.0.1:4173`。
- `/api/health`：`ok=true`、`service_ready=true`。
- 现有画像返回 `profile_version=2`、认知与情感结构。
- `affective_defaults` 中不存在 `daily_minutes` 或 `daily_time_minutes`。
- 抽查用户的 3 条现有计划，缺失 `path_context` 的数量为 0；示例路径恢复 30 天、每日最大容量 60 分钟。

### 人工验收步骤

1. 打开 `http://127.0.0.1:4173/`，确认现有页面和已有学习路径仍能打开。
2. 打开一个已有学习路径，确认目标、天数、节点和版本没有丢失。
3. 打开 `http://127.0.0.1:4173/api/profiles/{你的 user_id}`，确认响应包含 `profile_version: 2`、`cognitive_traits` 和 `affective_defaults`。
4. 确认 `affective_defaults` 内没有每日分钟字段；旧的顶层 `daily_minutes` 暂时保留用于兼容现有 UI。
5. 打开 `http://127.0.0.1:4173/api/users/{你的 user_id}/plans`，确认每个计划包含 `path_context`，其中有 `goal_text`、`target_days` 和 `max_daily_minutes`。
6. 新建一条学习路径，确认旧路径仍存在且新路径使用独立 `path_id`。

### 真实模式与 fallback

- 本阶段是数据契约和 SQLite 迁移，不依赖 OpenAI、Neo4j 或 ChromaDB 才能完成。
- Neo4j/JSON KG 的现有 Planning 优先级未改变。
- 旧计划和旧画像通过兼容字段读取，不需要 fallback 伪造新记录。

### 已知限制

- 现有 PlanningAgent 仍读取 legacy `LearnerProfile.daily_minutes`；这是 O5 前的兼容桥接，不代表它仍属于情感偏好。
- 旧计划的回填快照只能使用当时已保存的字段，无法补造当时未采集的 inference reason 或 confidence。
- `user_documents`、`path_document_links` 和 `workload_estimates` 当前只是空数据契约；上传、解析、权限和业务写入属于 O1/O2/O4。
- 现有前端尚未展示 V2 画像嵌套字段和路径上下文；属于 O3/O7。

### 用户确认记录

- 2026-07-24：用户确认新的 Onboarding V2 与私有文档分阶段方案，授权开始 O0。
- Stage O0 完成确认：待用户验收。

### 下一步

等待用户确认 Stage O0。确认后只进入 Stage O1：私有 PDF 上传与异步解析，完成后再次暂停等待确认。

## Stage O0 用户确认与 Stage O1 启动（2026-07-24）

- Stage O0 用户确认：已确认。
- Stage O1 当前状态：进行中。
- Stage O1 范围：私有 PDF 上传、文件校验与 hash 去重、用户隔离存储、后台解析任务、私有 chunk 索引、状态查询、失败重试和删除清理。
- 明确不包含：文档概念到 KG 映射、学习范围确认、Onboarding UI、最终工作量计算。

## Stage O1：私有 PDF 上传与异步解析（2026-07-24）

### 状态

- 当前状态：待用户确认。
- 开始与完成日期：2026-07-24。
- 本阶段完成后已暂停；未开始 Stage O2 文档概念映射。

### 完成内容

- 新增 `pathly_documents.py`，实现学习者私有 PDF 文档服务。
- 上传时校验用户 ID、`.pdf` 后缀、PDF 文件头、空文件和最大文件大小；默认限制 25 MB，可通过 `PATHLY_MAX_PDF_BYTES` 配置。
- 原始文件使用不可猜测的 user hash、随机 document ID 和固定内部文件名保存；API 不返回 `storage_key` 或服务器路径。
- 使用 SHA-256 在同一用户内去重；同一用户重复上传返回原 document，跨用户相同文件仍创建独立 document 和独立私有索引。
- 新增后台 ingestion job 状态：`queued / parsing / indexing / ready / ocr_required / failed`，并记录进度、模式、错误码和是否可重试。
- 复用现有 `stage1_adaptive_chunking` 的清洗、文档类型判断和 chunking 逻辑，并保留页码。
- 文字型 PDF 写入 SQLite 私有 chunks，并写入按用户隔离的 Chroma collection。
- O1 使用本地确定性 hash embedding，模式明确标记为 `private_chroma_local_hash`；不依赖 OpenAI 或在线模型下载。
- 扫描型/无可选择文字 PDF 明确标记为 `ocr_required / not_indexed`，没有伪装解析成功。
- 索引异常标记 `failed` 与 `retryable=1`；重试创建新 job，成功后恢复 `ready`。
- 删除时校验文档属于请求用户，删除私有 Chroma document IDs、SQLite chunks/jobs 和专属原始文件目录，并对数据库文档记录做软删除。
- 8501 的全局 KG、Neo4j 和公共 `kg_chunks` 未修改。

### 新增接口

- `POST /api/documents`
- `GET /api/users/{user_id}/documents`
- `GET /api/documents/{document_id}?user_id=...`
- `GET /api/documents/{document_id}/status?user_id=...`
- `POST /api/documents/{document_id}/retry`
- `DELETE /api/documents/{document_id}?user_id=...`

`POST /api/documents` 使用 multipart：`user_id` 表单字段与 `file` 文件字段。当前仍采用第一版匿名 user ID 边界，服务端对每次读取、状态、重试和删除校验 document owner；正式登录鉴权不属于本阶段。

### 数据库变更

Pathly `pathly_learning.db` 增量新增：

- `document_ingestion_jobs`
- `document_chunks`
- 对 document/job/chunk 查询使用的索引

沿用 O0 的 `user_documents` 契约表。没有清空或覆盖旧画像、旧路径或计划版本。

### 配置与依赖

新增/使用：

- `PATHLY_PRIVATE_DOCUMENT_DIR`
- `PATHLY_PRIVATE_CHROMA_DIR`
- `PATHLY_MAX_PDF_BYTES`
- `python-multipart`
- `pdfplumber`
- `chromadb`

`/api/health` 和 `/api/capabilities` 新增 `private_documents`，展示支持格式、大小限制和 ingestion mode，不暴露真实目录。

### 测试与结果

使用项目虚拟环境执行：

- O1 私有文档专项：6 项，通过。
- Pathly 全部契约、API 与服务回归：`19 passed`。
- Goal Parser、Planning Agent、Stage 4.1 ConceptExpander 和 TimeAllocator：`10 passed`。
- 合计：`29 passed`。

专项覆盖：

- 真实文字型 PDF 解析和私有 Chroma 写入。
- 同用户 hash 去重。
- 跨用户独立 document 与 collection。
- 用户 B 无法读取用户 A 的 document。
- 空白/扫描 PDF 进入 `ocr_required`。
- 伪 PDF 和错误扩展名被拒绝。
- 删除原始文件、SQLite chunks 和 Chroma IDs。
- 强制索引失败后标记 retryable，并在重试后成功。
- FastAPI multipart 上传、状态、列表、重复上传和删除。

已知第三方 warning：FastAPI TestClient/httpx2 迁移提示与 OpenTelemetry metadata 弃用提示；均不影响当前结果。

### 真实服务验证

- 已重启 `127.0.0.1:4173` 加载 O1。
- `/api/health`：`ok=true`、`service_ready=true`。
- `private_documents.available=true`。
- 支持类型：PDF。
- 模式：`private_chroma_local_hash`。
- OpenAPI 已注册全部 5 个唯一路径、6 个文档操作。
- 使用 HTTP 客户端上传伪 PDF 返回 `400 / invalid_document`。
- 检查后真实数据库仍为 active documents=0、jobs=0、chunks=0；没有写入测试文档。

### 人工验收步骤

本阶段尚未实现上传 UI，建议先用 FastAPI 的交互文档验收：

1. 打开 `http://127.0.0.1:4173/docs`。
2. 展开 `POST /api/documents`，点击 Try it out。
3. `user_id` 填当前 Pathly 用户 ID，选择一份文字型 PDF 后执行。
4. 复制返回的 `document_id`，调用 status 接口；后台完成后应为 `ready`，并显示 `chunk_count` 和 `private_chroma_local_hash`。
5. 用相同 user_id 再传同一文件，应返回相同 document_id 且 `duplicate=true`。
6. 用另一个 user_id 查询该 document_id，应返回 404。
7. 上传扫描型 PDF，应显示 `ocr_required`，而不是 ready。
8. 调用 DELETE 后，原 user 的文档列表不再包含该文档。
9. 回到 Pathly 首页，确认已有画像和学习路径仍然正常。

### 真实模式与 fallback

- PDF 解析和本地 hash index 不依赖 OpenAI、Neo4j 或公共 Chroma collection。
- Chroma 写入失败时文档明确进入 `failed/retryable`，不会冒充 ready。
- 扫描 PDF 当前明确进入 `ocr_required`；真正 OCR adapter 属于后续增强，不在 O1 假装完成。

### 已知限制

- 当前没有学习者上传 UI，只能通过 API；UI 属于 O7。
- 当前只正式支持文字型 PDF。
- 本地 hash embedding 用于稳定、隔离和可测试的 O1 索引，不代表最终语义检索质量；O2 会实现文档到 canonical KG 的映射，后续 Content/RAG 阶段再决定生产 embedding 策略。
- 当前匿名 user ID 是第一版身份边界，尚未建设登录、session token 或正式授权系统。
- 删除时如果 Chroma 本身不可访问，源码和 SQLite 私有文本仍优先删除；不可用索引的后台清理队列尚未实现。

### 用户确认记录

- 2026-07-24：用户确认 Stage O0，允许进入 O1。
- 2026-07-24：测试文件写入两次因平台自动审批连接中断被拒绝；用户两次明确授权重试，第三次成功。该问题属于开发工具，不是 Pathly 故障。
- Stage O1 完成确认：待用户验收。

### 下一步

等待用户确认 Stage O1。确认后只进入 Stage O2：文档范围、目标解释与私有知识覆盖层，完成后再次暂停等待确认。

## Stage O1 用户确认与 Stage O2 启动（2026-07-24）

- Stage O1 用户确认：已确认。
- Stage O2 当前状态：进行中。
- Stage O2 范围：文档页码/用途范围、目标解释、候选概念、canonical KG 映射、私有概念候选、来源模式和用户确认。
- 明确不包含：认知—情感画像问答、最终工作量、每日活动排程和 Onboarding UI。

## Stage O2：文档范围、目标解释与私有知识覆盖层（2026-07-24）

### 状态

- 当前状态：待用户确认。
- 开始与完成日期：2026-07-24。
- 本阶段完成后已暂停；未开始 Stage O3 认知—情感画像 V2 问答。

### 完成内容

- 新增 `pathly_goal_interpretation.py`，实现文档范围、目标解释、canonical KG 映射、私有概念候选和用户确认。
- 支持三种来源模式：
  - `private_plus_kg`：私有资料为主，允许 KG 补足。
  - `private_only`：只使用选定私有资料范围，缺口明确提示。
  - `kg_only`：本次解释忽略私有文档。
- 每份文档可设置用途：`core / supplementary / exam_scope / assignment / project`。
- 支持整份文档、包含/排除页码、包含/排除章节标签。
- 新解析 PDF 会把页面第一条标题线保存为 `section_path`；旧文档缺少标题元数据时，使用 chunk 开头作为可解释回退。
- `core` 与 `exam_scope` 默认视为 required，用户可明确覆盖。
- 目标解析优先复用现有 GoalParser 的已知概念规则，不为了概念提取强制调用 LLM。
- 文档候选概念来自 canonical node/alias 的明确文本证据，以及有限的英文标题短语、缩写和中文短语候选。
- 每条 `DocumentConceptEvidence` 保存 document、chunk IDs、requested term、canonical/private ID、置信度、原因和状态。
- exact/alias 映射置信度为 1.0；高于 0.78 的可靠候选自动接受；0.60–0.78 必须用户确认；低于阈值或无候选时进入 `private:*` 私有覆盖层。
- 私有概念和低置信 canonical 映射都必须由用户接受、重新映射或拒绝，才能把解释状态改为 `confirmed`。
- 未知概念只保存在当前用户私有覆盖层，不写 Neo4j，也不追加到 JSON KG。
- 返回文档对目标的覆盖情况、来源模式、KG 来源、coverage warning 和简短 reason。
- 删除文档时同步删除其 `document_concept_evidence`，避免保留已删除资料的映射证据。
- Neo4j 优先读取；连接失败后回退校准 JSON KG，并明确添加 warning。

### 新增接口

- `PATCH /api/documents/{document_id}/scope`
- `POST /api/goal-interpretations`
- `GET /api/goal-interpretations/{interpretation_id}?user_id=...`
- `POST /api/goal-interpretations/{interpretation_id}/confirm`

现有文档上传、状态、列表、重试和删除 API 保持兼容。

### 数据库变更

Pathly `pathly_learning.db` 增量新增：

- `goal_interpretations`
- `document_concept_evidence`
- 用户/文档查询索引

解释 JSON 与 evidence 分开保存：JSON 用于恢复确认页，evidence 用于审计具体映射依据。没有修改旧画像、旧路径或计划版本。

### 映射与全局 KG 边界

- O2 只调用 `node_names`、`get_topic` 和 `search_topics` 等读取方法。
- 不调用 Neo4j CREATE/MERGE/SET/DELETE。
- 不修改 JSON KG 文件。
- 8501 仍是唯一的全局 KG 构建与校准入口。
- 私有 `private:*` ID 不能成为全局 canonical node。

### 测试与结果

使用项目虚拟环境执行：

- Pathly O0/O1/O2、API、持久化和静态服务：`27 passed`。
- Goal Parser、TopicMapper、Planning Agent、Stage 4.1 ConceptExpander 和 TimeAllocator：`18 passed`。
- 合计：`45 passed`。

O2 专项覆盖：

- 只包含第 1 页时，第 2 页概念不会进入解释。
- included/excluded section 正确筛选 chunks，冲突范围被拒绝。
- canonical concept 与未知私有概念同时存在。
- `private_only` 对目标不在文档范围内给出 coverage warning。
- 低置信 canonical candidate 必须用户明确确认。
- 私有概念必须接受、映射或拒绝后才能 confirmed。
- 用户 B 无法读取用户 A 的文档或解释。
- JSON KG 在解释前后 SHA-256 完全不变。
- 真实 PDF → 私有 chunks → JSON KG 映射端到端通过。
- 删除文档后映射 evidence 同步清理。

### 真实服务与真实 KG 验证

- 已重启 `127.0.0.1:4173` 加载最终 O2。
- `/api/health`：`ok=true`、`service_ready=true`。
- OpenAPI 已注册 4 个 O2 唯一路径，并包含 `included_sections / excluded_sections`。
- 真实 Pathly 数据库中 `goal_interpretations` 与 `document_concept_evidence` 表存在。
- 验证结束后真实数据库 interpretation=0、evidence=0；没有写入测试解释。
- 真实 Neo4j 只读映射来源：`neo4j`。
- 映射前：309 个节点、794 条关系。
- 映射后：309 个节点、794 条关系。
- 结论：节点和关系数量完全不变。

### 人工验收步骤

本阶段尚未实现 Onboarding UI，建议使用 `http://127.0.0.1:4173/docs`：

1. 使用 O1 上传并等待一份文字型 PDF 状态为 ready。
2. 调用 `POST /api/goal-interpretations`。
3. 填写 `user_id`、`goal_text`、`source_mode=private_plus_kg`，并传入 document ID。
4. 可设置 included_pages/excluded_pages 或 included_sections/excluded_sections。
5. 检查返回的 `canonical_concepts`、`private_concepts`、`confirmation_required`、`coverage`、`kg_source` 和 `reason`。
6. 对低置信映射，在 confirm API 的 `confirmed_mappings` 中选择 canonical concept。
7. 对私有概念，把 private ID 放入 `accepted_private_concepts`，或把 term 放入 `rejected_terms`。
8. 所有待确认项处理后，状态应变为 `confirmed`。
9. 换另一个 user_id 读取 interpretation，应返回 404。
10. 删除原文档后，文档列表不再显示该资料，其私有映射证据同步清理。

### 真实模式与 fallback

- Neo4j 可用时显示 `kg_source=neo4j`。
- Neo4j 不可用时使用校准 JSON KG，并在 coverage warning 中说明回退。
- 映射完全失败的词不会冒充 canonical concept，而是进入私有候选或确认流程。
- 不依赖 OpenAI 才能完成 O2 的稳定解释。

### 已知限制

- 章节识别目前是 PDF 页面标题线启发式，不等于完整目录树解析；结构复杂的教材优先使用页码范围。
- 私有候选提取是确定性的轻量规则，目标是稳定和可审计，不代表最终 NLP/LLM 关键词质量。
- 私有覆盖层当前提供解释和确认数据，尚未进入最终 ActivityPlanner、工作量或每日内容；这些属于 O4 及后续阶段。
- 当前没有学习者可视化确认页面；UI 属于 O7。
- 当前仍使用匿名 user ID 作为所有权边界，正式登录鉴权不属于本阶段。
- 开发中曾出现一次 PowerShell 换行字符被写成普通文本的语法错误；在服务重启前已定位、修复并通过完整回归，未影响运行中的 4173 或用户数据。
- 真实 KG 验证第一次被 Windows 临时 SQLite 文件锁打断清理；改为忽略临时清理锁后完成验证，与 Pathly 数据或 KG 无关。

### 用户确认记录

- 2026-07-24：用户确认 Stage O1，允许进入 O2。
- Stage O2 完成确认：待用户验收。

### 下一步

等待用户确认 Stage O2。确认后只进入 Stage O3：认知—情感画像 V2 与重复 Onboarding，完成后再次暂停等待确认。

## Stage O2 用户确认与 Stage O3 启动（2026-07-24）

- Stage O2 用户确认：已确认。
- Stage O3 当前状态：进行中。
- Stage O3 范围：首次/再次问题集、情境式认知—情感推断、推断依据与置信度、目标微诊断、用户覆盖确认、草稿持久化与恢复。
- 明确不包含：最终活动工作量、容量协商、每日排程和 Onboarding UI。
## Stage O3：认知—情感画像 V2 与重复 Onboarding（2026-07-24）

### 状态

- 当前状态：待用户确认。
- 开始与完成日期：2026-07-24。
- Stage O2 用户确认已记录；O3 完成后已暂停，尚未进入 O4。

### 完成内容

- 新增 `pathly_onboarding.py`，将 Onboarding 从一次性前端问答拆成可持久化、可恢复、可审计的服务流程。
- 首次 Onboarding 使用 12 个情境式问题，覆盖数学、编程、抽象与逻辑基础，既往学习体验，讲解与案例偏好，节奏，以及动机、信心、焦虑和自我调节。
- 再次 Onboarding 使用 6 个增量问题，只询问资料是否变化、当前目标熟悉度、本路径风格覆盖，以及当前动机、信心和焦虑；已有稳定画像默认复用。
- 自动根据该用户是否已有画像决定 `first_time` 或 `repeat`，不再假设一个用户只能做一次 Onboarding。
- 每个推断字段均保存 `value`、`confidence`、`reason`、`evidence_source` 和 `confirmed`，包括学习节奏偏好。
- 支持用户在确认前覆盖认知、稳定偏好与情感字段；用户覆盖项的置信度固定为 1.0，来源标记为 `user_override`。
- 目标熟悉度作为当前路径的 `target_mastery` 与 `target_mastery_evidence` 保存，不写入全局 `mastery_vector`，避免一次新目标问答污染长期能力画像。
- 支持关联已确认的 O2 `goal_interpretation_id`。系统校验解释属于同一用户且状态为 `confirmed`，再把 canonical/private 目标概念带入当前路径上下文。
- 首次确认后写入真实 `learner_profiles.db`，同时保留认知—情感 V2 字段，并桥接现有 Planning 所需的兼容字段。
- 草稿支持自动保存答案、当前步骤、画像预览、路径上下文预览、恢复、列表和软删除；跨用户读取或修改返回 404。
- 再次 Onboarding 可标记 `profile_changed=yes` 并提交稳定画像修正；未声明变化时沿用原稳定画像。

### 新增接口

- `POST /api/onboarding-drafts`
- `GET /api/onboarding-drafts/{draft_id}?user_id=...`
- `GET /api/users/{user_id}/onboarding-drafts`
- `PATCH /api/onboarding-drafts/{draft_id}`
- `POST /api/onboarding-drafts/{draft_id}/confirm-profile`
- `DELETE /api/onboarding-drafts/{draft_id}?user_id=...`

所有接口继续使用统一 `ok / data / error / request_id` 响应结构。

### 数据库变更

Pathly `pathly_learning.db` 增量新增：

- `onboarding_drafts`：`draft_id`、`user_id`、`onboarding_type`、`status`、`current_step`、`draft_json`、创建/更新时间与软删除时间。
- 用户与更新时间复合索引，用于恢复最近的 Onboarding 草稿。

画像确认继续写入现有 `learner_profiles.db`；未更改旧计划版本，也未写入或修改 Neo4j/JSON KG。

### 测试命令与结果

使用项目虚拟环境实际执行：

- O3 专项：`7 passed`。
- Pathly O0–O3、文档、目标解释、Profile、Planning、API 与静态服务完整回归：`34 passed`。
- Goal Parser、TopicMapper、TopicMapper 置信度、PathPlanner、Planning Agent、ConceptExpander 与 TimeAllocator 回归：`20 passed`。
- 本次完整验证合计：`54 passed`。
- Python 语法检查：通过。

专项覆盖首次/再次问题集、缺失答案校验、情境推断、推断理由与置信度、用户覆盖、稳定画像复用、目标微诊断隔离、O2 已确认解释接入、跨用户隔离、草稿恢复/删除、画像持久化，以及不同基础对 ConceptExpander 工作量估算的影响。

已知第三方 warning：FastAPI TestClient/httpx2 迁移提示与 OpenTelemetry metadata 弃用提示；均不影响当前结果。

### 真实服务验证

- 已重启 `127.0.0.1:4173` 并加载 O3。
- `/api/health`：`ok=true`、`data.status=ok`。
- 首页返回 HTTP 200 且包含 Pathly 页面内容。
- OpenAPI 中 6 个 O3 操作对应的 4 类路径均已注册。
- 真实 `pathly_learning.db` 中 `onboarding_drafts` 表存在。
- 验证结束时真实库草稿数为 0、既有计划数为 8；没有为了验收写入虚构用户或草稿。
- 现有前端仍可访问；O3 本身尚未改造可视化 Onboarding UI，该项按阶段计划属于 O7。

### 真实模式与 fallback

- O3 的问题选择、规则推断、置信度、草稿恢复和画像写入不依赖 OpenAI、Neo4j 或 ChromaDB，外部依赖不可用时仍可完成。
- 若关联 O2 目标解释，只接受已经确认且属于当前用户的解释，未确认解释会被拒绝，不会静默回退成已确认目标。
- O3 没有把启发式推断冒充心理测量结果；所有推断都带理由、来源和可修改入口。

### 已知限制

- 当前置信度是可解释的产品启发式分值，不是经过心理测量学验证的统计置信度。
- 再次 Onboarding 的目标熟悉度目前是一个粗粒度回答，暂时应用于该目标的全部目标概念；后续可用逐概念诊断进一步细化。
- 为兼容当前 Planning，首次画像仍生成 7 天、每天 75 分钟的隐藏占位值；O5 将正式实现“先估算总工作量，再协商期限与每日容量”，当前 UI 不应把占位值当作最终承诺。
- 本阶段不包含 Activity 工作量、总时长估算、容量协商、每日排程或 UI；这些分别属于 O4、O5、O6/O7。
- 当前仍以匿名 user ID 作为所有权边界，尚未建立正式登录鉴权。

### 人工验收步骤

当前阶段可通过 `http://127.0.0.1:4173/docs` 验收：

1. 调用 `POST /api/onboarding-drafts`，传入一个尚无画像的 `user_id`，应返回 `onboarding_type=first_time` 和 12 个问题。
2. 通过 PATCH 分次保存答案与 `current_step`，刷新后用 GET 读取同一草稿，答案和步骤应保留。
3. 补齐 12 个答案后查看返回的 `profile_preview`：推断字段应显示 value、confidence、reason、evidence_source 和 confirmed。
4. 调用 `confirm-profile`，可传认知或偏好覆盖；响应与随后 Profile 查询中，覆盖值应存在且来源为 `user_override`。
5. 对同一用户再创建草稿，应返回 `onboarding_type=repeat` 和 6 个问题，并在 `profile_snapshot` 中复用稳定画像。
6. 再次流程填写 `target_familiarity` 后确认，结果应出现在当前 `path_context_preview.target_mastery`，而不是全局 `mastery_vector`。
7. 若提供 `goal_interpretation_id`，必须先在 O2 确认；确认后应看到 canonical/private 目标概念进入路径上下文。
8. 用另一个 `user_id` 读取或修改该草稿，应返回 404。
9. 删除未完成草稿后，用户草稿列表不再显示它。

### 用户确认记录

- 2026-07-24：用户确认 Stage O2，允许进入 O3。
- Stage O3 完成确认：待用户验收。

### 下一步

等待用户确认 Stage O3。确认后只进入 Stage O4：把目标与知识节点展开为可估算的学习活动和总工作量；不提前进入期限/每日容量协商、排程或 UI。## Stage O3 用户确认与 Stage O4 启动（2026-07-24）

- Stage O3 用户确认：已确认。
- Stage O4 按既定范围启动并完成；未提前进入 O5 容量协商、O6 排程或 O7 UI。

## Stage O4：最终活动工作量模型（2026-07-24）

### 状态

- 当前状态：待用户确认。
- 开始与完成日期：2026-07-24。
- 本阶段完成后已暂停；尚未进入 Stage O5。

### 完成内容

- 新增 `pathly_workload.py`，实现独立 `ActivityPlanner`、`WorkloadService` 与 `WorkloadStore`。
- 承接现有 ConceptExpander 的 canonical 概念路径和 KG `estimated_learning_time`，在不创建正式 plan 的前提下生成最终活动工作量。
- 活动层包含讲解、示例、练习、代码/应用、复习、Quiz、项目和反思；所有活动记录 concept、分钟、来源和 reason。
- 根据长期画像、本路径偏好覆盖、编程基础、当前信心/焦虑和自我调节调整示例、练习、代码、复习、Quiz、项目和反思比例。
- 偏好只改变活动结构与总时间，不改变 canonical 概念路径。
- 最终估算完全不接受 requested days 或 daily capacity；先计算达到目标所需的总分钟，O5 才进行天数和每日容量协商。
- `is_final=true` 只在至少存在一个确认概念且完整活动类别通过校验后返回；无确认概念会明确拒绝。
- 用户指定的必读文档按确认页码/章节过滤私有 chunks，基于去重后的 word count、画像相关阅读速度和来源页码生成阅读活动。
- 参考资料保留为内容/RAG 来源，但不增加独立阅读时间。
- 必读材料与 concept explanation 重叠时，先用阅读时间替换重复讲解分钟；只有超过可替换部分才增加净总时间。
- 跨文档/重复范围按 chunk ID 去重，并返回 `deduplication` 明细与节省分钟。
- 私有概念或 KG 不可用时使用透明模板估算，明确记录 source、confidence、reason 和 warning，不冒充 KG 元数据。
- Neo4j 优先、校准 JSON KG 回退；两者都失败时使用目标概念模板，仍可返回明确标记的完整活动估算。
- 支持可选模型活动生成器；模型失败或返回不完整 schema 时使用 `fallback_template`，保留 fallback reason 与 warning。当前正式服务默认采用确定性模板，不假装调用实时模型。
- O4 估算写回 Onboarding draft 的摘要和 estimate ID，但保持 `profile_confirmed` 状态语义，不创建 plan v1。
- `WorkloadEstimate` 契约升级到 schema v2，补充 example、code、activity total、结构化来源、生成模式和完整估算范围。
- `/api/capabilities` 新增 `workload_estimation`，公开完整活动范围、天数解耦和文档去重能力。

### 新增接口

- `POST /api/onboarding-drafts/{draft_id}/workload-estimates`
- `GET /api/onboarding-drafts/{draft_id}/workload-estimate?user_id=...`
- `GET /api/workload-estimates/{estimate_id}?user_id=...`

所有接口继续使用统一 `ok / data / error / request_id` 响应；估算读取执行 user ownership 检查。

### 数据结构与数据库

复用 O0 已创建的 `workload_estimates` 表，并新增 path + updated_at 索引用于读取草稿的最新估算。估算 JSON 现在包含：

- O3 draft、user 和预路径 `path_id=onboarding:{draft_id}`；
- concept path、concept units 和 KG source；
- 九类分钟构成、总分钟、活动列表和 activity mix；
- estimate sources、confidence、coverage warnings；
- document source refs、scope 和 deduplication；
- generation mode、fallback reason、`estimate_is_final/is_final`。

未修改旧 plan、Neo4j、JSON KG 或 8501 代码；O5 最终确认前仍不创建正式路径。

### 测试命令与结果

使用项目虚拟环境实际执行：

- O4 专项：`8 passed`。
- Pathly O0–O4、文档、目标解释、Onboarding、Profile、Planning、API 与静态服务完整回归：`42 passed`。
- Goal Parser、TopicMapper、TopicMapper 置信度、PathPlanner、Planning Agent、ConceptExpander 与 TimeAllocator：`20 passed`。
- 本阶段完整验证合计：`62 passed`。
- O4 接入后的额外服务子集复核：`13 passed`。
- Python 语法检查：通过。

O4 专项覆盖：

- 完整活动类别和总分钟求和；
- 没有确认概念时拒绝 final；
- 10 天与 30 天不改变达标总分钟；
- theory 与 project 偏好改变活动结构和总时间但不改变概念路径；
- reference 文档不加时；
- required 文档计时、页码引用和重叠去重；
- 模型失败后明确使用完整模板 fallback；
- SQLite 持久化、最新估算恢复和跨用户隔离；
- profile 未确认时 API 拒绝估算。

已知第三方 warning：FastAPI TestClient/httpx2 迁移提示与 OpenTelemetry metadata 弃用提示；均不影响当前结果。

### 真实 KG 与服务验证

- 使用真实已有匿名画像和真实 Neo4j 进行只读 O4 概念展开。
- `Neural Networks` 被展开为 2 个 source-grounded 概念节点，概念基础工作量为 204 分钟，`kg_source=neo4j`，无 coverage warning。
- 该过程只调用 KG 读取与路径规划方法，不执行 CREATE/MERGE/SET/DELETE。
- 已重启 `127.0.0.1:4173` 加载最终 O4。
- `/api/health`：`ok=true`、`data.status=ok`。
- 首页返回 HTTP 200。
- OpenAPI 中 3 个 O4 路径全部存在。
- `/api/capabilities`：`workload_estimation.available=true`、`duration_independent=true`、`document_deduplication=true`。
- 真实库检查：workload estimates=0、onboarding drafts=0、既有 plans=8；没有为了验收写入虚构草稿、估算或计划。

### 真实模式与 fallback

- `kg_source=neo4j` 时整体 mode 为 live；Neo4j 失败后校准 JSON KG 返回 fallback。
- canonical/private template 会在 estimate sources 中分别标记 `kg_metadata` 或 `private_concept_template`，并带置信度与理由。
- 当前活动生成主路径是可复现的 deterministic template；若未来接入模型且调用失败，现有 schema 校验会切换为 `fallback_template`。
- 文档不可用或已删除时不会静默忽略必读范围，而是拒绝最终估算并要求用户修正资料范围。

### 已知限制

- 当前活动时间系数和阅读速度是透明、可测试的产品启发式规则，尚未由真实学习行为数据校准。
- 私有概念缺少 KG 时间元数据时默认从 90 分钟模板出发，再依据基础和目标 mastery 调整；来源和低置信度会明确显示。
- 当前服务未接入实时 LLM 活动生成器，默认 deterministic template；已完成模型 adapter 的 schema/fallback 边界。
- 技术型目标会生成代码/应用与项目活动。面向完全非技术领域时，后续可把 `code` 细分为领域应用活动类型，而不是在本阶段扩展 ontology。
- 文档阅读估算基于解析后的 word count；图表密集、公式密集或扫描资料需要后续内容复杂度/OCR 校准。
- 本阶段没有采集用户天数、截止日期或每日最大可用时间，也不返回推荐每日分钟；这些严格属于 O5。
- 本阶段没有把活动排到具体天；活动级排程属于 O6。
- 当前前端尚未展示工作量构成；Onboarding Workspace UI 属于 O7。

### 人工验收步骤

当前可通过 `http://127.0.0.1:4173/docs` 验收：

1. 准备一个 O3 状态为 `profile_confirmed` 的 Onboarding draft。
2. 调用 `POST /api/onboarding-drafts/{draft_id}/workload-estimates`，body 只需 `user_id`；接口不询问或接受天数。
3. 检查 `estimate_is_final=true`、`estimate_scope=complete_activity_workload`，并确认 total 是所有活动分钟之和。
4. 检查 activities 至少包含 explanation、example、practice、code、review、quiz、project 和 reflection，每项均有 reason/source。
5. 检查 estimate_sources、estimate_confidence、kg_source、mode 和 coverage_warnings。
6. 用 GET estimate 接口刷新恢复结果；换另一个 user_id 应返回 404。
7. 若 O2 文档仅是 supplementary/reference，required_reading_minutes 应为 0，但 estimate_sources 仍有文档来源。
8. 若把同一确认范围设为 required，应该生成 required_reading 活动、文档页码/chunk 引用和 deduplication 明细。
9. 创建相同目标/基础但不同 activity_style 的两个已确认 draft，概念路径应相同，活动 mix 与 total 应不同并有 reason。
10. 不要在 O4 期待 recommended daily minutes；O5 才会用本阶段 total 计算任意天数的每日建议和容量缺口。

### 用户确认记录

- 2026-07-24：用户确认 Stage O3，允许进入 O4。
- Stage O4 完成确认：待用户验收。

### 下一步

等待用户确认 Stage O4。确认后只进入 Stage O5：支持任意目标天数/截止日期，先读取本阶段最终总分钟，再计算推荐每日时间、最大可用容量、精确缺口与可行性协商；不会提前进行每日活动排程或 UI。## Stage O4 用户确认与连续实施授权（2026-07-24）

- 用户确认 O4，并授权从 O5 连续实施到 O8；中间不再等待人工确认。
- 每阶段仍必须通过专项、完整回归、真实服务与 fallback 质量门，并在本日志记录“内部验收通过”后才能进入下一阶段。

## Stage O5：容量优先的可行性协商（2026-07-24）

### 内部验收结论

- 状态：内部验收通过（已获连续实施授权）。
- 实现任意 1–3650 天或截止日期、两步容量采集、四级可行性、精确差额、策略选择、独立范围缩减草案与显式确认。
- 1000 分钟/10 天得到 100 分钟每天；每天最多 60 分钟时缺口 400 分钟、至少 17 天。
- 范围缩减保护先修关系、保留必读材料、拒绝时不改变原目标；接受后生成明确部分目标。
- 只有可行且明确选择策略后才创建 plan v1；v1 days 为空并标记等待 O6，重复确认幂等。
- 新增 feasibility_decisions 表、所有权索引及 4 个 O5 API；capabilities 已公开容量协商能力。
- O5 专项：9 passed；Pathly 全量：51 passed；KG/Planning：20 passed；合计 71 passed。
- 真实 4173：health ok、capacity_negotiation available、O5 路由全部注册。
- 启动验收脚本曾因新服务已实际占用 4173 而误报等待失败；前台诊断确认是端口已成功监听，最终健康与路由复核通过，不是产品故障。
- 已知限制：O5 不排每日活动；正式时间线由 O6 生成。

### 下一阶段

自动进入 O6：活动级全周期排程与 plan v2。## Stage O6：全周期活动排程（2026-07-25）

### 内部验收结论

- 状态：内部验收通过（已获连续实施授权）。
- 新增确定性 ActivityScheduler 和 ScheduleService；按先修与活动优先级排程，拆分跨日活动，复习使用周期内可实现的 +1/+3/+7/+14 间隔。
- 每日不超过确认容量；返回日只包含实际活动，无 0 分钟 padding。
- paced_consolidation 使用盈余容量生成 optional 活动；容量或间隔冲突保存在 unscheduled_activities，不静默丢失。
- O5 plan v1 保持只读，O6 为同一路径生成 v2；input hash 保证重复请求幂等。
- 新增 POST/GET /api/plans/{plan_id}/schedule，capabilities 增加 activity_scheduling。
- O6 专项：9 passed；Pathly 全量：60 passed。KG/Planning 已在 O5 质量门通过，O6 未修改 KG/Planning。
- 真实 4173：health ok；schedule route、deterministic、preserves_unscheduled 全部为 true。
- 首次重启检查因依赖初始化时间超过短等待窗口而未连接；用户明确授权重试后，以 40 秒窗口验收通过。
- 已知限制：时间线当前使用 Day N，不绑定具体日历日期；日期展示可由确认 deadline 推导，UI 在 O7 展示。

### 下一阶段

自动进入 O7：真实 Onboarding Workspace、资料库、工作量/容量与路径时间线 UI。
## 2026-07-25 O6 真实服务验收重试（用户再次授权）

- 状态：内部验收通过（已获连续实施授权）
- 首次重试结果：失败。误用了系统 Python，测试收集时报 `ModuleNotFoundError: fastapi`；该结果属于执行环境选择错误，不是排程逻辑失败。
- 修正：切换到 Pathly 启动脚本使用的 `KG_construction\.venv\Scripts\python.exe`。
- 专项验证：
  - `python -m py_compile pathly_scheduler.py pathly_server.py`：通过。
  - `python -m pytest tests/test_pathly_scheduler.py -q`：`9 passed`，1 条 Starlette/httpx 弃用警告。
- 真实服务验证：
  - 服务：`http://127.0.0.1:4173`，健康检查通过，进程监听正常。
  - 在实际计划库中创建隔离验收用户 `o6-real-acceptance-20260725` 的 plan v1，并通过真实 HTTP 接口调用排程。
  - 首次 `POST /api/plans/{plan_id}/schedule`：成功生成 plan v2。
  - 重复 POST：返回同一 v2，幂等性通过。
  - `GET /api/plans/{plan_id}/schedule`：恢复同一 v2。
  - 路径版本数：2（v1 保留、v2 新增）。
  - 实际排程日：5；每日 1–60 分钟，超容量或 0 分钟日为 0。
  - 未能满足复习间隔的活动：2 条，均保留在 `unscheduled_activities`，未静默丢弃。
  - 返回模式：`fallback`，界面和接口未冒充 `live`。
- 结论：O6 专项测试、真实进程、真实 HTTP、版本保留、幂等性、容量约束和未排程保留均通过，可以进入 O7。
# Stage O7：真实 Onboarding UI 与路径可视化（2026-07-25）

## 状态

- 内部代码与自动化验收通过（已获连续实施授权）。
- 自动浏览器视觉验收受 Codex Windows 浏览器工具限制：`CreateProcessWithLogonW failed: 1385`。未虚假记录为浏览器通过，保留最终人工视觉验收步骤。

## 修改内容

- 正式首页切换为真实 O1–O6 Onboarding Workspace；不再加载固定七天、今日学习、Quiz、Adaptation 或演示控制数据。
- 私有资料可上传、轮询、重试、删除；明确显示不会进入公共 KG。
- 首次画像使用完整问题；同一用户再次建路径使用增量问题。
- 目标映射不再自动接受：新增公共 KG 候选与私有概念显式确认界面。
- 工作量先于天数显示；支持 1–3650 天与每日容量输入。
- 新增独立范围缩减草案、原/新工作量对比、移除/保留概念、必读资料保留提示及接受/拒绝操作。
- Dashboard 支持多路径、概念来源、路径版本、知识地图与活动时间线；窄屏隐藏复杂地图并保留时间线。
- 修复真实服务发现的白屏根因：`index.html` 已引用 `pathly-app.js`，但 FastAPI 未提供该静态路由；现已增加 `/pathly-app.js` 与 `/pathly-ui.css`，并加入回归测试。

## 测试与实际结果

- `node --check pathly-app.js`：通过。
- O7 前端与服务专项：10 passed。
- 最终 Pathly 全量：75 passed，2 条第三方弃用警告。
- 真实 HTTP：首页 200、`pathly-app.js?v=8` 200、`pathly-ui.css?v=8` 200。
- 真实首次 Onboarding：12 个画像问题。
- 真实再次 Onboarding：6 个增量问题，`onboarding_type=repeat`。

## 人工视觉验收

1. 打开 `http://127.0.0.1:4173/`，确认非白屏且没有“演示控制”。
2. 点击“新建路径”，确认目标、资料来源和 PDF 上传可操作。
3. 使用私有资料时确认出现目标映射确认页，而不是自动进入画像。
4. 完成容量不足场景，确认“缩小范围”出现独立前后对比并可拒绝恢复。
5. Dashboard 切换知识地图/时间线；缩窄窗口后确认纵向时间线仍可用。

# Stage O8：隐私、安全、降级与最终验收（2026-07-25）

## 状态

- 实现与内部自动验收通过（已获连续实施授权）。
- 待用户整体验收。
- 环境限制：本机未安装 Docker，故 Dockerfile 已通过静态契约测试，但未宣称镜像实际构建通过；自动浏览器视觉验收同样受上述 Windows 工具限制。

## 安全与数据架构

- 新增服务端匿名会话表：只保存 token hash、匿名 user ID、创建/过期/撤销时间；原始 token 仅存在 HttpOnly Cookie。
- 正式服务强制会话校验；生产配置使用 Secure Cookie，SameSite=Lax。
- 写操作校验同源；JSON、查询参数和用户路径中的 `user_id` 必须与会话一致。
- 安全测试首次发现 `/api/profiles/{user_id}` 未纳入路径所有权判断，攻击测试得到 200；修复后跨会话访问真实返回 403。
- 文档上传校验扩展名、MIME、PDF magic bytes、25 MB、500 页、5000 chunks、120 秒解析限制与安全存储路径。
- 扫描件进入 `ocr_required`；损坏、超限、解析或索引失败进入可恢复状态。
- 结构化日志记录 request ID、路由、耗时、状态和哈希 user ID，不记录画像、PDF 或聊天正文；最终真实进程已输出该日志。
- 生产镜像只复制 Pathly 运行代码、Planning/KG 运行时代码与公共 KG，不复制 `.env`、SQLite、私有文档或 Chroma 数据。
- 新增 `.env.example`、修正 Dockerfile、运行说明与隐私/恢复说明。

## 专项与降级验证

- 会话与私有文档安全专项：11 passed。
- 跨会话真实 HTTP：无 Cookie 401；会话创建 201；自己资源 200；另一会话画像 403；跨域写入 403。
- Cookie：HttpOnly=true、SameSite=Lax；本地 HTTP 验收 Secure=false，生产模板 Secure=true。
- Neo4j 故障注入：成功回退 JSON KG，返回 mode=fallback、sources=sqlite_profile+kg_json。
- 模型不可用：已有测试验证 `fallback_template` 与明确 fallback reason。
- Chroma 索引失败：已有测试验证失败可重试，恢复后 ready。
- PDF：扫描、伪造 magic、MIME 不符、页数/分块超限均有测试。
- 删除文档：文件、chunks 与私有索引清理测试通过，不影响公共 KG。
- 原 KG/Planning 回归：6 passed。
- Docker 静态部署契约：3 passed；实际 build 未执行（环境无 Docker）。

## 最终真实端到端结果

- 匿名安全会话：创建成功。
- 私有 PDF：ready，1 chunk。
- 目标解释：显式确认后 confirmed。
- 首次画像：12 题完成；第二次画像：6 个增量问题。
- 完整工作量：667 分钟。
- 容量：13 天 × 180 分钟，comfortable，用户选择 proceed。
- plan v1：version=1、days=[]。
- plan v2：version=2、5 个有效学习日。
- GET 恢复：返回同一个 v2；用户路径列表保留 v1/v2 两版。
- 本次真实链路 mode=live；O6 独立验收的 fallback 数据保持明确标记。
- 最终服务 PID 18440，4173 ready，`DEMO_MODE=false`，session required=true，新版静态资源 200。

## 已知限制

- 浏览器工具无法在当前 Codex Windows 沙箱启动，因此桌面/窄屏视觉质量需要用户按 O7 步骤人工确认。
- 本机没有 Docker，镜像实际构建需在安装 Docker 的环境执行运行说明中的命令。
- Starlette TestClient/httpx 与 OpenTelemetry 各有 1 条第三方弃用警告，不影响当前功能。
- O7 按规划隐藏了尚未真实实现的每日讲义、Chat、Quiz 与 Adaptation；这些功能没有以静态假数据冒充完成。

## 总结论

O5、O6、O7、O8 的代码、数据库迁移、专项测试、完整回归、真实服务安全检查、fallback 注入与 O1–O6 真实端到端链路均已完成。当前进入用户整体验收；自动浏览器视觉与 Docker 实际构建是两项明确的环境受限验收，不记录为已通过。
# Hotfix：Onboarding `null.value` 崩溃（2026-07-25）

## 问题与根因

- 用户在进入 Onboarding 时看到：`Cannot read properties of null (reading 'value')`。
- 根因是通用 `act()` 在执行回调前调用 `render()`，导致当前 DOM 被替换；随后 `beginOnboarding()` 再读取 `#goal.value` 时，输入节点在部分恢复/异步状态下已不存在。
- 同类风险同时存在于天数和每日时长输入；目标映射复选框也可能因预先重渲染而恢复默认勾选。

## 修复

- `act()` 不再在回调执行前重建 DOM；改为添加/移除 busy class，并只在操作完成后渲染。
- `beginOnboarding()` 在进入异步操作前读取并校验目标输入；输入节点缺失时返回可恢复提示，不再抛 JavaScript TypeError。
- `createDecision()` 在异步操作前读取、校验天数和每日分钟数。
- 前端资源版本从 v8 提升至 v9，确保浏览器不继续运行旧脚本。
- 新增 DOM 读取顺序回归测试。

## 验证

- `node --check pathly-app.js`：通过。
- 前端/服务专项：11 passed。
- Pathly 全量回归：76 passed，2 条第三方弃用警告。
- 真实 4173：主页 200、v9 脚本 200、匿名会话 201。
- 真实脚本内容确认：存在 `goalInput` 空值保护；不存在 `state.busy=true; state.error=null; render()` 旧逻辑。
- 服务 PID：47948。
- 自动浏览器控制仍被 Windows 沙箱 `CreateProcessWithLogonW failed: 1385` 阻止，未记录为浏览器自动验收通过。

## 用户验收

刷新 `http://127.0.0.1:4173/`，确认地址加载 `pathly-app.js?v=9`，填写目标后点击“继续建立画像”。页面应进入画像问题，不再出现 `null.value`。
# UI language migration：English-only Pathly（2026-07-25）

## Scope

- Pathly learner-facing product only; the separate 8501 KG administration workspace was not changed.
- Converted navigation, onboarding, document library, learner profile, workload, feasibility, scope review, dashboard, loading, error, recovery and confirmation copy to English.
- Converted all first-time and repeat onboarding questions and option labels returned by the API to English.
- Changed HTML language metadata to `lang="en"` and the English product title/description.
- Upgraded static assets from v9 to v10 to prevent stale localized scripts.

## Verification

- English-only regression now checks `index.html`, `pathly-app.js` and `pathly_onboarding.py` for CJK characters.
- Frontend and onboarding focused suite: 17 passed.
- Full Pathly regression: 77 passed, with 2 existing third-party deprecation warnings.
- Real 4173 results: homepage 200, v10 JavaScript 200, anonymous session and onboarding draft 201.
- Real homepage: `lang=en`, no CJK characters.
- Real JavaScript: no CJK characters.
- Real first-time onboarding response: 12 questions, no CJK characters.
- First live question: `Which statement best describes you when working with formulas and mathematical derivations?`
- Service PID: 2416.

## Known environment limit

- Automated visual browser control was attempted again and blocked by the Codex Windows sandbox with `CreateProcessWithLogonW failed: 1385`; this is not recorded as a visual pass.
# Hotfix：browser bilingual translation overlay（2026-07-25）

- User screenshot showed English UI followed by inserted Chinese translations, including brand/navigation labels and repeated private-concept descriptions.
- Root cause: a browser translation extension/bilingual mode, not character encoding and not Pathly API data. The live v10 HTML, JavaScript and onboarding API had already been verified to contain no CJK characters.
- Added `<html lang="en" translate="no" class="notranslate">` and `<meta name="google" content="notranslate" />`.
- Frontend regression: 7 passed.
- Live 4173: status 200; all three no-translate markers present; HTML contains no CJK characters.
- If a browser extension forces bilingual mode, the user must also select “show original” or disable translation for `127.0.0.1` in that extension.
# Hotfix：private concept hash shown as label（2026-07-25）

## Root cause

- Values such as `private:2d4dc2611a78a45e` are stable internal private-concept IDs, not corrupted text.
- The API already retained the extracted `requested_term`, but the UI looked only for `label` and `name`; because neither existed, it rendered `private_concept_id` as the title.

## Fix

- Private concept API objects now include `display_name=requested_term` at creation and confirmation.
- Stored legacy interpretations are enriched on read with `display_name` from `requested_term`.
- Frontend display order is now `display_name → requested_term → label → name → Unrecognized private concept`; raw IDs are no longer normal display labels.
- Static asset version upgraded from v10 to v11.

## Verification

- Related unit/integration suite: 15 passed.
- Full Pathly regression: 78 passed, 2 existing third-party deprecation warnings.
- Real 4173 private-only document test: PDF ready; 2 private concepts; all had display names; zero display names equaled their hash IDs.
- Live sample labels: `Quantum Foo Engine`, `Latent Widget Protocol`.
- Internal IDs remain available only in data for stable ownership and references.
# Hotfix：goal text cleared by document checkbox（2026-07-25）

## Root cause

- Goal text existed only in the textarea DOM until onboarding submission.
- Selecting or clearing a document called `toggleDoc()` and re-rendered the workspace, restoring `state.goal` (still empty) and erasing the typed text.
- The same state gap could also occur after a document upload completed and triggered a render.

## Fix

- Goal textarea now synchronizes every input event to `state.goal`.
- `toggleDoc()` calls `syncGoalInput()` before changing selection and rendering.
- Static assets upgraded from v11 to v12.

## Verification

- Frontend focused suite: 9 passed.
- Full Pathly regression: 79 passed, 2 existing third-party deprecation warnings.
- Live 4173: homepage and v12 JavaScript 200; script contains live input synchronization and checkbox pre-render preservation.
- Service PID: 58156.
- Browser click automation was attempted but again blocked by the Codex Windows sandbox (`CreateProcessWithLogonW failed: 1385`); not recorded as a browser pass.
# UI hotfix：secondary action button styling（2026-07-25）

- Root cause: `.scope-actions` provided layout only; its plain buttons retained browser-native appearance while the primary action used the Pathly design system.
- Added semantic `v2-secondary` styling to Back, Cancel and Reject actions.
- Added consistent 44px minimum height, padding, 12px radius, green border/text, product font weight, hover elevation, focus-visible outline and coordinated primary hover behavior.
- Static assets upgraded from v12 to v13.
- Frontend focused suite: 10 passed.
- Full Pathly regression: 80 passed, 2 existing third-party deprecation warnings.
- Live 4173: v13 CSS/JS 200; secondary base, hover and focus styles present; Back button uses `v2-secondary`.
- Automated visual browser inspection was attempted but blocked by the existing Windows sandbox error 1385; not recorded as a visual pass.
# Onboarding affective-question audit and multi-PDF upload（2026-07-26）

## Affective question audit

- Confirmed that confidence and pressure are operational inputs, not display-only profile fields.
- Confidence and pressure change review/quiz activity ratios; pressure also changes required-document reading speed estimates.
- Motivation was stored in the affective profile and path context but was not consumed by workload or scheduling logic.
- Removed the motivation question from both first-time and repeat onboarding.
- Kept confidence and pressure questions because they materially affect personalization.
- Retained motivation schema/default compatibility so existing learner profiles remain readable.
- First-time onboarding now contains 11 questions; repeat onboarding contains 5.

## Multi-PDF upload

- Both New Path and My Library file pickers now accept multiple PDFs in one selection.
- Selected files are submitted concurrently through the existing per-document secure API.
- Every file keeps independent validation, deduplication, ownership, background parsing and indexing.
- Partial failure no longer cancels successful files; the UI reports accepted count and failed filenames/reasons.
- Goal text is synchronized before upload so an upload-triggered render cannot erase the learner's draft goal.
- Static assets upgraded from v13 to v14.

## Verification

- Onboarding/workload focused regression: 15 passed.
- Frontend/onboarding/private-document focused regression: 25 passed.
- Full Pathly regression: 81 passed, with 2 existing third-party deprecation warnings.
- Live 4173 service restarted successfully; PID 42308; homepage 200 and v14 loaded.
- Live JavaScript exposes two multi-file inputs and parallel upload handling.
- Live first-time onboarding: 11 questions; motivation absent; confidence and pressure present.

## Known limits

- Multi-file upload is implemented as safe concurrent submissions to the existing single-document endpoint, not as a new all-or-nothing batch transaction.
- Files continue parsing independently in the background; readiness time may differ by document size.
# Repeat Onboarding incremental profile review（2026-07-26）

## Product behavior

- The returning-learner question now has two meaningful branches.
- Choosing `No` reuses the saved long-term profile and asks only path-specific questions.
- Choosing `Yes` opens an optional profile-review panel containing the saved value for each stable dimension.
- Learners explicitly select only the dimensions that changed; the original situational question is shown only for selected dimensions.
- The review covers cognitive foundations, explanation style, preferred examples, pace, baseline confidence, baseline pressure and recovery after interruptions.
- A before/after comparison is shown before profile confirmation.
- No long-term value is written until the learner confirms the profile step.
- Choosing `Yes` without selecting any dimension is blocked; choosing `No` clears unconfirmed review answers.

## Compatibility and UI

- Existing repeat-onboarding drafts are normalized when edited or confirmed.
- Legacy `current_motivation` questions are removed from old repeat drafts during normalization.
- `motivation_baseline` remains readable in stored schemas but is hidden from the learner-facing Live Profile.
- Path-specific confidence and pressure remain separate from long-term baseline updates.
- Added responsive review cards and compact mobile change comparison.
- Static assets upgraded from v14 to v15.

## Verification

- Backend profile-review suite: 9 passed.
- Frontend and onboarding focused suite: 21 passed.
- Full Pathly regression: 84 passed, with 2 existing third-party deprecation warnings.
- Live 4173 homepage: 200; v15, incremental review UI and motivation display filter confirmed.
- A live write-based anonymous-session E2E attempt was rejected when the external approval service disconnected; this is not recorded as passed.
- Equivalent create/update/confirm behavior is covered by API integration tests.
# Learner Profile persisted-data page fix（2026-07-26）

## Root cause

- The Learner Profile page read only `state.draft.profile_snapshot`.
- A learner with a saved SQLite profile but no current onboarding draft was incorrectly shown the first-time empty state.
- Navigation and refresh therefore made the page appear to lose an existing profile.

## Fix

- Added independent loading from `GET /api/profiles/{user_id}` during hydration and whenever the Profile page is opened.
- Added distinct loading, API error, true 404 empty and persisted-profile states.
- Profile confirmation now refreshes the in-memory persisted profile immediately.
- The page now separates reusable cognitive foundations from long-term learning preferences.
- Added profile version, reusable-dimension count, last-updated display and inference source/confidence details.
- Kept path-specific goals, mastery and timing out of the long-term profile page.
- Added a `Review Profile in a New Path` entry into the incremental repeat-onboarding flow.
- Kept `motivation_baseline` hidden while preserving storage compatibility.
- Added responsive desktop and narrow-screen layouts.
- Static assets upgraded from v15 to v16.

## Verification

- Profile UI, API and session-isolation focused suite: 23 passed.
- Full Pathly regression: 85 passed, with 2 existing third-party deprecation warnings.
- Live 4173: homepage 200, v16 loaded, independent Profile API call and removal of draft-snapshot dependency confirmed.
- Automated in-app visual inspection was attempted but blocked by the existing Windows sandbox error 1385; it is not recorded as a visual pass.
# Global fixed notification layer（2026-07-26）

## Root cause

- Errors and success notices were rendered inside the main page flow beneath the header.
- When the learner had scrolled down, messages appeared above the current viewport and required scrolling back to the top.
- Success notices had no independent dismiss action.

## Fix

- Replaced inline banners with a viewport-fixed notification stack.
- Errors and success updates remain visible at the top-right regardless of page scroll.
- Both notification types now have independent `Dismiss` actions.
- Added `role=alert`, `role=status`, `aria-live` and keyboard focus treatment.
- Notifications do not block interaction outside their own cards.
- Narrow screens use fixed 12px left/right/top margins and full available width.
- Added entrance animation, elevation, wrapping for long API messages and a high stacking layer.
- Static assets upgraded from v16 to v17.

## Verification

- Frontend focused suite: 14 passed.
- Full Pathly regression: 86 passed, with 2 existing third-party deprecation warnings.
- Live 4173: homepage 200; v17, notification stack, both dismiss actions, fixed positioning and z-index confirmed.
- Automated visual browser control remains unavailable because of the existing Windows sandbox error 1385; it is not recorded as a visual pass.
# Feasibility strategy selected state（2026-07-26）

## Clarification

- The empty field reported in Live Profile is `interest_tags`, not the removed motivation question.
- `interest_tags` is currently an unpopulated reserved field; adding a real optional onboarding question remains a separate product change.

## Fix

- Strategy cards now derive selection from the persisted `decision.selected_strategy`.
- The selected strategy shows a green border, light-green background, elevation and checkmark.
- Selection remains visible after the decision API response and when the saved decision is restored.
- Added hover and keyboard focus states.
- Added `radiogroup`, `radio` and `aria-checked` semantics.
- Static assets upgraded from v17 to v18.

## Verification

- Frontend and feasibility focused suite: 24 passed.
- Full Pathly regression: 87 passed, with 2 existing third-party deprecation warnings.
- Live 4173: homepage 200; v18, server-driven selected state, radio semantics, selected styling and checkmark confirmed.
# Feasibility strategy action hotfix（2026-07-27）

## Root cause

- Tight/feasible `extend_days` options omitted `suggested_days`.
- The frontend converted the missing value to `0` and sent it as `requested_days`, causing FastAPI validation to return 422.
- `save_draft` displayed a success notice without calling the decision API, so it neither saved nor selected the strategy.
- The fake-success branch bypassed the shared action wrapper, leaving an unrelated previous error visible.

## Fix

- Tight decisions now receive a deterministic future day that reaches the feasible buffer threshold.
- Feasible decisions receive a deterministic future day that reaches the comfortable buffer threshold.
- Ratio calculations use integer arithmetic to avoid `1.1` floating-point ceil errors.
- `extend_days` has a frontend fallback of at least `current requested days + 1` for previously stored options without a suggestion.
- `save_draft` now PATCHes the feasibility decision and receives the persisted selected state.
- `save_draft`, `adjust_outcome` and `set_daily_capacity` no longer expose `Confirm and Create Path`.
- All API-backed strategy clicks clear stale errors through the shared action boundary.
- Static assets upgraded from v18 to v19.

## Verification

- Feasibility and frontend focused suite: 26 passed.
- Full Pathly regression: 89 passed, with 2 existing third-party deprecation warnings.
- Exact boundary: 210 minutes at 21 minutes/day and 10 days recommends 11 days, not 0 or 12.
- The 3650-day maximum does not expose an impossible extension.
- Live 4173 restarted; homepage 200 and v19 loaded.
- Live v19 contains safe day fallback, real save-draft API flow, removal of the fake-success branch and path-confirmation authorization filtering.
# Onboarding tail closure: recovery, goal revision, pending documents (2026-07-27)

## Status and timing

- Status: internal acceptance passed; ready for user acceptance.
- Completed: 2026-07-27 16:34 +08:00.
- Scope: a small Onboarding closure stage only. Daily content, chat, Quiz, Adaptation and deployment work remain outside this stage.

## Product behavior completed

- Feasibility decisions are now linked back to the active onboarding draft.
- Refresh restores the saved decision by draft reference, with a latest-decision-by-estimate fallback for older drafts.
- The selected strategy and `adjust_outcome` edit state survive refresh.
- `adjust_outcome` now opens the real Goal & Sources editor instead of only showing a notice.
- Revising a goal preserves the confirmed learner profile and onboarding answers.
- Revising a goal invalidates the old workload estimate and capacity decision before recalculation.
- Historical estimate and decision records remain in SQLite for audit; only the active draft references are cleared.
- Documents in pending/queued/processing/parsing/indexing states are polled every two seconds.
- Non-ready documents are visibly disabled and cannot be selected or submitted to goal interpretation.
- Previously selected documents are pruned if they are no longer ready.
- Static assets upgraded from v19 to v20.

## API and data changes

- Added `POST /api/onboarding-drafts/{draft_id}/revise-goal`.
- Added `GET /api/workload-estimates/{estimate_id}/feasibility-decision`.
- Added `feasibility_decision_id` to the persisted onboarding draft JSON when a decision is created.
- No destructive database migration was required; existing JSON payload storage remains compatible.

## Verification

- JavaScript syntax check: passed.
- Python compile check for feasibility, onboarding and server modules: passed.
- Full automated regression: 93 passed, 2 third-party deprecation warnings.
- Regression tests cover decision-to-draft linking, cross-user decision isolation, profile-preserving goal revision, downstream invalidation, decision restoration contracts and pending-document gating/polling.
- Live 4173 service: `/api/health` returned 200 and `service_ready=true`.
- Live homepage returned 200 and loaded v20 JavaScript and CSS.
- Live OpenAPI exposes both new endpoints.
- In-app visual browser automation was attempted but blocked by Windows sandbox error 1385; it is not recorded as a visual pass.

## Known limits and manual acceptance

- A document that remains pending because its parser has genuinely failed still requires the existing retry/delete recovery actions in My Library.
- Goal revision reuses the confirmed profile by design; it does not re-ask long-term profile questions.
- Manual acceptance:
  1. Reach Capacity, select a strategy, refresh, and confirm the same card remains selected.
  2. Select `adjust_outcome`; change the goal; continue and confirm Workload is recalculated without repeating Learner Profile.
  3. Upload a PDF and confirm it is disabled while pending, then becomes selectable when ready.

# Onboarding clickable steps and capacity reconfirmation (2026-07-27)

## Status and timing

- Status: internal acceptance passed; ready for user acceptance.
- Completed: 2026-07-27 17:22 +08:00.

## Product behavior completed

- Every reached Onboarding step is now a real keyboard-accessible button.
- Future incomplete steps remain disabled so required confirmation cannot be skipped.
- From Create Path, learners can return to Goal & Sources, Learner Profile, Workload or Capacity.
- Goal changes remain explicit and invalidate downstream workload/capacity only after saving.
- Learner Profile and Workload provide safe review checkpoints without silently changing confirmed data.
- Returning to Capacity restores the current days and daily-minute values and permits a new feasibility check.
- An insufficient capacity result now remains on Capacity instead of immediately entering Create Path.
- The learner must make a second explicit choice: extend days, increase daily time, or keep limits and review goal/scope alternatives.
- Capacity changes are persisted only after `Confirm Change and Continue`.
- Static assets upgraded from v20 to v21.

## API and data changes

- Existing draft goal revision now also supports an unconfirmed `draft`, preserving answers while changing the goal.
- Confirmed path goals still invalidate workload and capacity references when revised.
- No database migration or destructive data change was required.

## Verification

- Focused navigation, onboarding and feasibility suite: 42 passed.
- Full regression: 96 passed, 2 third-party deprecation warnings.
- JavaScript and Python syntax checks passed.
- Live 4173 homepage returned 200 and loaded v21 JavaScript/CSS.
- The live v21 script contains clickable-step navigation, profile/workload review checkpoints and capacity correction confirmation.
- In-app visual automation was attempted but remains blocked by Windows sandbox error 1385; it is not recorded as a visual pass.

## Manual acceptance

1. On Create Path, click each completed node and confirm it opens the corresponding earlier checkpoint.
2. Return to Capacity, enter a deliberately insufficient combination and click `Check Feasibility`.
3. Confirm the page remains on Capacity and displays `SECOND CONFIRMATION REQUIRED`.
4. Select an adjustment and confirm the selected card has a visible selected state.
5. Click `Confirm Change and Continue`; confirm the values change and only then enter Create Path.

# Create Path strategy explicit confirmation (2026-07-27)

## Status

- Status: internal acceptance passed; ready for user acceptance.
- Scope: prevent strategy-card selection from mutating the feasibility decision.

## Product behavior completed

- Clicking a strategy card now changes only local pending selection state.
- The workload, recommended daily minutes and capacity gap above remain unchanged while a choice is pending.
- A confirmation panel shows Current and After confirmation values.
- Only `Confirm This Choice` writes the selected strategy to the feasibility decision.
- `extend_days`, `increase_daily_time`, `proceed`, `save_draft`, `adjust_outcome` and `narrow_scope` follow the same confirmation boundary.
- Cancelling the preview clears the pending selection without changing persisted data.
- `Confirm and Create Path` remains a separate final action and is hidden while an unconfirmed strategy is pending.
- Static assets upgraded from v21 to v22.

## Verification

- Frontend and feasibility focused suite: 31 passed.
- Full regression: 96 passed, 2 third-party deprecation warnings.
- JavaScript and Python syntax checks passed.
- Live 4173 homepage returned 200 and loaded v22.
- Live v22 contains the confirmation preview and handler.
- Verified the live strategy-card click handler contains no API call.

## Manual acceptance

1. Record the three values in the top summary.
2. Click `extend_days`; confirm the values do not change.
3. Review the Current and After confirmation comparison.
4. Click Cancel and confirm no value changes.
5. Select again and click `Confirm This Choice`; only now should the top values update.
6. Confirm that path creation still requires the separate `Confirm and Create Path` action.

# Remove redundant save_draft strategy (2026-07-27)

## Status

- Status: internal acceptance passed; ready for user acceptance.
- Decision: Onboarding already auto-saves, so a separate save-draft strategy is redundant and misleading.

## Product behavior completed

- Removed `save_draft` from capacity-pending, insufficient, tight and feasible option generation.
- Removed all `save_draft` labels, previews and notices from the frontend.
- Automatic persistence of onboarding drafts, answers, workload, feasibility decision and browser draft pointer remains unchanged.
- Kept legacy backend recognition and path-creation blocking for existing stored `save_draft` decisions so old data remains safe and readable.
- Static assets upgraded from v22 to v23.

## Verification

- Frontend and feasibility focused suite: 33 passed.
- Full regression: 98 passed, 2 third-party deprecation warnings.
- Live 4173 homepage returned 200 and loaded v23.
- The live frontend contains no `save_draft`.
- The live frontend still persists the current `draftId` for automatic refresh recovery.

# Dashboard selected view and readable private concepts (2026-07-27)

## Status

- Status: internal acceptance passed; ready for user acceptance.
- Scope: make the Dashboard view switch explicit and remove opaque private concept IDs from learner-facing nodes.

## Product behavior completed

- `Knowledge Map` and `Activity Timeline` now have a persistent visual selected state driven by the active Dashboard view.
- Both controls expose `aria-pressed`, grouped semantics, hover and keyboard-focus states.
- Newly generated workload concept paths preserve the private concept `display_name` from the confirmed goal interpretation.
- Existing historical plans that contain only `private:<hash>` are rendered as numbered `Private concept` labels instead of exposing internal IDs.
- Canonical concept labels remain unchanged.
- Static assets upgraded from v23 to v24.

## Data and compatibility

- No database migration or destructive data change was required.
- New estimates store both the stable private concept ID and its human-readable display name in the concept path.
- A hash alone cannot reconstruct the historical source phrase. Historical plans therefore use an honest generic label; regenerating a path from its confirmed interpretation stores the real label.

## Verification

- JavaScript and Python syntax checks passed.
- Focused frontend, workload and scheduler suite: 41 passed, 1 third-party deprecation warning.
- Full regression: 101 passed, 2 third-party deprecation warnings.
- Live 4173 homepage serves v24.
- Live v24 contains the selected-state accessibility attributes and readable private-label guard; the previous raw-ID renderer is absent.
- In-app visual automation was attempted but remains blocked by Windows sandbox error 1385; it is not recorded as a visual pass.

## Manual acceptance

1. Refresh the Learning Paths page.
2. Confirm `Knowledge Map` is visibly selected initially.
3. Click `Activity Timeline`; confirm its selected state moves with the displayed view.
4. Return to `Knowledge Map`; confirm no node displays `private:<hash>`.
5. Existing paths may display numbered `Private concept` labels. A newly generated path should display the original extracted concept names.

# Activity Timeline private-ID and encoding cleanup (2026-07-27)

## Status

- Status: internal acceptance passed; ready for user acceptance.
- Correction: the v24 fix covered Knowledge Map nodes but did not cover Activity Timeline titles and reasons.

## Product behavior completed

- Historical plan activity titles, reasons and Planning Rationale now pass through the same readable private-concept resolver as Knowledge Map nodes.
- Known private IDs are replaced by their concept display name; historical IDs with no recoverable label use `Private concept N`.
- Newly generated activities are sanitized in the backend before workload and schedule persistence.
- Private concept planning reasons and estimate-source reasons now carry the confirmed display name.
- Removed all remaining learner-facing encoding artifacts from the HTML and JavaScript assets.
- Static assets upgraded from v24 to v25.

## Verification

- JavaScript and Python syntax checks passed.
- Focused frontend, workload and scheduler suite: 43 passed, 1 third-party warning.
- Full regression: 103 passed, 2 third-party warnings.
- Learner-facing `index.html` and `pathly-app.js` contain zero non-ASCII characters after cleanup.
- Live 4173 homepage serves v25; live v25 includes the timeline scrubber and private fallback.
- In-app visual automation was attempted but remains blocked by Windows sandbox error 1385; it is not recorded as a visual pass.

## Manual acceptance

1. Hard-refresh Learning Paths and switch to Activity Timeline.
2. Confirm activity titles and reasons do not contain `private:<hash>`.
3. Confirm separators, arrows, privacy label and loading copy contain no encoding artifacts.
4. Historical paths may show `Private concept N`; newly generated paths should show the extracted concept display name.
