---
status: accepted
---

# 采用 Python 模块化单体与确定性工作流编排

FlyWiki 首发采用 Python 模块化单体仓库，以 FastAPI 提供控制面，以 Celery Beat/API 触发任务、Celery Worker 执行可靠异步工作、LangGraph 表达显式工作流，并在受限节点中通过 LiteLLM 直接执行语义判断。确定性任务、重试、配额、知识变更和通知不交给 Agent；业务后端不使用 OpenClaw、DeepAgents，也不直接采用 OpenAI Agents SDK；首发不引入 Temporal 或微服务拆分。

## Considered Options

- DeepAgents 承担全部工作流：开发直观，但调度、重试、幂等和权限依赖模型行为。
- Temporal：长期耐久工作流能力强，但一期引入新的运行体系和运维成本。
- OpenClaw 或 Hermes Agent 后端：已有定时任务体验，但会把产品耦合到通用 Agent Runtime。
- 微服务：部署隔离更强，但当前规模下接口和运维成本高于收益。

## Consequences

- 同一个 Knowledge Base 的 OpenKB 写入串行，不同 Knowledge Base 可以并行。
- LangGraph 语义节点只有 Workspace 范围内的读取和提案权限；写入和外发必须经过确定性 Module。
- FlyWiki 业务 Module 不直接依赖 OpenAI Agents SDK；OpenKB 上游若包含该传递依赖，只能存在于固定版本的隔离 Worker 中。
- PostgreSQL 是任务和领域状态真相源，Redis 只承担队列、锁、缓存和临时状态。
- 当重试和跨月工作流的复杂度真实超过 Celery 能力时，再以数据评估 Temporal。
