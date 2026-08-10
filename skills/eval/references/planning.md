# 评测规划与本地资产合同

> 在创建 session、目标快照、Persona / Scenario、Methodology 或 case index 时读取本页。只做规划时到本页为止；不要因此加载执行、Trace 或反馈合同。

## 目录

1. Session 与目标快照
2. Persona、Scenario 与 Cases
3. Methodology
4. Local Use 零值门
5. 规划检查

## 1. Session 与目标快照

每次验证使用独立目录，固定建在 `~/.mirasim/eval/sessions/<slug>/`（设置 `MIRASIM_HOME` 时以它替换 `~/.mirasim`；slug 用 `<yyMMdd-HHmm>-<被测物短名>`）。位置是合同的一部分：mirasim 的 eval viewer 只扫描这个约定。规划阶段先创建：

```text
session/
├── request.md
├── session.json
├── target.json
├── methodology.json
├── case-index.json
├── uses.local.json
├── personas/
└── scenarios/
```

后续阶段新增自己的 packet、prompt、runner log、trace、evidence、feedback 与版本文件；不要在规划阶段提前造空结果。

`request.md` 原样保存用户请求。`target.json` 至少记录 primary surface、入口、访问方式、被验证版本、内容指纹和允许子代理读取的范围；文件用 SHA-256，代码优先用 git commit 加工作区 diff，服务记录构建号或部署标识。目标页要求的附加字段也写在这里。

`session.json` 记录 session id、当前轮次、文件清单与哈希、目标版本、实际 runner/model/process 的预期或已知信息，以及 `"status": "local_only"`。另写 `"language": "<语言标签>"`（如 `zh` / `en`）；完整语言判定与哪些字段保持证据原文，以 SKILL.md 为单一真源。不要记录 usage、隐藏推理或秘密，也不要伪造远端 id。

## 2. Persona、Scenario 与 Cases

字段形状在这里，怎么写厚按 `cast.md`。Persona 的三层信息各有归属，同一事实只出现一次：

```json
{
  "name": "清楚可辨认的名字",
  "profile": {"text": "身份锚：恒常取舍、性情与一道让他立体的裂缝。300-500 字"},
  "skills": [
    {"name": "有壁垒的本事", "text": "怎么做到、达到什么效果；首句 40 字内自己站得住"}
  ],
  "memory": {
    "text": "进不了检索键的整体背景，可留空",
    "episodes": [
      {"situation": "会遇到的那类处境", "behavior": "当时真做了什么", "outcome": "留下了什么判断"}
    ]
  },
  "tags": ["稳定检索标签"],
  "status": "active"
}
```

`episodes` 是主力而不是补充：引擎按当前处境只浮现最相关的几条；经历写少才会把行为让给“积极的平均人”。按 `cast.md` 写 6–14 条、一条一事、使用处境词。

Scenario 只描述自然发生的事情，同时也是召回查询：

```json
{
  "name": "任务名称",
  "kind": "task_completion",
  "goal": {"text": "想得到的结果，以及为什么是现在"},
  "env": {"text": "手上材料、时间、已经试过什么、谁在等结果"},
  "closure": {
    "text": "何时结束",
    "success": [{"text": "可观察的成功证据"}],
    "abandon": [{"text": "会自然离开的条件"}],
    "max_turns": 8
  },
  "tags": ["稳定检索标签"],
  "status": "active"
}
```

`kind` 只取 `task_completion` / `open_exploration` / `social_interaction` / `evaluation_probe`。两类资产的 `status` 只取 `draft` / `active` / `archived`。`success` / `abandon` 条目可带机器谓词 `check`，本地通常留空。Scenario 应允许人物走出预想路径；若已暗示按钮、命令、缺陷或答案就重写。`abandon` 为空通常意味着测不出流失。

定稿前运行：

```bash
python3 scripts/check-cast.py <persona.json> --scenario <scenario.json> --target "<被测物名>"
```

`case-index.json` 是本地索引。每项写从 0 开始的 `index`、稳定 `case_key`，以及 persona、scenario、状态副本、Local Use、packet、prompt、runner log、trace 与 evidence 的 session 相对路径。另写本地 `track: "task_user" | "design_review"`；它不是 scenario kind。Persona / Scenario 可以复用，但每个 case 的上下文和可变状态必须独立。

## 3. Methodology

Methodology 是执行与分析合同，不等于评分表。本地使用 `meta.kind="review"`，`execute_by` / `analyse_by` / `report_by` 都为 `caller`：

```json
{
  "meta": {
    "kind": "review",
    "surface": "<已选 primary surface>",
    "domain": "与当前问题相符的领域",
    "goal": "为什么组织这些外部视角",
    "execute_by": "caller",
    "analyse_by": "caller",
    "report_by": "caller",
    "measure": [],
    "report": [],
    "analysis": {
      "questions": ["这次需要回答的问题"],
      "dimensions": ["需要区分的行为或判断差异"],
      "deliverable": "反馈怎样服务当前工作",
      "notes": ""
    }
  },
  "name": "方法论名称",
  "desc": "目的、边界与被验证版本",
  "world": {
    "situation": "所有 case 都能知道的客观开场信息",
    "environment": {"kind": "isolated"},
    "closure": {"max_steps": 12}
  },
  "cases": [
    {
      "persona": "personas/case-a.json",
      "scenario": "scenarios/case-a.json",
      "runtime": {"kind": "shell", "cwd": "/workspace/session/case-a", "uses": []}
    }
  ],
  "tags": ["review", "local"],
  "status": "active"
}
```

`surface` 只取 `app`、`web`、`agent`、`skill`、`model`、`cli`、`document`、`image`。Runtime 描述怎样接触目标，例如 browser 的 `start_url` 或 shell 的隔离 `cwd`；caller 模式下它只是可追溯入口声明。

本地 case 的 `persona` / `scenario` 可以是内联完整对象，也可以是 session 相对 JSON 文件；viewer 两种都能读。不要把分析问题、指标、rubric 或 owner 担忧写进 case packet。`measure` 默认留空；只有比较版本、检查门槛或用户明确要求量化时，才从目标页与验证问题定义可照着判的 judge rubric。接平台后的远端 id、完整 measure/report schema 与 Methodology 校正只按 `cli.md`。

## 4. Local Use 零值门

Local Use 默认是零，写 `{"uses":[]}`。只有至少一个 case 确实需要人物现实中已有、且不绕过被测入口的周边能力时，才按 SKILL 路由读取 `local-use.md` 并生成 contract、binding 与 exposure。规划 packet 时只能暴露 contract/exposure，不能泄露 binding、凭据或内部实现。

## 5. 规划检查

- 用户授权、验证问题、primary surface、目标指纹、语言和结论边界已固定。
- Persona 数量有行为差异依据，经历可召回，人物和事情里没有对目标的评价。
- Scenario 写自然目的、可观察成功与自然放弃，不写操作步骤或 rubric。
- Methodology 的分析只给主代理；case index 顺序、文件引用、状态副本与 track 明确。
- Local Use 为零，或每个非零 Use 都有现实性与非后门理由。
