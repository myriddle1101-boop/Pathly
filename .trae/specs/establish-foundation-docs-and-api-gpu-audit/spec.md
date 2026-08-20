# 基础建设文档与 API/GPU 审计 Spec

## Why
当前项目已经完成了一部分基础设施代码，但缺少正式的产品文档沉淀和基础环境说明，导致后续开发、汇报和答辩材料不够统一。与此同时，OpenAI API 尚未配置完成，GPU 也只是代码层支持切换，尚未形成可确认的基础建设结论。

## What Changes
- 新增 `PRD.md`，沉淀当前系统目标、模块边界、Month 1 基础设施现状与下一步开发路线。
- 新增 `CHANGELOG.md`，记录本轮基础设施落地内容，作为后续每次改动后的更新入口。
- 明确 OpenAI API 的本地配置方式、验证方式和排错方式。
- 输出当前 GPU 迁移状态审计结论，区分“代码已支持”与“运行时已确认迁移完成”。
- 在文档中明确当前三块基础设施 `KG / RAG / 用户画像` 的完成度、依赖关系和后续优先级。

## Impact
- Affected specs: 基础建设文档规范、环境配置规范、运行时审计规范
- Affected code: `KG_construction/test_openai.py`、`KG_construction/infra/device_manager.py`、`KG_construction/stage2a_hybrid_keybert_llm.py`、`KG_construction/stage2c_similarity.py`

## ADDED Requirements
### Requirement: 项目基础 PRD
系统 SHALL 提供一份可直接用于毕设开发和汇报的 `PRD.md`，清晰描述系统目标、用户价值、模块结构、当前进度和近期开发计划。

#### Scenario: PRD 覆盖基础建设
- **WHEN** 读者打开 `PRD.md`
- **THEN** 可以看到 `KG`、`RAG`、`用户画像`、`Planning Agent` 的职责划分与当前完成度
- **THEN** 可以看到当前 Month 1 范围内已完成内容和下一步待做内容

### Requirement: 变更记录文档
系统 SHALL 提供一份 `CHANGELOG.md`，记录基础设施落地、环境要求和后续变更维护规则。

#### Scenario: 记录本轮基础设施更新
- **WHEN** 读者查看 `CHANGELOG.md`
- **THEN** 可以看到新增的基础设施模块、Planning Agent 主链路、评测脚本、依赖补充和已知限制

### Requirement: OpenAI API 配置说明
系统 SHALL 提供一套明确的 OpenAI API 配置与验证说明，适配当前 Windows + VS Code + `.venv` 环境。

#### Scenario: 配置 API
- **WHEN** 用户按照说明配置 `OPENAI_API_KEY`
- **THEN** 能明确知道应放在什么位置、如何在当前会话中验证
- **THEN** 能使用 `test_openai.py` 进行连通性测试

### Requirement: GPU 迁移状态审计
系统 SHALL 明确区分 GPU 支持代码、GPU 运行时可用性和 GPU 迁移完成状态，并在文档中给出当前结论。

#### Scenario: 判断是否已迁移到 GPU
- **WHEN** 用户查看文档中的 GPU 审计说明
- **THEN** 能知道当前 `stage2a` 与 `stage2c` 已接入 `device_manager`
- **THEN** 能知道仅凭代码结构不能证明“已经迁移完成”
- **THEN** 能知道需要通过运行日志或 benchmark 输出确认实际设备是否为 `cuda`

### Requirement: 基础设施优先级说明
系统 SHALL 明确当前三块基础设施的建设状态和建议优先级，帮助后续先把底座做稳。

#### Scenario: 明确下一步
- **WHEN** 用户查看基础设施部分
- **THEN** 能看到当前建议顺序为 `API 配置 -> GPU 运行确认 -> KG benchmark -> app.py 中接入 Planning Agent 或 Content Agent`

## MODIFIED Requirements
### Requirement: 基础设施进度表达方式
系统 SHALL 将“功能代码已存在”与“环境已配置完成、运行已验证”分开表达，避免把设计状态误写成完成状态。

#### Scenario: 审核当前状态
- **WHEN** 文档描述基础设施进度
- **THEN** 必须分别标出“已实现”“待配置”“待运行验证”“已知限制”

## REMOVED Requirements
### Requirement: 无正式基础建设文档也可推进开发
**Reason**: 当前项目已进入多模块并行阶段，缺失统一文档会增加沟通和维护成本。  
**Migration**: 以后所有基础设施和阶段性改动先同步到 `PRD.md` 与 `CHANGELOG.md`，再继续后续开发。
