# FlyWiki

FlyWiki 把持续进入的资料编译为可追溯知识，比较新旧证据，并帮助用户判断哪些内容是新增、强化、冲突或需要认知更新。本词汇表规定产品、领域模型和交互共同使用的语言。

> **首发范围标注**：执行者为个人开发者 + AI 辅助。首发是单用户自托管产品，但所有领域对象仍受 Workspace 隔离。标注 `（后续）` 的术语保留领域定义与数据结构边界，但不进入首个可演示闭环。

## 所有权与范围

**Workspace**:
用户、数据、权限、配额和审计的最高隔离单元。一个 Workspace 可以包含多个 Knowledge Base。
_Avoid_: Tenant、空间账户

**Knowledge Base**:
围绕一组资料、知识页和图谱形成的独立知识集合。每个 Knowledge Base 只属于一个 Workspace。
_Avoid_: 项目、Vault、OpenKB Workspace

**Knowledge Collection**:
只读聚合多个 Knowledge Base 查询结果的虚拟集合，不改变各 Knowledge Base 的所有权和编译边界。
_Avoid_: 合并库、跨库复制

## 来源与证据

**Source**:
同一外部资料在系统中的逻辑身份，例如一篇网页、一份文件或一期播客。Source 本身不承载会变化的正文。
_Avoid_: Document、Knowledge、素材

**Source Version**:
Source 在某次采集时形成的不可变内容快照。网页 Source Version 默认保存原始 HTML、清洗 Markdown、元数据、下载附件与 locator 映射；后续重新抓取会创建新版本，不覆盖旧版本。
_Avoid_: 当前文件、最新版正文

**Editable Note**:
从 Source Version 派生、由用户编辑并独立版本化的 Markdown 内容。它可以参与知识编译，但不得覆盖或冒充原始证据。
_Avoid_: 原文、Source Version、富文本块

**Evidence Span**:
Source Version 中可精确定位和复核的最小证据片段，包含原文及页码、时间码、行号或网页范围等定位信息。
_Avoid_: Fragment、Chunk、引用文本

**Claim**:
可以被证据支持、反驳、限制或替代的可判断陈述。Claim 必须明确适用时间、对象和条件。
_Avoid_: 观点、结论、知识点

**Evidence Relation**:
Evidence Span 对 Claim 产生的有方向语义关系，包括支持、反驳、限制、补充和替代。
_Avoid_: 相关关系、相似度

## 系统知识与个人认知

**Compiled Knowledge**:
系统根据 Source Version、Claim 和 Evidence Relation 生成的当前知识表达，包括知识页、主题结构和图谱。它可以自动更新，但不代表用户已经接受。
_Avoid_: 我的知识、事实真相、Belief

**Graph Projection**:
从 Claim、Evidence Span、Evidence Relation 和 Compiled Knowledge 生成的可重建关系视图。图数据库、布局和可视化都不是唯一真相源。
_Avoid_: 事实主库、唯一知识图谱

**Knowledge Delta**:
新 Evidence Span 或 Claim 相对当前 Compiled Knowledge 与 Belief 的可解释比较结果。数据模型保留新增、强化、限制、冲突、替代、重复和低价值七类枚举；产品面向用户收敛为四分类：世界新知识（新增）、可能需要认知更新（限制/冲突/替代）、强化、值得阅读/忽略（重复/低价值）。它描述发生了什么变化，不代表用户必须改变认知。
_Avoid_: 更新消息、认知结论、自动纠正

**Knowledge Digest**:
按主题和优先级组织的一组 Knowledge Delta，附带依据、影响对象和建议动作，可按计划或重大事件推送给用户审阅。
_Avoid_: 资讯摘要、消息列表、自动认知更新

**Belief**:
用户明确表达或确认过的个人判断及其适用边界。首发最简形态：Belief 由 Workspace Knowledge Status 的“接受”状态直接承担——用户对某个 Claim 标记接受，该 Claim 即成为其 Belief。系统只能提出修改建议，不能自动改变 Belief。
_Avoid_: 用户画像、系统结论、推断认知

**Profile Document**（后续）:
用户可编辑、可版本化的身份、兴趣、记忆或认知记录。首发不设独立 Profile Document 体系，其职责由 [[Belief]] 的最简形态承担。
_Avoid_: 隐式画像、长期 Prompt

**Change Proposal**:
新证据或系统分析对 Compiled Knowledge 或 Belief 提出的候选变化，尚未获得用户确认。
_Avoid_: 自动更新、事实修正

**Knowledge Change Set**:
一次可审阅、可审计和可回滚的知识修改集合，记录修改前后、触发原因、依据和执行结果。
_Avoid_: 自动修复、直接写入

**Knowledge Inbox**:
集中呈现 Change Proposal、健康问题和异常任务的待处理视图。它是处理入口，不是新的知识存储。（访客投稿与记忆候选属于后续范围。）
_Avoid_: 消息中心、通知列表

## 追踪、消化、研究与发布

**Watch Rule**:
用户明确配置的持续追踪规则，规定主题、来源、频率、过滤条件、预算和目标 Knowledge Base。
_Avoid_: 爬虫任务、订阅关键词

**Research Session**（后续）:
围绕一个问题临时组合 Knowledge Release、联网资料和访客附件的研究工作区。临时资料不会自动进入所有者的 Knowledge Base。
_Avoid_: 聊天会话、共享知识库

**Writing Artifact**（后续）:
在可信写作流程中形成的提纲、草稿或成稿，保存事实主张、推论、创作内容和引用之间的关系。
_Avoid_: AI 回答、Evidence Pack

**Trusted Version**（后续）:
Writing Artifact 通过 Claim—Citation Audit 后形成的版本。它表示引用门禁已通过，不表示平台对所有事实作绝对真实性担保。
_Avoid_: 真实版本、可信分数

**Knowledge Release**（后续）:
Knowledge Base 用于分享和查询的不可变发布快照。新的发布原子替换默认指针，旧发布可保留、回退或被强制下架。首发知识回滚由 [[Knowledge Change Set]] 承担，不依赖 Release 快照。
_Avoid_: 当前 Wiki、公开库、Share

## 渠道与访问

**Channel**:
把外部通信系统的收发能力规范化为 FlyWiki 消息的传输 Adapter。Channel 只负责身份、消息和投递，不承担 Agent、知识编译或 Workspace 所有权。
_Avoid_: OpenClaw、Agent Runtime、知识库后端

**Channel Principal**:
微信、飞书或其他通信渠道中可被识别的外部身份。它必须绑定平台账号，不能单独拥有 Workspace。
_Avoid_: 用户账号、联系人

**Channel Binding**:
Workspace Owner、Channel Principal、默认 Knowledge Base、会话范围和授权能力之间的可撤销关系。首发微信绑定仅允许 Owner 本人，并通过显式指令切换 Knowledge Base。
_Avoid_: 登录、好友关系

**Edge Device**（后续）:
运行在用户设备上的受限本地连接器，负责本地文件同步和设备密钥保管，不运行通用 Agent。首发自托管服务直接承载 WeixinChannel，不另设 Edge Device。
_Avoid_: OpenClaw、桌面 Agent、客户端机器人

**Share Link**（后续）:
指向一个 Knowledge Release 的可撤销、不可猜测且默认不被索引的访问入口。
_Avoid_: 公开网址、文件分享

**Visitor Session**（后续）:
匿名或已登录访客在 Share Link 下进行查询、研究和写作的隔离会话。访客产出不修改所有者知识库。
_Avoid_: 协作编辑、共享 Workspace

## 健康与治理

**Knowledge Health Finding**:
针对引用、来源新鲜度、冲突、结构或编译状态发现的可解释问题（首发不含发布健康）。Finding 必须指向具体对象和建议动作。
_Avoid_: 健康分、可信分、告警日志

**Evidence Status**:
Claim 在证据层的当前状态，包括无支持、单一来源、相互印证、有争议和已被替代。
_Avoid_: 置信度、真实性概率

**Workspace Knowledge Status**:
用户对某个 Claim 的认知状态，包括未知、已见、接受、拒绝和已被替代。
_Avoid_: Evidence Status、阅读进度
