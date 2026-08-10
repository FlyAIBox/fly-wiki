# Case 派发与执行合同

> 只有真正准备 packet、做 preflight 或派发 case 时读取本页。Persona、Scenario、Methodology 与目标入口应已按规划合同冻结；只写方案时不要读取。

## 目录

1. Preflight 与隔离
2. 真实入口
3. Packet 与子代理指令
4. 执行失败语义
5. 执行检查

## 1. Preflight 与隔离

派发前检查并写入 `preflight.json`：

- 装置能呈现目标真实入口，指纹与 `target.json` 一致；不预先替人物完成任务；
- packet、trace 和 evidence 路径可读写；
- 非零 Local Use 已按 `local-use.md` 在一次性状态副本上成功试跑；零 Use 时跳过；
- 每个 case 有独立 cwd、文件副本、账号与目标页/runtime 要求的状态副本；
- 子代理看不到 analysis、其他 case、历史 feedback、修改方案和无关仓库内容；
- 子代理工具与 persona 现实能力相容；代理有 shell、浏览器或代码能力不等于 persona 会用；
- 目标源码默认只读，除非 scenario 的任务本身就是编辑；
- 可能留存或上传的材料不含凭据与不必要的个人/项目机密。

彼此没有共享可变状态的 cases 才并行，其余排队。cases 超过 3 个且共用同一入口或装置时，先派 1 个探路 case 走完整链路；验真通过再放其余。探路 trace 有效就保留。不能完全隔离时串行，并在每个 case 前恢复到记录过的初态。Preflight 是准备动作，不写进用户 trace。

最小可见范围优先使用独立工作副本。宿主无法真正限制文件访问时，在 prompt 给白名单并在完成后审计工具调用；将这种软隔离写进结论边界。

## 2. 真实入口

真实入口、目标专属 packet、证据形态与步数预算以 SKILL 命中的唯一 `target-*.md` 为准；若有 runtime 叠加合同也同时遵守。

工具不支持目标体验方式时可以降级做更窄验证，但必须同步改写验证问题与结论边界。通过 shell 就记录命令，通过浏览器实际点击才记录点击，通过文本读取不能声称看过渲染效果。若 persona 不会使用唯一入口，应让其真实受阻，不能由执行模型替他跨过知识门槛。

## 3. Packet 与子代理指令

为每个 case 创建 `packets/<case-key>/`，并把最终 prompt 保存到 `prompts/<case-key>.md`。Packet 只放本人的 persona、scenario、共享客观情境、目标、允许能力、可见范围、语言和 trace 路径；不要把 Methodology、analysis、measure、owner 担忧、其他 case 或历史 feedback 交给子代理。

普通使用轨 prompt 以这段为骨架；其他轨道只叠加已加载目标页允许的角色合同：

> 读取本 case packet 中的 persona、scenario、target 和可用能力，从这个人的视角完成 scenario 中的事情。persona 的经历是处境下会自然想起的东西，不是待办清单；用得上的才用。只访问 packet 允许的范围，通过真实入口行动，下一步由你自己判断。不要充当评审，不要补全不存在的内容。把简短公开理由、实际动作、公开反应、真实观察和目标页要求的证据逐步写入指定 trace。办成、自然放弃、预算耗尽或执行环境失败时如实结束；只向主代理返回终态和 trace 路径。

追加工具真实性约束：

> 工具能力不会扩大 persona 的知识和权限。每一步写实际调用的入口与动作；用 shell 就记真实命令，只有实际操作图形界面才能写点击。做不到 persona 会做的真实动作时停止并说明限制，不要换工具代做后宣称用户成功。

再按 `orchestration.md` 追加执行循环要点：

> 每步先观察再决定，多数步只做一件事。动作后核对现场是否变化；没变化就换方法，连续几轮无进展就如实停止这个意图。宣称办成前，对照 scenario 成功条件在当前观察中逐项核实；核不过就继续或放弃，核实到位就立即收尾。

每份 prompt 明写本轮语言：

> 本 case 的叙述使用 <本轮语言>：`thought`、`observation`、`outcome` 用它；人物实际说出的 `say` 与输入保持这个人真会说、真会打的原文。`operates[].do`、输出、命令、URL 与界面文字同样保持证据原样；需要译文时另附并标明。

宿主有原生子代理就用干净上下文，没有就启动无历史新进程。模型可按复杂度分档，但证据与真实性合同不随档位放松。

## 4. 执行失败语义

夹具、runner、代理、网络代理、Local Use 或隔离环境故障记 `error`。测试装置正常时，目标本身打不开、启动失败或返回错误仍是用户路径：按实际进展记 `abandoned`、`timeout`，或人物仍办成时记 `succeeded`。不能用 `error` 把目标问题从反馈里抹掉。

## 5. 执行检查

- 所有 prompts 已保存，packet 没有分析口径、跨 case 或历史信息泄漏。
- Preflight 与用户行为分开；初态、账号、cwd 与可变数据互相隔离。
- 子代理完整遵循 `orchestration.md`，没有借工具能力越过 persona 的现实知识或权限。
- 实际 runner、模型、进程、起止时间与装置限制已记录，不含 usage、秘密或隐藏推理。
