---
status: accepted
---

# 以 Workspace 作为唯一租户与安全边界

FlyWiki 从第一天以 Workspace 隔离数据、权限、配额、密钥和审计，暂时提供单用户体验但不另设重复的 Tenant 概念。平台账号是根身份；个人微信、飞书和 Edge Device 只形成可撤销 Channel Binding。匿名 Share Link 只授予特定 Knowledge Release 的读取、查询和 Visitor Session 写作能力，访客不能修改所有者 Knowledge Base。

## Considered Options

- 先做全局单用户表，后期迁移多租户：早期更快，但关键表和对象键迁移风险高。
- 以微信或飞书身份作为主账号：登录方便，但渠道失效、换机或离职会导致所有权和恢复问题。
- 共享实时知识库：协作直接，但无法保持发布快照、证据门禁和所有者控制。

## Consequences

- 所有 Workspace 资源使用包含 `workspace_id` 的组合外键，并由 PostgreSQL RLS 与应用层共同约束。
- Celery 任务携带签名执行上下文，Capability Gateway 在每次调用时重新授权。
- 个人微信凭证只保存在 Edge Device 的系统密钥库，云端不集中保存。
- 分享默认不展示或下载原始资料；访客附件属于 Visitor Session，只有提交并获接受后才能进入所有者知识库。
