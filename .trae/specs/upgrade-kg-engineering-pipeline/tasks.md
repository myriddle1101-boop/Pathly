# Tasks

- [x] Task 1: 冻结当前可用 KG baseline
  - [x] SubTask 1.1: 盘点当前可跑通的 KG 主链路、代表性输入样本和关键输出目录
  - [x] SubTask 1.2: 建立 baseline 保存方式，保留依赖、样本、输出和状态说明
  - [x] SubTask 1.3: 产出 baseline 阶段输出物，确保后续升级可回滚、可复现

- [x] Task 2: 完成 GPU 优先执行链路
  - [x] SubTask 2.1: 统一本地模型的设备选择逻辑，收口到 `device_manager`
  - [x] SubTask 2.2: 让 `stage2a`、`stage2c`、RAG 向量化优先使用 GPU，并保留 CPU 回退
  - [x] SubTask 2.3: 增加运行时验证，确认输出中能明确记录 `device_info`
  - [x] SubTask 2.4: 产出 GPU 阶段输出物，包括验证日志和 CPU/GPU 对比 benchmark

- [x] Task 3: 提升批量稳定性
  - [x] SubTask 3.1: 为单文档运行增加 manifest 结构，记录输入、哈希、stage 状态、耗时和输出路径
  - [x] SubTask 3.2: 为批量流程增加失败隔离和断点续跑能力
  - [x] SubTask 3.3: 为每个 stage 补充统一日志和输入输出检查
  - [x] SubTask 3.4: 产出批量稳定阶段输出物，包括 manifest、批量日志和失败恢复样例

- [x] Task 4: 完成可评测版本
  - [x] SubTask 4.1: 固定性能 benchmark 输入、输出格式和运行方式
  - [x] SubTask 4.2: 固定 KG 质量评测的小样本输入、指标和输出格式
  - [x] SubTask 4.3: 让评测结果可稳定复现，并直接支持论文实验使用
  - [x] SubTask 4.4: 产出评测阶段输出物，包括 benchmark 结果、quality_eval 结果和实验表格底稿

- [x] Task 5: 更新文档与项目状态
  - [x] SubTask 5.1: 更新 `PRD.md` 记录 baseline、GPU、批量稳定和评测状态
  - [x] SubTask 5.2: 更新 `CHANGELOG.md` 记录每个阶段的新增能力和输出物
  - [x] SubTask 5.3: 明确当前工程版本与原型版本的状态边界

- [ ] Task 6: 做最终验收
  - [ ] SubTask 6.1: 验证 baseline 可回滚、可复现
  - [ ] SubTask 6.2: 验证 GPU 优先链路已真正进入运行时
  - [ ] SubTask 6.3: 验证批量处理时单文档失败不影响其他任务
  - [ ] SubTask 6.4: 验证 benchmark 与质量评测结果可被稳定产出

- [ ] Task 7: 修复 Task 6 最终验收未通过项
  - [ ] SubTask 7.1: 修复 baseline 复现实验不一致问题，至少让代表样本 `Security and Privacy in ML` 的 `stage2a-stage4` 产物可按配方重跑并通过 `sha256` 校验
  - [ ] SubTask 7.2: 完成 CUDA 运行时打通并补齐 `stage2a`、`stage2c` 的真实 `device_info.device = cuda` 证据；若当前环境暂不具备条件，则更新口径并显式降级为 CPU-only 已验证
  - [ ] SubTask 7.3: 用真实批量运行样本补齐 `manifest.json`、`run_log.json`、`recovery_state.json`、`batch_run_log.json` 和失败隔离 / 断点续跑验收证据
  - [ ] SubTask 7.4: 修复 Task 4 结果不稳定问题，重新定义 benchmark 波动容忍区间与质量评测稳定性判据，并更新论文实验使用口径
  - [ ] SubTask 7.5: 同步修正文档中的验收结论、评测指标数值和阶段状态，避免把“已有入口”写成“已最终通过”

# Task Dependencies
- `Task 2` depends on `Task 1`
- `Task 3` depends on `Task 1`
- `Task 4` depends on `Task 2` and `Task 3`
- `Task 5` depends on `Task 1`, `Task 2`, `Task 3`, and `Task 4`
- `Task 6` depends on `Task 1`, `Task 2`, `Task 3`, `Task 4`, and `Task 5`
- `Task 7` depends on `Task 6`
