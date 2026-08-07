---
status: accepted
---

# 采用 Python 模块化单体与确定性工作流编排

FlyWiki 首发采用 Python 模块化单体仓库，以 FastAPI 提供控制面，以 Celery Beat/API 触发任务、Celery Worker 执行可靠异步工作，并以 DeepAgents 作为项目统一的智能体框架。DeepAgents 用于研究、综合、冲突分析和 grounded chat 等开放式、多步语义任务；需要自定义状态流时使用其底层 LangGraph。确定性任务、重试、幂等、权限、配额、知识写入、回滚和通知不交给 Agent；业务后端不使用 OpenClaw，也不直接采用 OpenAI Agents SDK；首发不引入 Temporal 或微服务拆分。

业务 Module 只依赖小型 `AgentRuntime` Interface；生产 Adapter 使用 DeepAgents，测试 Adapter 使用可确定复现的 Fake。DeepAgents 只能调用 Capability Gateway 暴露的 Workspace 范围工具，默认不授予 Shell、任意文件系统、直接数据库写入或任意网络访问。

## Considered Options

- DeepAgents 承担全部工作流：开发直观，但调度、重试、幂等和权限会依赖模型行为。
- 只使用 LiteLLM 调用或手写 LangGraph：控制精确，但会重复实现长时程规划、上下文管理、子智能体和 HITL 等 Agent harness 能力。
- Temporal：长期耐久工作流能力强，但一期引入新的运行体系和运维成本。
- OpenClaw 或 Hermes Agent 后端：已有定时任务体验，但会把产品耦合到通用 Agent Runtime。
- 微服务：部署隔离更强，但当前规模下接口和运维成本高于收益。

## Consequences

- 同一个 Knowledge Base 的 OpenKB 写入串行，不同 Knowledge Base 可以并行。
- `AgentRuntime` 是业务 Module 与 DeepAgents 的唯一 Seam；不得在领域代码中散布 `create_deep_agent` 调用。
- DeepAgents Run 只有 Workspace 范围内的读取和提案权限；写入和外发必须经过确定性 Module。
- DeepAgents 的 filesystem、Shell、persistent memory 和 sub-agent 能力按任务显式开启，而不是使用全局默认权限。
- FlyWiki 业务 Module 不直接依赖 OpenAI Agents SDK；OpenKB 上游若包含该传递依赖，只能存在于固定版本的隔离 Worker 中。
- PostgreSQL 是任务和领域状态真相源，Redis 只承担队列、锁、缓存和临时状态。
- 当重试和跨月工作流的复杂度真实超过 Celery 能力时，再以数据评估 Temporal。

## References

- [DeepAgents](https://github.com/langchain-ai/deepagents) — 基于 LangGraph 的 Agent harness、能力与安全边界。
