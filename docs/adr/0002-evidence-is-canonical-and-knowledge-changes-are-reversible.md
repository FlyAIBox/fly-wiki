---
status: accepted
---

# 以不可变证据为真相源并保证知识变更可逆

FlyWiki 以不可变 Source Version 和 Evidence Span 作为事实依据，以 Claim 和 Evidence Relation 表达系统知识，以 Belief 表达用户确认认知。OpenKB 知识页、图谱视图、摘要、报告和搜索索引都是可重建派生物；任何自动维护只能产生可审计、可回滚的 Knowledge Change Set，不能自动删除原始资料、解除证据关系、改变 Belief 或发布 Knowledge Release。

## Considered Options

- 以最新 Wiki 页面作为真相源：实现简单，但整页重写会丢失证据、冲突和历史边界。
- 允许 Agent 直接维护知识库：自动化程度高，但权限、回滚和审计不可控。
- 用综合可信分排序和门禁：界面简洁，但掩盖来源、覆盖、时效与冲突的不同问题。

## Consequences

- 重新抓取 Source 只创建新 Source Version，旧引用永久指向旧版本。
- 世界知识可以自动更新，个人 Belief 只能由用户确认更新。
- 健康中心展示可解释维度和问题清单，不展示单一可信分。
- Knowledge Release 原子发布；失败构建保留上一个可用版本，强制下架可立即覆盖历史访问。
