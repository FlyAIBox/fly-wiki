---
status: accepted
date: 2026-08-06
---

# 采用原生消息 Channel，并以微信作为首个实现

FlyWiki 定义自己的 `Channel` 端口，不把 OpenClaw 或其他通用 Agent Runtime 作为运行依赖。首个实现 `WeixinChannel` 参考 OpenClaw 的 Gateway/Channel 分层，直接适配腾讯微信 iLink Bot 协议，通过二维码完成授权。Channel 只规范化身份、入站消息、出站消息和投递状态；知识库路由、权限、会话、采集、编译与问答仍由 FlyWiki 领域 Module 负责。

首发只允许 Workspace Owner 本人使用微信私聊。每个 Channel Binding 绑定一个默认 Knowledge Base；切换目标库必须由用户显式执行，模型不得猜测写入目标。链接提交采用即时确认、后台异步处理和完成/失败通知，同一消息与同一 Source Version 必须幂等。

## Considered Options

- 依赖 OpenClaw 运行：可直接利用现成 Gateway，但会把知识产品生命周期、权限与会话耦合到通用 Agent Runtime。
- 使用个人微信非官方逆向协议：接入面更自由，但账号风险和维护成本不可控。
- 微信小程序：官方且稳定，但不符合“把微信作为日常消息 Channel”的交互目标。
- 以微信身份作为根账号：登录简单，但渠道失效会危及 Workspace 所有权与恢复。

## Consequences

- 业务代码只依赖 FlyWiki 的 Channel 端口；微信协议实现位于 Adapter。
- 微信登录凭证只保存在自托管实例的加密 Secret Store，不进入导出包、日志或模型上下文。
- 非 allowlist 身份的消息在调用模型和访问知识前拒绝。
- 普通文本进入默认 Knowledge Base 的 grounded chat；公众号或公开网页链接进入默认 Knowledge Base 的 Capture Pipeline。
- 新增飞书、Telegram 等入口时复用相同端口，不改变知识领域模型。
- OpenClaw 可作为实现参考和互操作对象，但不是部署前置条件。

## References

- [Tencent/openclaw-weixin](https://github.com/Tencent/openclaw-weixin) — 腾讯微信团队维护的 OpenClaw Channel 与 iLink Bot 协议说明。
- [OpenClaw Chat channels](https://docs.openclaw.ai/channels) — Gateway/Channel 分层与微信外部插件定位。
