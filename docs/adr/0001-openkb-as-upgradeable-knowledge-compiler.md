---
status: accepted
---

# 以可升级的 OpenKB 编译器作为知识底座

FlyWiki 使用 VectifyAI/OpenKB 负责 Knowledge Base 的 Wiki 编译、原生图谱和基础 Lint，但不把 OpenKB 内部页面模型扩展成整个平台数据库。FlyWiki 通过独立进程中的 `OpenKBAdapter` 调用精确固定版本的 OpenKB，并以独立 `openkb-evidence` 扩展保存 Evidence Span、Claim 和类型化关系；对 OpenKB 的修改仅限通用扩展钩子并优先向上游贡献。Source Version 和证据数据是可重建 OpenKB Workspace 的真相源，因此升级前可以重建、对比和回退。

此决策覆盖《开源基座选型分析》中“P0 以 WeKnora 作为上游知识服务、OpenKB 仅作实验基线”的历史建议。WeKnora 继续作为 IM、分享、连接器、多租户、健康检查和运维体验的实现参考，不作为 FlyWiki 后端运行依赖。

## Considered Options

- 深度 fork OpenKB：初期直接，但会扩大升级冲突并把平台领域模型耦合到 Markdown 页面。
- 使用 WeKnora 作为核心：平台能力成熟，但与统一 Python 技术栈和用户指定的 OpenKB 基础不符。
- 自研知识编译器：控制力最高，但会重复 OpenKB 已有能力并延迟一期交付。

## Consequences

- 只有 `OpenKBAdapter` 和 `openkb-evidence` 可以依赖 OpenKB 内部接口。
- OpenKB 原生结构 Lint 直接复用；语义 Lint 只产生候选问题。
- CI 同时验证固定版本、最新稳定版和主分支兼容性，只有固定版本失败会阻断发布。
