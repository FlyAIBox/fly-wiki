---
status: accepted
date: 2026-08-06
---

# 以自托管 Langfuse 作为智能体观测与评估面

FlyWiki 首发部署固定版本的自托管 Langfuse，统一记录从 Channel 入站、Capture Pipeline、OpenKB 编译、检索、DeepAgents Run、模型与工具调用、引用审计、Knowledge Change Set 到消息投递的关键链路。Langfuse 负责 tracing、调试、成本与延迟分析、人工标注、Scores、Datasets 和 Experiments；PostgreSQL 仍是任务与领域状态真相源，Langfuse 故障不得阻断核心业务或改变知识状态。

每个用户意图或后台任务形成一个稳定命名的 Trace；检索、Agent、LLM、tool、citation audit 和 delivery 形成 Observation。Trace 使用 `workspace_id`、`knowledge_base_id`、任务类型、版本和幂等键关联，但默认不记录完整私密正文、微信凭证、API Key、Secret、未脱敏聊天或附件。自托管遥测默认关闭。

## Evaluation contract

- 线上 Scores：任务成功、引用覆盖、locator 有效、groundedness、工具拒绝、用户反馈、成本与延迟。
- 离线 Datasets：grounded chat、Knowledge Delta 分类、冲突边界、工具授权和引用审计的固定案例。
- Experiments：比较模型、Prompt、DeepAgents 配置、检索和代码版本；回归超过门槛时阻断发布。
- 人工标注与自动评估都保存评分方法和版本，LLM-as-a-Judge 不能替代确定性引用与权限检查。

## Considered Options

- 只使用普通日志与 OpenTelemetry Collector：运行诊断足够，但缺少面向 LLM 的 Scores、Datasets、Experiments 和标注工作流。
- 使用 DeepAgents 官方优先推荐的 LangSmith：框架集成自然，但与已确认的自托管、开源观测栈选择不一致。
- 同时把 Langfuse 当任务数据库：减少存储种类，但会让观测系统进入业务正确性路径。

## Consequences

- Langfuse SDK/OTel 调用集中在 `Observability` Module，业务调用者只提交稳定事件语义，不了解 Langfuse 数据模型细节。
- 提供 No-op Adapter，Langfuse 不可用时业务继续运行并报告观测降级。
- Trace/Observation 名称视为评估 Interface，修改时必须迁移 Dashboard、Evaluator 和 Dataset 过滤规则。
- 生产默认脱敏并限制保留期；测试 Dataset 只使用获许可、脱敏或合成内容。
- Langfuse、ClickHouse 与其依赖使用固定版本和持久卷，默认不暴露公网端口。

## References

- [Langfuse](https://github.com/langfuse/langfuse) — 自托管 LLM observability 与 evaluation 平台。
- [Langfuse Observability](https://langfuse.com/docs/observability/overview)
- [Langfuse Evaluation](https://langfuse.com/docs/evaluation/overview)
