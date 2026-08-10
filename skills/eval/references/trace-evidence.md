# Trace、Evidence 与本地验真合同

> 只有真正记录或验真 case 结果时读取本页。执行循环由 `orchestration.md` 规定；本页只定义可复核的落盘形状与接受门。

## 目录

1. Trace schema
2. Runtime evidence
3. 状态与验真
4. 本地留痕
5. Trace 检查

## 1. Trace schema

每个 case 写入 `traces/<case-key>.json`：

```json
{
  "status": "succeeded",
  "outcome": "最终办成了什么，或为什么停下",
  "steps": [
    {
      "thought": "影响这一步的简短、可公开理由",
      "do": "实际动作；调用 Use 时写名字和关键参数",
      "say": "当时会公开表达的话，可为空",
      "observation": "真实结果及 evidence 引用",
      "operates": [
        {
          "do": "一次底层操作：GUI 写人话动作，shell 写字面命令",
          "output": "stdout/stderr 或界面反应的关键片段（不超过 4000 字符）",
          "ok": true,
          "shot": "<case-key>/03-1.png"
        }
      ],
      "shots": ["<case-key>/03.png"]
    }
  ]
}
```

每个 step 只有 `thought`、`do`、`say`、`observation` 四个字符串字段（至少一项非空），外加可选 `operates`（不超过 50 条/步）与 `shots`（不超过 10 张/步）。调用能力时把能力名、真实参数与结果写入既有字段，不自创 `capability`、`result` 等替代字段，也不用文件引用代替 steps。`thought` 只保存简短公开理由，不索取或保存隐藏思维链。

## 2. Runtime evidence

- **GUI runtime**：每次点击、输入或导航写一条 operate；操作后截图写进该条 `shot`，步末画面写进 `shots`。文件统一放 `evidence/<case-key>/`，trace 中使用相对 `evidence/` 根的路径。
- **CLI / shell**：每条真实命令写一条 operate，`do` 是字面命令，`output` 是 stdout/stderr 关键片段，`ok` 按退出码；完整输出留 `runner-logs/<case-key>.jsonl`。
- **Agent / model**：人物实际 utterance 保持在 `say`，目标完整回复和可见 tool event 原样保存在 observation、runner log 或 evidence，并由 observation 回指。
- **Artifact**：保存人物实际看到的渲染画面或读取形态；图像证据按目标叠加合同回指具体画面、页与区域。

`ok=false` 必须保留。不要把整页源码或整屏日志塞进 observation；原始材料落 evidence / runner log，observation 只保留足以复核结论的事实与引用。

## 3. 状态与验真

状态只用 `succeeded`、`abandoned`、`timeout`、`error`。前三者描述用户路径；`error` 只描述装置或执行环境故障。除 `error` 外每个终态至少一条 step；`succeeded` / `abandoned` 必须有非空 `outcome`。单 case 不超过 scenario / Methodology 预算和 200 个规划步。

主代理接受 trace 前，逐项对照实际工具调用、stdout/stderr、截图、渲染文件或会话事件。只能取得部分独立证据时据此验真并收窄结论；没有独立证据时不得声称“真实使用已通过”。入口、动作、观察、状态或证据不一致的 case 作废，保留原始材料和原因；只有装置可改善时才用干净上下文重跑，不在同一不可观测条件下无限重试。无效 trace 不进入反馈，也不能作为 Loop 已改善的证据。

主代理可以修正契约外枚举和漏字段，但不能润色人物行为与结局。没跑成的 case 用 `error` 占位，不能从 case 列表删除。

## 4. 本地留痕

本地执行阶段新增：

```text
session/
├── preflight.json
├── packets/<case-key>/
├── prompts/<case-key>.md
├── runner-logs/<case-key>.jsonl
├── traces/<case-key>.json
├── evidence/<case-key>/
└── manifest.json
```

`manifest.json` 保存文件路径、SHA-256 与证据引用。`runner-logs/` 保存宿主可见且已脱敏的工具调用、输出、浏览器动作或会话事件；保留实际入口、参数、结果、退出状态和时间，移除隐藏推理、usage 与秘密。

接平台时才按 `cli.md` 机械生成、校验或上传平台请求体；本地 viewer 直接读取 Methodology、case index、traces、evidence 与 feedback，不需要为了本地运行提前造上送材料。

## 5. Trace 检查

- case 数量与 `case-index.json` 同序同长；无结果项以 `error` 占位。
- 每个终态、step、operate、shot 路径和 evidence 文件可复核，runner log 与降级边界已保存。
- 入口和动作与实际工具记录一致；无效执行已隔离，没有当作用户成功。
- 语言遵循 `session.json.language`；真实 say、输入、命令、输出、界面原文与 URL 保持证据原样。
- 文件不含 token、cookie、密码、个人数据、本地 binding、无关源码、usage 或隐藏推理。
