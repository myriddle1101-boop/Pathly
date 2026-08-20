# DP4 / KQ6 双用户最终验收报告

日期：2026-08-14

## 验收对象

- Foundation Learner：`demo-foundation-learner`
- Advanced Learner：`demo-advanced-learner`
- 相同目标：Learn how neural networks solve XOR using activation functions and gradient descent
- 相同黄金五节点、来源版本、60 分钟/天、60 天控制条件

## 真实生成结果

| 项目 | Foundation | Advanced |
|---|---:|---:|
| 计划 ID | `9e0d672f-30e8-4134-a982-75d5ed835212` | `f9770079-a153-421c-9c37-3d2466a0f493` |
| 黄金节点 | 5/5 | 5/5 |
| 教学 payload | 5/5 ready | 5/5 ready |
| 生成模式 | approved_profile_fallback | approved_profile_fallback |
| 生成器 | source-grounded-v4-dp3-dual-user-v1 | source-grounded-v4-dp3-dual-user-v1 |
| Prompt | ml-education-expert-v2 | ml-education-expert-v2 |
| 画像处理 | dual-user-treatment-v1 | dual-user-treatment-v1 |

两套内容在每个节点均产生了 7 个可测差异：开篇 hook、解释顺序、机制粒度、先修解释、来源解释、例子步骤数、题目 framing。Foundation 使用 student-support 场景；Advanced 使用 image-classification 场景。canonical 定义、边界、来源和正误结论一致；所有题目通过 KQ4 质量门禁。

## 隔离与持久化

- 两个计划 owner、画像、缓存身份不同。
- 两个账号分别保存第一道题的答案，刷新/重新读取状态均恢复正确。
- 交叉读取另一账号资源返回空，不存在串号。
- 重新生成使用当前账号及其计划情境，并携带 profile/prompt/generator 版本。

## 自动化验证

- DP0–DP3 专项与回归测试：`297 passed`。
- 五节点离线 fallback 双画像矩阵：`10/10 ready`。
- 每题均有 assessment target、source refs、针对性反馈；元说明检测为 0。
- live 模型路径的有效/失败分支测试通过；一次真实 live 全矩阵因外部模型响应超时，未将其冒充为成功，最终用户路径由已验证的节点专属 fallback 保证可用。

## 结论

DP4/KQ6 在受控双用户、真实计划、节点专属 fallback 和端到端隔离条件下通过。后续可直接从页面顶部账号入口切换两个用户进行人工验收；不需要继续投入 v1/v2 或扩大知识领域。
