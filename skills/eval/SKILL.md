---
name: eval
description: 仅在用户明确调用 eval（如 `$eval`、`/eval` 或“使用 eval”）时启用。让彼此隔离的外部用户通过真实入口使用指定目标，留下可追溯行为证据；视觉创作成品另加独立开放式设计评审。按用户授权停在反馈，或修改并持续复验。一般性的评审、测试或优化请求不得自动触发。
---

# eval

## 核心职责

把当前工作交给相关外部人物真实使用，观察他们理解了什么、怎样选择、在哪里受阻，再让主代理据证据反馈或改进。使用轨里的子代理只办自己的事，不替用户打分；视觉设计评审是独立角色，不能揉进自然用户。

仿真与分析默认只在本地完成。除非用户在本次对话明确要求“接平台 / 传到 mirofish / 留档到平台 / 复用平台资产”，否则不探测、不安装、不登录、不检索、不回写 mirofish，状态记 `local_only`。

## 1. 先固定授权与语言

从用户原话判断深度，不擅自升级：

- **只评测**：运行一轮，交付反馈，不改目标。
- **优化或修复**：先取外部证据，再修改并用干净上下文复验。
- **持续改进 / 达到结果**：循环到证据足够、边际信息耗尽，或只剩用户必须决定的取舍。

只有缺失信息会改变目标、授权或结果解释时才追问。

**本技能自己是中文写的，那是给你的指令，不是产出语言。** 本轮人读内容的语言依次取：用户明确指定 → 本次对话语言 → 目标受众语言。写入 `session.json.language`，整轮保持一致。Persona、scenario、prompt、`thought`、`observation`、`outcome`、feedback 与 `ab.md` 使用该语言；字段名与 `status` 等枚举值、`case_key`、文件名，以及人物实际说出的 `say`、真实输入、命令、stdout/stderr、URL、界面原文和 `request.md` 保持原样，必要时另附并标明译文，不覆盖证据。

## 2. 先按验证问题路由目标

先写一句真正要回答的问题，并固定目标版本、真实入口、可见环境和完成证据。**按这轮要验证的人类接触方式选 primary surface，不按文件扩展名或承载界面选。** 例如：通过网页与 Agent 对话，目标仍是 `agent`；只评网站截图的视觉呈现，则是 `image`。

判定 surface 后，**只完整读取命中的目标页，不预读、扫描或搜索其他 `target-*.md`**：

| Primary surface | 只读这一目标页 | 判定边界 |
|---|---|---|
| `web` | [references/target-web.md](references/target-web.md) | 验证网页里的用户任务与交互 |
| `app` | [references/target-app.md](references/target-app.md) | 当前本地 case 禁派；读完即按其边界停止 |
| `agent` / `model` | [references/target-conversation.md](references/target-conversation.md) | 验证对话与 Agent 行为，即使入口是网页或 CLI |
| `skill` / `cli` | [references/target-tool.md](references/target-tool.md) | 验证安装、上手与真实命令工作流 |
| `document` / `image` | [references/target-artifact.md](references/target-artifact.md) | 验证最终成品的理解、决定与转手使用 |

目标确实横跨多个独立 surface 时，为每个 surface 分开 Methodology / run，再综合反馈；只读取实际在本轮范围内的目标页。不要因为一个产品“也有”其他入口就把所有目标规则一起加载。

目标与 runtime 分两轴处理：

- 实际通过浏览器行动时，再读 [references/browser.md](references/browser.md)；`web` 必读，网页里的 Agent 也读，但后者不加载 `target-web.md`。
- `image`，以及视觉表达承载信息或要求“好看 / 专业 / 可发布 / 可演示”的 `document`，再读 [references/design-review.md](references/design-review.md)。纯文字且呈现不影响决定的文档不读。
- `app` 命中目标页的禁派边界后，不再加载执行协议或组装伪 case。

## 3. 再按阶段加载公共合同

只在条件命中时读取对应文件；禁止为“了解全貌”把 references 目录整批打开：

| 条件 | 读取 |
|---|---|
| 开始写 persona / scenario | [references/cast.md](references/cast.md) |
| 创建 session、目标快照、Methodology 或 case index | [references/planning.md](references/planning.md) |
| 写 packet / preflight / prompt，准备派发 case | [references/execution.md](references/execution.md) |
| 真正派发并执行至少一个 case | [references/orchestration.md](references/orchestration.md) |
| 记录或验真 trace、evidence、runner log | [references/trace-evidence.md](references/trace-evidence.md) |
| 综合已验真 traces、写 feedback 或交付本地 run | [references/feedback.md](references/feedback.md) |
| 至少一个 case 确实需要非零 Local Use | [references/local-use.md](references/local-use.md) |
| 用户已授权修改目标 | [references/loop.md](references/loop.md) |
| 仓库目标需要盘点真实产品能力，或装置缺能力 | [references/equip.md](references/equip.md) |
| 用户要求引导配置，或接受了引导提议 | [references/guided.md](references/guided.md) |
| 用户明确要求接 mirofish 平台 | [references/cli.md](references/cli.md) |

规划、执行、证据与反馈是四个独立阶段；不要因为最终可能会运行，就在只做方案时预读后三阶段。目标任务、专属证据和失败模式以已经命中的目标页为准。

## 4. 把请求变成真实 cases

1. 找出哪些人物差异会改变理解、路径、约束或最终选择；每个有行为依据的差异形成一个 persona 假设。
2. 给每个人一件自然发生的事。Scenario 只写目的、客观处境、可观察成功与自然放弃条件，不写步骤、疑似缺陷、rubric 或正确答案。
3. 视角数由仍待回答的不确定性决定；窄问题可只有一个 case，复杂问题可到个位数或十几个。不要凑固定人数或正反例。
4. 默认本地新造完整资产；只有用户明确接平台时才按 `cli.md` 检索和复用。

Persona 以可召回的具体经历为主，不能只换职业标签。动笔前完整读取 `cast.md`，并在定稿前运行：

```bash
python3 scripts/check-cast.py <persona.json> --scenario <scenario.json> --target "<被测物名>"
```

每个 case 使用独立子代理或无历史新进程，只给本人的 persona、scenario、共享客观情境、目标入口、必要能力、可见范围和 trace 合同。不给 analysis、measure、owner 担忧、其他 case、历史 feedback 或修改意图。

## 5. 真实运行与验真

能打开就真打开，能运行就真运行，能看就保存实际画面。拿源码、想象、替代入口或主代理环境冒充真实体验会让整轮作废；只能降级时同时收窄验证问题与结论边界。

子代理有工具不等于 persona 会用。只能执行人物现实中会做的动作，也不能用 Local Use 绕过正在验证的入口。工具或环境失败记 execution error，不写成用户放弃。

主代理逐项对照实际工具记录、输出、截图或会话事件验真 trace。入口、动作、观察、状态或证据不一致的 case 作废；环境可改善时用干净上下文重跑，无独立证据时不得声称“真实使用已通过”。

## 6. 反馈与修改

只有开始综合已验真 traces 时才读取 `feedback.md`；按它区分事实、专业判断、解释、未知与装置限制，并把产品需求和实现方案分开。

只有已获得修改授权才读取并执行 `loop.md`。修改前保存版本与指纹，所有可执行 finding 进入处置账，修改后用新上下文复验；不得把“建议提了但没追踪”或固定人物任务饱和伪装成收敛。视觉目标还叠加 `design-review.md` 的高优 finding 与收敛门。

## 7. 留痕与交付

Session 固定放在 `~/.mirasim/eval/sessions/<yyMMdd-HHmm>-<目标短名>/`（设置 `MIRASIM_HOME` 时替换根目录）。各阶段只保存自己实际产生的规划资产、prompt、原始 trace、runner log、evidence 与 feedback；Loop 另存版本和 diff。`bundle.json` 只在用户明确接平台时按 `cli.md` 生成。本地交付按 `feedback.md`。

## 不可妥协

- Trace 忠实描述实际入口、动作、观察与终态；不索取或保存隐藏思维链，`thought` 只留简短公开理由。
- 保存外部可复核证据；没有真实画面、输出或往返时，不作超出证据的体验结论。
- 上传前清理 token、cookie、密码、个人数据、本地 binding、无关源码和隐藏推理；脱敏秘密，不美化行为。
- 仿真人物和专业 reviewer 都只是证据视角，最终取舍仍属于用户和主代理。
