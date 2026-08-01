# FlyWiki

FlyWiki 把持续进入的资料编译为可追溯知识，并帮助用户在研究、判断和写作时区分事实依据、系统推论与个人认知。本词汇表规定产品、领域模型和交互共同使用的语言。

## 所有权与范围

**Workspace**:
用户、数据、权限、配额和审计的最高隔离单元。一个 Workspace 可以包含多个 Knowledge Base。
_Avoid_: Tenant、空间账户

**Knowledge Base**:
围绕一组资料、知识页、图谱和发布版本形成的独立知识集合。每个 Knowledge Base 只属于一个 Workspace。
_Avoid_: 项目、Vault、OpenKB Workspace

**Knowledge Collection**:
只读聚合多个 Knowledge Base 查询结果的虚拟集合，不改变各 Knowledge Base 的所有权和编译边界。
_Avoid_: 合并库、跨库复制

## 来源与证据

**Source**:
同一外部资料在系统中的逻辑身份，例如一篇网页、一份文件或一期播客。Source 本身不承载会变化的正文。
_Avoid_: Document、Knowledge、素材

**Source Version**:
Source 在某次采集时形成的不可变内容快照。后续重新抓取会创建新版本，不覆盖旧版本。
_Avoid_: 当前文件、最新版正文

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

**Belief**:
用户明确表达或确认过的个人判断及其适用边界。系统只能提出修改建议，不能自动改变 Belief。
_Avoid_: 用户画像、系统结论、推断认知

**Profile Document**:
用户可编辑、可版本化的身份、兴趣、记忆或认知记录。
_Avoid_: 隐式画像、长期 Prompt

**Change Proposal**:
新证据或系统分析对 Compiled Knowledge、Belief 或 Profile Document 提出的候选变化，尚未获得用户确认。
_Avoid_: 自动更新、事实修正

**Knowledge Change Set**:
一次可审阅、可审计和可回滚的知识修改集合，记录修改前后、触发原因、依据和执行结果。
_Avoid_: 自动修复、直接写入

**Knowledge Inbox**:
集中呈现 Change Proposal、健康问题、访客投稿、记忆候选和异常任务的待处理视图。它是处理入口，不是新的知识存储。
_Avoid_: 消息中心、通知列表

## 研究、写作与发布

**Watch Rule**:
用户明确配置的持续追踪规则，规定主题、来源、频率、过滤条件、预算和目标 Knowledge Base。
_Avoid_: 爬虫任务、订阅关键词

**Research Session**:
围绕一个问题临时组合 Knowledge Release、联网资料和访客附件的研究工作区。临时资料不会自动进入所有者的 Knowledge Base。
_Avoid_: 聊天会话、共享知识库

**Writing Artifact**:
在可信写作流程中形成的提纲、草稿或成稿，保存事实主张、推论、创作内容和引用之间的关系。
_Avoid_: AI 回答、Evidence Pack

**Trusted Version**:
Writing Artifact 通过 Claim—Citation Audit 后形成的版本。它表示引用门禁已通过，不表示平台对所有事实作绝对真实性担保。
_Avoid_: 真实版本、可信分数

**Knowledge Release**:
Knowledge Base 用于分享和查询的不可变发布快照。新的发布原子替换默认指针，旧发布可保留、回退或被强制下架。
_Avoid_: 当前 Wiki、公开库、Share

## 渠道与访问

**Channel Principal**:
微信、飞书或其他通信渠道中可被识别的外部身份。它必须绑定平台账号，不能单独拥有 Workspace。
_Avoid_: 用户账号、联系人

**Channel Binding**:
平台账号、Channel Principal、会话范围和授权能力之间的可撤销关系。
_Avoid_: 登录、好友关系

**Edge Device**:
运行在用户设备或私有服务器上的受限本地连接器，负责本地文件同步、个人微信接入和本地密钥保管，不运行通用 Agent。
_Avoid_: OpenClaw、桌面 Agent、客户端机器人

**Share Link**:
指向一个 Knowledge Release 的可撤销、不可猜测且默认不被索引的访问入口。
_Avoid_: 公开网址、文件分享

**Visitor Session**:
匿名或已登录访客在 Share Link 下进行查询、研究和写作的隔离会话。访客产出不修改所有者知识库。
_Avoid_: 协作编辑、共享 Workspace

## 健康与治理

**Knowledge Health Finding**:
针对引用、来源新鲜度、冲突、结构、编译或发布状态发现的可解释问题。Finding 必须指向具体对象和建议动作。
_Avoid_: 健康分、可信分、告警日志

**Evidence Status**:
Claim 在证据层的当前状态，包括无支持、单一来源、相互印证、有争议和已被替代。
_Avoid_: 置信度、真实性概率

**Workspace Knowledge Status**:
用户对某个 Claim 的认知状态，包括未知、已见、接受、拒绝和已被替代。
_Avoid_: Evidence Status、阅读进度
