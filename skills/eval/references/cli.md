# mirofish CLI：资产复用与本地 Trace 留档

> **本页默认整页不用。** eval 默认全程不碰 mirofish CLI——不探测、不安装、不登录、不检索、不回写，本地 session 就是完整留痕。**只有用户在本次对话里明确要求**接平台（"传到 mirofish / 留档到平台 / 复用平台资产"）时才读本页并按它执行；用户没提就到此为止，别把"CLI 没装"当成待办或缺陷报给用户。

仿真和分析始终在本地。CLI 只负责资产、trace、反馈和迭代谱系的可追溯副本；本技能不使用 `mirofish runs submit`。

## 目录

1. 接入与安装
2. 检索和创建资产
3. 物化本地运行包
4. 上传前检查
5. 首次上送与读回
6. 修订与新版本
7. 离线 Session 恢复

## 1. 接入与安装

用户要求接平台之后才走这一节（没要求就一步都不做）。先运行技能自带的接入脚本（本 Skill 目录下 `scripts/ensure-cli.sh`，用绝对路径执行——宿主的当前目录通常不在技能目录）：

```bash
sh <本技能目录>/scripts/ensure-cli.sh
```

它按「`MIROFISH_BIN` → PATH 上已装/开发版 → 从固定地址安装」的顺序解析 CLI，只装缺失、绝不覆盖本地已有版本；固定地址默认 `https://api.mirofish.ai/connect/cli.tgz`，可用 `MIROFISH_CLI_URL` 覆写。脚本成功后：

```bash
mirofish doctor --json
```

未登录时运行 `mirofish auth login --base <地址>`（或 `--with-token` 粘贴平台连接器页新建的访问令牌）。

**不要在 mirasim 宿主里运行 `mirofish skills install`**：本 skill 随 mirasim 内置并由它自动升级（指纹门控），CLI 再装一份会盖掉安装标记、挡住后续自动升级。只有在非 mirasim 宿主（裸 Claude / Codex）里才需要 `mirofish skills install --agent both` 补装。

连接失败不阻塞本地仿真。保持完整 session，把 `session.json` 标为 `pending_upload`；不要编造资产 id 或 run id。

## 2. 检索和创建资产

先用“受众/目标 + 任务 + 关键约束”检索，brief 只用于筛选，确认复用前读全文：

```bash
mirofish grep "<关键词>" --kind personas --json
mirofish grep "<关键词>" --kind scenarios --json
mirofish grep "<关键词>" --kind methodologies --json
mirofish grep "<关键词>" --kind uses --json

mirofish personas get <id> --brief
mirofish scenarios get <id> --brief
mirofish methodologies get <id> --brief

mirofish personas get <id>
mirofish scenarios get <id>
mirofish methodologies get <id>
mirofish uses get <id>
```

职业名或标题相似不代表可复用；行为逻辑、目标、处境和收束口径都要贴合。创建新的可复用资产——**已登录时资产定稿即创建**（生成 persona/scenario/methodology 的当下就落库拿远端 id，不要攒到仿真跑完再补录）：

```bash
mirofish personas create -f persona.json --json
mirofish scenarios create -f scenario.json --json
mirofish methodologies schema > methodology-schema.json
mirofish methodologies create -f methodology.json --json
mirofish uses schema > use-schema.json
mirofish uses create -f use.json --json
```

把返回 id 写入 `session.json` 的映射，并用远端 id 组装最终 Methodology。三个归属轴必须都是 `caller`；Methodology 的 `measure` 可以为空。

`mirofish uses schema` 是当前 CLI 对后端 `UseCreate`/`UseRef` 的契约投影，不是服务端动态 schema；Methodology 与 ingest 仍以服务端 schema 为权威。Local Use binding 不上传。只有存在真实 platform-compatible `impl`（已注册 ref 或适合在平台执行的 code）时，才能创建平台 Use 并由 Methodology Runtime 通过 `UseRef` 记录。只有本机 command binding 时就把 contract、binding 与 exposure 留在本地 session；不伪造 `impl`，也不为了留档上传本地代码。

平台 Methodology 与本地规划相比，多出这些精确合同：

- case 的 persona/scenario 可以使用 `persona_id` / `scenario_id`，也可以分别以内联 `persona` / `scenario` 给完整对象；每侧恰取一种，不能都给或都缺。远端引用必须是真实返回的 id。
- `runtime.uses` 只写已存在的 `UseRef`：`{"use":"use_...","params":{...}}`，可选 `artifact` 填该 use 声明的资源槽。本地 key 不能冒充远端 id。
- 可选顶层 `groups` 形状为 `{key, interaction: "single"|"multi", situation, cases, relations}`；非空时取代 flat `cases`。本地不组装多人耦合 `multi`，只有平台执行才使用。
- 可选 `inputs` 条目为 `{key, label, desc, type: "number"|"text", unit, value}`；key 不得与 measure/report 撞名。`status` 只取 `draft` / `active` / `archived`。
- `measure` 条目为 `{key, label, desc, method, unit, range}`。`method="deterministic"` 的 key 只取 `completion_rate`、`avg_steps`、`recommend_rate`、`sentiment_positive`、`sentiment_neutral`、`sentiment_negative`、`grounding_failure_rate`；`method="judge"` 的 key 自定且 `desc` 必须是可执行 rubric；`method="checker"` 由平台 verifier 产生。
- `report` 条目为 `{key, label, desc}`，`desc` 是章节生成指令；各组内 key 唯一，measure 与 report 不得撞 key。
- caller 链必须闭合：`execute_by="caller"` 要求 `analyse_by="caller"`，后者要求 `report_by="caller"`。analysis、measure 与 rubric 始终不进入 case packet。

## 3. 物化本地运行包

复用平台 Methodology 时，把定义和引用资产拉到文件：

```bash
mirofish pull <mth_id> --out <session_dir> --json
```

检查物化后的 cases 顺序，再补 caller 本地的 target、uses、prompts、preflight 与 evidence 目录。子代理按文件路径读取，不把全部资产搬进主上下文。

## 4. 上传前检查

`bundle.json` 是 ingest 请求体，不是本地 session manifest。它按 `case-index.json` 排序，与 Methodology 的 flat cases 同序同长，并内联每个 case 的完整结果：

```json
{
  "cases": [
    {
      "index": 0,
      "status": "succeeded",
      "outcome": "最终落点",
      "steps": [
        {
          "thought": "简短公开理由",
          "do": "真实动作",
          "say": "公开反应",
          "observation": "真实结果",
          "operates": [{"do": "底层操作", "output": "直接结果", "ok": true, "shot": "case-a/03-1.png"}],
          "shots": ["case-a/03.png"]
        }
      ]
    }
  ],
  "runner": {"agent": "实际宿主", "model": "实际模型"},
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601"
}
```

服务端按顺序关联 case，不消费本地 `case_key`。没跑成的 case 用 `error` 占位，不能删除。Bundle 不能放 trace/instruction 路径、文件哈希、按 case 分组的 runner log、usage、隐藏推理、Local Use binding 或无关源码；路径与哈希属于本地 `manifest.json`。

先保存当日权威契约：

```bash
mirofish runs ingest --schema > ingest-schema.json
mirofish runs ingest --check -f bundle.json --index case-index.json --evidence evidence --json
```

检查：

- `bundle.json` 可解析，`cases` 与 Methodology flat cases 同序同长；本地 `--check` 通过，但服务端仍是最终权威；
- status 只用 `succeeded`、`abandoned`、`timeout`、`error`；
- runner 写实际宿主和模型；
- 执行证据齐全（按端记录的形态合同以 `trace-evidence.md` 为真源）；截图路径相对 `evidence/` 根，`--check --evidence` 顺带校验文件存在、类型（png/jpg/webp）与大小（单张 ≤5MB）——允许格式与大小以本节为真源；
- feedback 引用的 case/step/evidence 存在；
- 不含 token、cookie、密码、API key、个人身份信息、Local Use binding、无关源码、费用或 usage；
- **截图逐张过一眼**：画面含凭据或个人信息的先打码，打不了码就从 bundle 里摘掉该 `shot`（该步文本轨迹保留）；
- 本地绝对路径在不影响证据时改成 session 相对引用；必须保留的敏感值先脱敏，并在本地记录脱敏说明。

脱敏只处理秘密和无关数据，不改变用户行为、观察与落点。截图随 ingest 的 `--evidence` 上传并在平台评测记录页逐步渲染；录像与其他附件当前不上传，原始文件继续留在本地 session。用户改口不传就停手、状态记 `local_only`；内容不适合离开本机时同样停止上送，保持 `pending_upload` 并写明缺口。

## 5. 首次上送与读回

**接了平台就随做随写**:用户已要求接平台时,每个真实完成的执行**一到终态就**写入 mirofish(资产已在生成时落库,这里补 run);中途用户改口说不传就停手、保持本地 `local_only`。每个真实完成的执行创建一条 run：

```bash
mirofish runs ingest --methodology <mth_id> -f bundle.json \
  --evidence evidence \
  --report feedback.md \
  --runner '{"agent":"<实际宿主>","model":"<实际模型>"}' \
  --json
```

`--evidence <目录>` 把 bundle 里 `shots`/`operates[].shot` 引用的相对路径截图自动上传换成平台 ref(内容寻址幂等,重传同图得同 ref);全是 oss:// ref 或没有截图时可省略。

只有 Methodology 声明 caller-owned judge 指标且数字能帮助本次决定时，才增加 `--measures measures.json`。`measures.json` 的形状是平台回传合同的 `measure` 字段：`{"<judge_key>": <数值>}`，key 必须 ∈ 该 Methodology `meta.measure` 里 `method="judge"` 的 key、数值落在其 `range` 内；判分必须与叙事报告（`--report`）一并回传。

诚实边界：caller 回写的报告在平台评测记录页以正文（markdown）呈现，不会像平台分析师产出的报告那样带逐条溯源、评分卡等结构化区块；结构化留档目前只有 evol 判决经 `--data` 传（§6）。不要向用户许诺平台页面会长出这些区块。

不能只相信命令退出码。保存 stdout/stderr，并读回核对：

```bash
mirofish runs result <run_id> --json
mirofish runs cases <run_id> --json
mirofish runs case <run_id> <index> --full --json
```

把 `run_id`、mode、case 数、读回摘要、时间和命令输出写入 `upload.json`，将 session 状态改成 `uploaded`。平台从 trace 计算 deterministic 读数；本地不上传用量。

## 6. 修订与新版本

严格区分“修正记录”和“产生新证据”。

只有同一次执行的漏记、格式错误或脱敏修订才更新原 run。更新前保留原 bundle、feedback、读回结果与修改原因：

```bash
mirofish runs ingest --run <run_id> -f bundle.corrected.json \
  --evidence evidence \
  --report feedback.corrected.md --data report-data.corrected.json \
  --revision-note "<为什么这是同一证据的修正>" \
  --json
```

(补漏截图也算同一证据的修正——corrected bundle 里新引用的截图同样经 `--evidence` 上传。)

更新后再次读回，确认 run id 不变、case 顺序不变、修订可见。报告随纠错整体替换；原报告有结构化 `data`（例如 evol 判决）时必须随 `--data` 一并传回，避免只补正文却清空结构化留档。不要用 update 覆盖重新执行、换模型、补跑用户或新版本验证；这些都创建新 run。

目标版本改变时，用稳定的 evol session 串起新 run：

```bash
mirofish runs ingest --methodology <mth_id> -f bundle.json \
  --report feedback.md \
  --data evol-data.json \
  --evol '{"session_id":"evo_<stable>","round":<N>,"hypothesis":"<这版想验证的变化>"}' \
  --json
```

`evol-data.json` 至少记录这一轮如何进入谱系；语义化 loop 不需要虚构分数，`dims` 可以为空。首轮（`baseline`）里有 `error`（执行环境故障）的 case，先修好环境重跑干净再进谱系——基线不干净，后面每一轮的对比都失真；实在修不了就在 `notes` 里点名该 case 不可比：

```json
{
  "evol": {
    "decision": "baseline",
    "diff": "这一轮被验证版本发生了什么变化",
    "notes": "行为证据怎样改变了下一步判断",
    "completion": {"completed": 3, "total": 3},
    "dims": [],
    "converged": false
  }
}
```

`completion` 记录本轮 case 完成事实（办成数 / 总数），**必须放在 `evol` 对象内**——谱系页只认 `evol.completion`，写到顶层不会被识别。

后续轮次按事实把 `decision` 写成 `keep` 或 `revert`；真正停止时再写 `converged: true`。`--evol` 负责把 run 串起来，`--data` 才让谱系页看见每轮判决与变化，两者不能互相替代。

按 [loop.md](loop.md) 判了另起时：**采用版**的 bundle 作为本轮 run 上送，落选版不 ingest、trace 留在本地轮目录；判决写进 `evol` 对象的 `pivot` 字段——`{"kind": "patch" 或 "rebuild"（采用的是补丁版还是另起版）, "premise": "换掉/保住的那条前提", "basis": "赢在哪，一句", "loser_ref": "落选版的本地轮目录或指纹"}`；`ab.md` 的口径一致性声明并入 `--report` 一起回传。`--data` 是自由 JSON、平台原样留档——谱系页当前未必渲染 `pivot`，但判决必须落进留档，不能只活在对话里。

Methodology 声明了 judge 指标、本轮已按 `--measures` 回传判分时，把同一组分数折进 `evol.dims`，谱系页才有轮间对比（条目形状以当日 `mirofish runs ingest --schema` 为权威）；没有量化的轮次 `dims` 保持为空，不虚构分数。

若 trace 不变、只补充语义反馈，可以使用：

```bash
mirofish runs report <run_id> -f feedback.md --source agent
```

## 7. 离线 Session 恢复

恢复连接后按 session 自身完成补传，不依赖旧对话记忆：

1. 校验 `request.md`、`target.json`、Methodology、persona、scenario、trace、feedback、bundle 和哈希仍完整。
2. 运行 `doctor`，保存当日 Methodology 与 ingest schema。
3. 对每个本地 persona/scenario 先检索；复用或创建后，将 local key → remote id 写入 `session.json`。
4. 以远端 id 生成 caller/caller/caller Methodology，创建后保存 mth id；不要改写各轮原始本地定义。
5. 扫描并脱敏待上传材料，按 bundle 上送，再读回核对；多轮 session 补传 `--evol` 时，round 以 `session.json` 记录的轮次为准——不猜，也不重复占用已上送轮的 round。
6. 写入 `upload.json`；任何一步失败都保留已完成映射，可安全重试，不重复创建已记录的资产或 run。

若本地证据不足以重建映射或确认顺序，不猜。保持 pending 并把缺口交给用户处理。
