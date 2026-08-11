---
status: accepted
---

# 通过可替换能力 Adapter 接入网页与社交平台采集

FlyWiki 将互联网采集定义为一个小的 `WebFetcher` Interface。Capture Pipeline、幂等、重试、Workspace 授权、Source Version 写入和附件持久化只依赖这个 Interface，不依赖某个 skill、CLI、MCP 服务或 Agent Runtime。

当前代码组合由三个 Adapter 按顺序组成；实际运行时可把这些 Adapter 放在独立的 Agent Reach runtime 或其他能力进程中：

1. `AgentReachSocialFetcher`：小红书、X/Twitter、B站、V2EX、Reddit、Facebook、Instagram 的只读路由；
2. `AgentReachWebFetcher`：Agent Reach skill 规定的通用 Jina Reader 网页路由；
3. `SafeWebFetcher`：FlyWiki 原生 HTTP 与附件回退，继续执行公网 DNS、重定向和大小限制。

Agent Reach 的 skill 文件只由 `DeepAgentsRuntime` 作为虚拟只读文件加载，不进入领域代码。平台命令、URL 解析、登录态要求、输出标准化和版本变化都封装在 Adapter 中；替换 Agent Reach 或改用其他 skill 时，只替换 skill 路径、Adapter 和组合工厂，不修改 Capture Pipeline 或证据模型。

DeepAgents 不直接执行每一次 Capture，也不直接持有 Shell、Cookie、任意网络或数据库写权限。开放式研究任务通过 `AgentRuntime` 调用 DeepAgents；DeepAgents 只获得 Capability Gateway 暴露的 `acquire_source` 工具。Gateway 绑定 Workspace 和 Run，调用同一个确定性采集 Service，并在正文返回给模型前创建不可变 Source Version。用户主动保存 URL 和后台 Watch Rule 仍由 Celery 与确定性 Module 执行。

## Considered Options

- 让 Capture Pipeline 直接调用 Agent Reach CLI：实现快，但 skill 更新、平台命令、登录态和进程失败会泄漏到证据流程。
- 让 DeepAgents 负责整个采集流程：灵活，但重试、幂等、权限和不可变 Source Version 会依赖模型行为，违反 ADR-0003。
- 每个平台直接实现一套 Capture Pipeline：平台能力完整，但会复制幂等、证据、附件和失败处理。

## Consequences

- Agent Reach CLI、OpenCLI、bili-cli、V2EX API 等外部能力只存在于 Acquisition Adapter；测试可使用确定性 Fake。
- 标准 API/Worker 镜像不内置需要用户登录态的 OpenCLI、twitter-cli 或 bili-cli；启用这些平台时，由独立 runtime 提供命令、浏览器会话和凭证。
- 平台专用命令不可用时，路由可以降级到通用网页或安全 HTTP Adapter；不可绕过 Workspace 和 SSRF 约束。
- 社交平台的登录态属于外部运行环境，不进入 Source、普通日志或 Agent 上下文。
- DeepAgents 获得的是受控 Capability，而不是通用 Shell；采集结果仍以不可变 Source Version 作为证据真相源。
