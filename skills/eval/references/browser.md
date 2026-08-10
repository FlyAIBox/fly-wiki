# agent-browser：web 类 case 的浏览器驱动层

任何实际通过浏览器行动的 case 都从这里取得 runtime，**当前正式通道**，不是备胎。Primary surface 可以是 `web`，也可以是经网页接入的 `agent` / `model`；加载本页不会改变目标分类。

为什么是它：simulator 的 MCP 注入已随 #498 整条撤走（GUI 控制交给 pi-gui），`mcp__simulator__*` 不再存在。而 pi-gui 经宿主的 `gui_task` 提供 —— 那是把整个 GUI 任务**委派给另一个代理**、只回纯文本 + session key，eval 要的逐步 ref 与截图证据链会在委派处断掉。所以 web 类 case 走 agent-browser：**子代理自己驱动、自己留证**。别两套混用（同一轮里混用两个驱动，证据口径就不可比）。

红线是：**agent 用自己的托管浏览器、永不共享用户的窗口与焦点**。agent-browser 的 `--session` 正是这个形态。

## 隔离契约（能并行的根据）

`--session <name>` 给每个 case 一个独立浏览器上下文，独立的：cookies、localStorage / sessionStorage、IndexedDB、cache、浏览历史、标签页。

**实测（2026-08-04，agent-browser 0.15.0）**：3 个子代理各持一个 session，**同时**打开同源 `example.com`，各写一个 localStorage 标记；主代理在三者都写完后逐个读回 —— 三个标记并存、互不覆盖，各自 URL 也各自保持。同源本该共享 storage，所以这正是隔离成立的证据。

## preflight：造 + 预热（主代理做，子代理不碰）

一个 case 一个 session。**冷启第一条命令会失败** —— 报 `Daemon failed to start`，页面停在 `about:blank`，而后续读命令可能安静地返回空白而不报错。所以预热必须核实「真的到了目标页」，没到就重试：

```bash
warm() {  # warm <session> <url> <期望在 url 里出现的串>
  for i in 1 2 3; do
    agent-browser --session "$1" open "$2" >/dev/null 2>&1
    case "$(agent-browser --session "$1" get url 2>/dev/null | tail -1)" in
      *"$3"*) return 0;;
    esac
  done
  return 1
}
warm case-a https://target.example/start target.example
```

- 预热到位后子代理零故障（实测 3 个并行子代理各 7 次调用，无一次报错）。**不要把冷启失败留给子代理** —— 那会在 trace 里变成一次假故障，而它不是这个人的真实经历。
- **全新访客**初态 = 一个没用过的 session 名，什么都别预置。**已登录测试账号**初态 = preflight 里登录后 `state save <path>`，再交给子代理（登录动作是准备，不进 trace）。
- 并行几个：browser case 通常 2–4 个，仍以 `execution.md` 的隔离合同和宿主资源为限，其余排队。

## 派给子代理的纪律（写进 packet）

1. **session 名由主代理指派**，子代理不许自选 —— 撞名就是共享会话，隔离当场失效。
2. **每条命令都带 `--session`，一次都不能漏。** 漏了不报错，会静默落到 `default` 会话（实测：漏一次就凭空多出一个 default session）—— 证据串到别处去了，**而且看起来一切正常**。
3. 子代理**不许 `close`**、不许 `session list`、不许碰别的 session 名。清理是主代理的收尾动作。
4. **禁 `--auto-connect`、禁 `--cdp`。** 这两个会接上用户自己正在跑的 Chrome，撞**绝不驱动用户自己的浏览器**这条红线——那是用户的登录态与隐私，也污染「全新访客」的前提。
5. 截图路径带 case 编号：`--session` 隔离浏览器，但管不了文件互相覆盖。

## 子代理怎么驱动

1. `agent-browser --session <case-key> snapshot -i` 拿可交互元素。输出形如 `- link "Learn more" [ref=e1]` —— **可见文字 + `@ref`**，正合「按可见文字挑 ref，不猜坐标、不写选择器」。
2. 按 ref 动作：`click @e1`、`fill @e2 "…"`、`press`、`get text`。
3. **动作后验证效果**：`diff snapshot` 与上次快照比对，或用 `get url` / `get text` 取轻信号。没有任何变化 = 动作没生效，换目标或换方法，不要原样重复（orchestration.md §2 的无进展熔断）。
4. **每次实际操作后落一张留档截图**：`agent-browser --session <case-key> screenshot <session>/evidence/<case>/03-1.png`，文件名与 trace 里该条 `operates[].shot` 的相对路径一致；步末画面同样落进 `shots`。

## 收尾（主代理）

```bash
agent-browser --session <case-key> close
agent-browser session list        # 必须复核
```

**`close` 会打印 `✓ Browser closed` 而 session 仍在列表里** —— 实测第一次 close 报成功却没关掉，第二次才真关（与冷启同源的 socket 时序问题）。所以收尾一律用 `session list` 复核，没消失就再关一次；漏关的 daemon 会一直挂在机器上。

**只关自己造的 session。** `session list` 里你没造过的那些是用户自己在用的浏览器上下文，**不许动**。
