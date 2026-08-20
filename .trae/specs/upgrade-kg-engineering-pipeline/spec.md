# KG 工程化升级 Spec

## Why
当前 `KG_construction` 已经具备可跑通的知识图谱流水线，但仍停留在“研究原型可用、工程能力不足”的阶段。为了支撑后续毕设开发、批量实验和论文评测，需要先冻结当前可用 baseline，再把系统升级为 `GPU 优先、批量稳定、可评测` 的工程版本。

## What Changes
- 新增“当前可用 KG baseline 冻结”能力，保存可回滚、可复现的输入、配置和输出产物。
- 新增 `GPU 优先` 执行链路，统一设备选择、批量编码和运行时验证。
- 新增 `批量稳定` 的任务执行机制，包括 manifest、日志、断点续跑和失败隔离。
- 新增 `可评测` 的质量与性能实验基线，形成固定输入、固定指标、固定输出。
- 新增“阶段输出物”规范，确保每一步升级都留下可审计产物。

## Impact
- Affected specs: KG baseline 管理、设备调度、批处理稳定性、实验评测规范
- Affected code: `KG_construction/app.py`、`KG_construction/infra/config.py`、`KG_construction/infra/device_manager.py`、`KG_construction/stage2a_hybrid_keybert_llm.py`、`KG_construction/stage2c_similarity.py`、`KG_construction/evaluation/kg_benchmark.py`、`KG_construction/evaluation/kg_quality_eval.py`、`KG_construction/web_data/`

## ADDED Requirements
### Requirement: KG Baseline 冻结
系统 SHALL 提供一套冻结当前可用 KG baseline 的机制，用于保存当前可跑通版本的配置、样本输入和关键输出。

#### Scenario: 冻结当前可用版本
- **WHEN** 开发者准备开始工程化升级
- **THEN** 系统能够保存当前 baseline 的依赖、样本文档、代表性输出和版本说明
- **THEN** 升级失败时可以回到冻结版本重新运行

### Requirement: GPU 优先执行
系统 SHALL 在本地嵌入与相似度计算相关模块中优先使用 GPU，并在 GPU 不可用时稳定回退到 CPU。

#### Scenario: GPU 可用
- **WHEN** 运行 `stage2a`、`stage2c` 或 RAG 向量化
- **THEN** 系统优先选择 `cuda`
- **THEN** 运行产物中记录设备信息、batch size 和耗时

#### Scenario: GPU 不可用
- **WHEN** 当前环境没有可用 CUDA
- **THEN** 系统自动回退到 `cpu`
- **THEN** 不影响功能正确性和产物结构

### Requirement: 批量稳定处理
系统 SHALL 提供按文档粒度的稳定批处理能力，支持失败隔离、断点续跑和统一执行记录。

#### Scenario: 批量处理多个 PDF
- **WHEN** 用户批量运行多个文档
- **THEN** 每个文档都生成独立的运行状态记录
- **THEN** 单个文档失败不会中断其他文档
- **THEN** 已完成 stage 可被复用，避免无意义重跑

### Requirement: 统一运行记录
系统 SHALL 为每个文档生成统一的 manifest 和日志，以支持调试、复盘和实验记录。

#### Scenario: 单文档运行完成
- **WHEN** 某个文档完整或部分跑完 KG pipeline
- **THEN** 系统产出 manifest，记录输入文件、哈希、各 stage 状态、设备信息、耗时和输出路径

### Requirement: 可评测实验基线
系统 SHALL 提供固定输入、固定指标和固定输出路径的性能与质量评测流程。

#### Scenario: 跑性能评测
- **WHEN** 开发者对同一份 PDF 分别运行 CPU 和 GPU 版本
- **THEN** 系统输出可比较的 benchmark 结果
- **THEN** 结果包含每个 stage 耗时、总耗时和设备信息

#### Scenario: 跑质量评测
- **WHEN** 开发者使用人工标注的小样本数据集评估 KG
- **THEN** 系统输出 topic、prerequisite、similarity 的固定指标结果
- **THEN** 输出结果可直接进入论文实验部分

### Requirement: 阶段输出物保留
系统 SHALL 为工程化升级的每个阶段保留明确输出物，确保升级过程可审计、可回顾、可展示。

#### Scenario: 阶段完成
- **WHEN** 每一阶段实现完成
- **THEN** 系统保留对应的代码、说明、日志、benchmark 或评测结果
- **THEN** 输出物能作为后续开发与论文写作依据

## MODIFIED Requirements
### Requirement: KG 系统状态表达
系统 SHALL 将 KG 系统从“单次可跑通原型”升级为“有 baseline、有设备策略、有批处理能力、有评测闭环的工程化系统”。

#### Scenario: 对外描述当前版本
- **WHEN** 开发者或评审查看系统状态
- **THEN** 可以明确区分 baseline、GPU 状态、批处理稳定性和评测完成度

## REMOVED Requirements
### Requirement: 仅以单次运行成功作为 KG 系统完成标准
**Reason**: 单次跑通无法支撑后续批量实验、工程迭代和论文评测。  
**Migration**: 以后以 baseline 冻结、GPU 运行确认、批量稳定验证和评测结果共同作为 KG 系统升级完成标准。
