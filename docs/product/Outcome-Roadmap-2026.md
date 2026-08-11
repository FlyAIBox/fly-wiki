# FlyWiki Outcome Roadmap 2026

> 更新日期：2026-08-11  
> 当前阶段：M0 — 微信驱动的自进化 Wiki 闭环  
> 跟踪入口：[FlyAIBox/fly-wiki Issues](https://github.com/FlyAIBox/fly-wiki/issues)  
> 依据：[产品基线](产品基线.md) · [首个里程碑](首个里程碑.md) · [领域词汇表](../../CONTEXT.md) · [ADR](../adr/)

## 1. Roadmap 原则

Roadmap 描述要实现的用户结果和阶段顺序，GitHub Issues 记录具体交付与验收状态。出现状态差异时，以 Issue 的验收证据和关闭状态为准，并同步修正本文。

阶段窗口用于表达顺序，不是发布日期承诺：

| 阶段 | 建议窗口 | 用户结果 |
| --- | --- | --- |
| M0 | Now / 2026 Q3 | Owner 能从微信提交两篇资料，在 Web 审阅知识变化，并获得带原文引用的回答 |
| M1 | Next / 2026 Q4 | 持续追踪者只需审阅重要变化，不再重复阅读全部来源 |
| M2 | Later / 2027 H1 | 用户能从浏览器顺手采集，并可把知识安全带出 FlyWiki |
| M3 | Explore / M2 后 | 在不削弱证据与 Workspace 边界的前提下扩展来源、图谱探索和 Channel |

## 2. 状态定义

| Roadmap 状态 | 判定规则 |
| --- | --- |
| ✅ 已完成 | Issue 已关闭，Acceptance criteria 有测试、验收记录或可重复演示作为证据 |
| 🟠 待验收 | 功能实现已完成，但 Issue 尚未完成验收或关闭 |
| 🟡 部分完成 | 已有实现和测试，但尚未覆盖 Issue 的完整 Scope |
| ⬜ 可开始 | 依赖已满足，Issue 已明确且带 `ready-for-agent` 或 `ready-for-human` |
| ⛔ 被依赖阻塞 | 至少一个前置 Issue 未完成 |
| 🔵 已规划 | 已进入 Roadmap，但尚未拆成可执行 Issue |

五个 canonical triage labels 只表达任务该由谁继续处理：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。它们不替代上述交付状态。

## 3. 当前状态快照

截至 2026-08-11，M0 总票 [#1](https://github.com/FlyAIBox/fly-wiki/issues/1) 和 10 个实现子票均为 Open。仓库实现状态为：1 项待验收、4 项部分完成、5 项尚未进入核心实现。采集模块由项目发起人确认完成，现有自动化验证为后端 52 项测试、前端 3 项测试及前端类型检查通过。

| 顺序 | 能力 | Issue | GitHub 状态 | Roadmap 状态 | 依赖 / 下一动作 |
| --- | --- | --- | --- | --- | --- |
| 0 | 自托管平台骨架与 Workspace Owner 边界 | [#3](https://github.com/FlyAIBox/fly-wiki/issues/3) | Open · `ready-for-agent` | 🟡 部分完成 | 核对完整 Compose、健康检查、迁移与 Workspace 隔离验收后关闭 |
| 0 | 不可变网页采集与 Editable Note | [#2](https://github.com/FlyAIBox/fly-wiki/issues/2) | Open · `ready-for-agent` | 🟠 待验收 | 按 AC 做一次真实网页/公众号回归，记录证据并关闭 Issue |
| 0 | 受限 AgentRuntime 与 DeepAgents | [#10](https://github.com/FlyAIBox/fly-wiki/issues/10) | Open · `ready-for-agent` | 🟡 部分完成 | 补多步 grounded analysis、取消/预算、静态依赖与权限拒绝验收 |
| 1 | OpenKB Worker 与可重建编译 | [#5](https://github.com/FlyAIBox/fly-wiki/issues/5) | Open · `ready-for-agent` | ⬜ 可开始 | M0 下一条核心价值切片；先完成 #2、#3 验收，替换 placeholder Worker |
| 2 | Claim—Evidence、Knowledge Delta 与可逆变更 | [#4](https://github.com/FlyAIBox/fly-wiki/issues/4) | Open · `ready-for-agent` | ⛔ 被依赖阻塞 | 依赖 #3、#5、#10 |
| 3 | 严格 grounded chat 与引用审计 | [#6](https://github.com/FlyAIBox/fly-wiki/issues/6) | Open · `ready-for-agent` | ⛔ 被依赖阻塞 | 依赖 #4、#5、#10 |
| 4A | Knowledge Inbox、Markdown 编辑与一跳证据图 | [#8](https://github.com/FlyAIBox/fly-wiki/issues/8) | Open · `ready-for-agent` | 🟡 部分完成 | 已有采集首页与 Note 编辑器；完整 Inbox、Delta 审阅和一跳图依赖 #6 |
| 4B | Owner-only WeixinChannel | [#7](https://github.com/FlyAIBox/fly-wiki/issues/7) | Open · `ready-for-agent` | ⛔ 被依赖阻塞 | 依赖 #3、#6；可与 #8 后半段并行 |
| 横切 | Langfuse 观测与评估闭环 | [#11](https://github.com/FlyAIBox/fly-wiki/issues/11) | Open · `ready-for-agent` | 🟡 部分完成 | 已有 Observability Interface/Adapter；随 #5—#7 补 Trace、Scores、Dataset 与 Experiment |
| 5 | 端到端验收与发布门禁 | [#9](https://github.com/FlyAIBox/fly-wiki/issues/9) | Open · `ready-for-agent` | ⛔ 被依赖阻塞 | 所有 M0 子票完成后执行八步演示、故障注入与重建验收 |

## 4. 推荐开发顺序

### M0-A：收口已实现基础

**结果**：让已完成的采集和平台能力拥有可信的完成状态，为后续模块提供稳定接口。

1. 按 #2 Acceptance criteria 完成真实来源验收并关闭采集票。
2. 补齐 #3 的 Compose 与 Workspace 边界验收。
3. 补齐 #10 的能力授权、结构化失败和 Fake 可复现测试。

完成门槛：三个 Issue 均有验收证据；后续开发不再绕过 Capture Pipeline、Workspace Context 或 AgentRuntime。

### M0-B：把资料编译成可重建知识

**结果陈述**：让 Owner 能把 Source Version 和 Editable Note 编译为可浏览 Wiki，同时保留原始证据和回退能力。

- 交付 [#5](https://github.com/FlyAIBox/fly-wiki/issues/5)：固定 OpenKB 版本、独立 Worker、OpenKBAdapter、串行写入、重建与回退。
- 关键指标：同一 Source Version 重试零重复；删除 OpenKB Workspace 后可重建；固定版本兼容测试阻断发布。

### M0-C：识别知识变化，而不是只生成摘要

**结果陈述**：让 Owner 看见第二篇资料相对当前 Compiled Knowledge 带来的新增、强化或认知更新，并能追溯和撤销。

- 交付 [#4](https://github.com/FlyAIBox/fly-wiki/issues/4)：Claim、Evidence Span、Evidence Relation、Knowledge Delta、Change Proposal 和 Knowledge Change Set。
- 关键指标：事实 Claim 的 Evidence Span 覆盖率 100%；四类产品结果可追溯到七类领域枚举；冲突未经审阅零自动生效；自动变更 100% 可回滚。

### M0-D：用证据回答问题

**结果陈述**：让 Owner 获得只基于当前 Knowledge Base 的回答，并能逐条打开事实依据。

- 交付 [#6](https://github.com/FlyAIBox/fly-wiki/issues/6)：检索、上下文组装、多轮问答、事实引用审计和“不知道”路径。
- 关键指标：已发送回答的事实 Claim 引用覆盖率 100%；无证据时零模型常识补答；跨 Knowledge Base 访问零容忍。

### M0-E：完成日常操作面和微信闭环

**结果陈述**：让 Owner 在 Web 集中处理知识变化，并在微信完成提交、进度接收和引用问答。

- 并行交付 [#8](https://github.com/FlyAIBox/fly-wiki/issues/8) 与 [#7](https://github.com/FlyAIBox/fly-wiki/issues/7)。
- Web 优先完成 Knowledge Inbox、冲突四动作、locator 原文定位和一跳 Graph Projection。
- Channel 优先完成 Owner allowlist、显式 Knowledge Base 路由、消息幂等、二维码授权与 token 脱敏。
- 关键指标：非 Owner 消息在调用模型前 100% 拒绝；消息重放零重复；移动端可完成核心审阅。

### M0-F：建立可发布的质量闭环

**结果陈述**：让每次发布都能证明证据、权限、幂等、回滚和观测没有回归。

- [#11](https://github.com/FlyAIBox/fly-wiki/issues/11) 是 #5—#7 的横切工作，不应留到最后一次性补埋点。
- 最后由 [#9](https://github.com/FlyAIBox/fly-wiki/issues/9) 固化八步演示、故障注入、OpenKB 重建和 Langfuse Experiment。
- 完成门槛：M0 子票全部关闭，总票 #1 清单全部勾选，且 [首个里程碑](首个里程碑.md) 的验收标准有可重复证据。

## 5. M1—M3 结果路线图

后续阶段暂不拆实现细节；进入开发前为每个阶段创建一个 Epic Issue，再按可独立验收的纵向切片拆子票。

| 阶段 | Outcome | 候选能力 | 成功信号 | 状态 |
| --- | --- | --- | --- | --- |
| M1 持续追踪与消化 | 让持续领域追踪者只审阅真正影响现有知识的变化，从而减少重复阅读和信息积压 | Watch Rule；RSS/Atom、博客、YouTube；调度与预算；Knowledge Digest；Knowledge Health Finding；Knowledge Inbox 完整化 | 至少 1 个真实 Watch Rule 连续运行 2 周；无实质变化不推送；高优先级 Digest 中 ≥80% 被判断为值得处理；失败可解释且可重试 | 🔵 已规划 |
| M2 采集体验与可携带性 | 让用户在阅读现场完成低摩擦采集，并能离开 FlyWiki 继续使用自己的内容 | WXT 浏览器扩展；模板字段、标签和批注；Obsidian 单向导出；更多 Knowledge Base 管理；备份恢复体验 | 浏览器采集复用同一 Capture Pipeline 且零重复；导出保留 Markdown、附件、元数据和稳定引用；恢复演练通过 | 🔵 已规划 |
| M3 生态扩展 | 让高级用户扩展来源和探索方式，同时保持证据、权限与成本边界 | X BYOK Adapter；全库 Graph Projection 探索；更多 Channel；Knowledge Collection 评估 | 任一新 Adapter 不改变领域真相源；跨库与跨 Workspace 测试通过；成本和失败率可观测；真实使用数据证明探索能力有价值 | 🔵 探索中 |

以下内容不因进入 M1—M3 自动获得优先级：多用户与角色、计费、企业后台、Knowledge Release、Share Link、Visitor Session、全自动修改 Belief、自动删除证据、OpenClaw 运行依赖。它们需要先修改产品基线或新增明确决策。

## 6. 状态跟踪机制

1. **GitHub 是执行真相源**：所有开发项必须有 Issue；本文只保留阶段、结果、依赖和状态快照。
2. **关闭需要证据**：Issue 评论记录测试命令、演示步骤、截图/Trace 或验收报告，再关闭并勾选父票清单。
3. **每周同步一次**：更新本文日期、当前状态表和下一条核心切片；若代码已实现但 Issue 仍 Open，标记为“待验收”，不计为已完成。
4. **依赖优先于并行度**：优先解除 #5 → #4 → #6 这条核心链路；#7 与 #8 只在 grounded chat 稳定后并行。
5. **质量红线优先**：locator、引用完整性、多轮编译保真、Workspace 权限、幂等和回滚失败时暂停发布，修复或收缩范围后重测。
6. **未来阶段按结果开票**：Issue 标题与 Outcome 先说明用户行为变化，再列 Scope、Acceptance criteria、Non-goals 和 Dependencies。

下一次状态更新应发生在 #2 验收关闭，或 #5 开始实施时，以先发生者为准。
