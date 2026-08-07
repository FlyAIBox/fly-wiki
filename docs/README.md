# FlyWiki 文档导航

## 一期基线（product/）

一期研发前置与交付基线全部收敛在 [`product/`](product/) 一个文件夹内，推荐阅读顺序见其 [README](product/README.md)：

- [竞品分析](product/竞品分析.md) — 市场格局、最接近竞品与差异化风险
- [可行性分析](product/可行性分析.md) — 风险、关键假设、R0 实验与 Go/Hold/Stop
- [一期 PRD](product/PRD-FlyWiki-一期.md) — 用户、目标、范围、指标与验收
- [一期产品设计](product/产品设计-FlyWiki-一期.md) — 信息架构、核心流程、状态与异常体验
- [一期产品与技术方案](product/一期产品与技术方案.md) — Module、OpenKB 边界、技术栈、Non-goals 与 Definition of Done

配套统一语言与硬决策：

- [领域词汇表](../CONTEXT.md) — Source、Evidence Span、Claim、Belief 等统一语言（含一期/二期范围标注）
- [架构决策记录](adr/) — OpenKB、证据真相源、工作流运行时和 Workspace 安全边界

## 运行与验收（runbooks/）

- [本地 Compose 骨架验收](runbooks/本地Compose验收.md) — 单命令启动后的手动检查项与期望输出
- [网页采集与 Editable Note 验收](runbooks/网页采集验收.md) — 异步采集、Source Version 与 Note 版本化

## 研究依据与支撑材料

以下文档是一期基线的一手依据，仍然有效：

- [竞品事实底稿](product-research/竞品事实底稿.md) — 截至 2026-08-01 的官方一手竞品事实与限制
- [研发前需求与商业验证问卷](product-research/研发前需求与商业验证问卷.md)
- [图谱与 LLM Wiki 设计](图谱与LLM-Wiki设计.md) — Claim、Evidence 和图谱关系的深入设计材料
- [开源知识库健康能力调研](开源知识库健康能力调研.md) — 健康能力依据
- [开源基座选型分析](开源基座选型分析.md) — OpenKB 底座选型演进记录
- [从想法到研发就绪](methodology/从想法到研发就绪.md) — 可跨项目复用的证据驱动研发前置方法

## 历史演进稿（archive/）

以下文档保留了产品发现与决策演进过程，已被一期基线取代，仅作历史参考，暂不删除。与当前基线冲突时，一律以 `product/` 一期方案、领域词汇表和已接受 ADR 为准。

- [PRD：FlyWiki 认知与证据工作台](archive/PRD-FlyWiki.md)
- [垂直认知顾问 PRD](archive/PRD-FlyWiki-垂直认知顾问.md)
- [历史产品可行性报告](archive/产品可行性报告.md)
- [产品场景定义](archive/产品场景定义.md)
- [MVP 与验证方案](archive/MVP与验证方案.md)
- [历史输出回放：产品可行性报告](archive/历史输出回放-产品可行性报告.md)
- [竞品与真需求验证：自进化知识库](archive/竞品与真需求验证-自进化知识库.md)
- [内容驱动与垂直化调整建议](archive/FlyWiki-内容驱动与垂直化调整建议.md)
- [个人开发者产品方法论：内容驱动](archive/个人开发者产品方法论-内容驱动.md)
