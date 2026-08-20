# Tasks

- [x] Task 1: 盘点基础建设现状并整理成可写入文档的事实清单
  - [x] SubTask 1.1: 确认 `PRD.md`、`CHANGELOG.md`、`.env` 在修改前当前不存在
  - [x] SubTask 1.2: 确认 OpenAI API 当前已配置成功，可通过 `test_openai.py` 复验
  - [x] SubTask 1.3: 确认 GPU 现状为“代码支持切换，但未完成运行时确认”

- [x] Task 2: 编写 `PRD.md`
  - [x] SubTask 2.1: 写明项目目标、目标用户和系统范围
  - [x] SubTask 2.2: 写明 `KG / RAG / 用户画像 / Planning Agent / Content Agent / Adaptation Agent` 的职责与当前进度
  - [x] SubTask 2.3: 写明 Month 1 的基础设施优先级、依赖关系和近期路线
  - [x] SubTask 2.4: 写明当前已知限制，包括 API 已配置成功且 GPU 未确认迁移完成

- [x] Task 3: 编写 `CHANGELOG.md`
  - [x] SubTask 3.1: 记录本轮新增的基础设施层、Planning Agent、评测脚本和测试
  - [x] SubTask 3.2: 记录依赖补充与环境要求
  - [x] SubTask 3.3: 记录已知问题与后续维护规则

- [x] Task 4: 将 API 配置与 GPU 审计说明写入文档
  - [x] SubTask 4.1: 写明 Windows PowerShell 下 `OPENAI_API_KEY` 的配置方式
  - [x] SubTask 4.2: 写明如何使用 `test_openai.py` 验证 API
  - [x] SubTask 4.3: 写明如何通过日志或 benchmark 字段确认 `cuda`
  - [x] SubTask 4.4: 明确当前结论不是“已迁移完成”，而是“已具备迁移入口”

- [x] Task 5: 自检文档完整性
  - [x] SubTask 5.1: 检查 `PRD.md` 是否覆盖基础建设与近期路线
  - [x] SubTask 5.2: 检查 `CHANGELOG.md` 是否覆盖本轮新增内容与限制
  - [x] SubTask 5.3: 检查文档表述是否区分“已实现”和“已验证”

- [ ] Task 6: 修复验收失败项中的 API 状态与勾选可验证性问题
  - [ ] SubTask 6.1: 统一 `spec / PRD / CHANGELOG / checklist` 对 API 状态的表述，明确区分“已配置”“可调用”“已独立验证”
  - [ ] SubTask 6.2: 去掉当前无法独立验证的完成勾选，或改写为可通过命令、脚本或记录独立验证的表述

# Task Dependencies
- `Task 2` depends on `Task 1`
- `Task 3` depends on `Task 1`
- `Task 4` depends on `Task 1`
- `Task 5` depends on `Task 2`, `Task 3`, and `Task 4`
