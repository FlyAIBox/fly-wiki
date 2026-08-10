# 非零 Local Use：能力声明、装配与暴露合同

> 只有至少一个 case 确实需要人物现实中已有、且不绕过被测入口的周边能力时读取本页。多数评测的 Use 数量为零，不要为形式加载或创建 Use。

把“能力声明”和“本机怎样执行”明确分开：

- `contract.name`、`contract.description`、`contract.params` 告诉执行者有什么能力、何时使用、需要什么参数。
- `binding` 是 caller 本机的执行装配，绑定命令、工具或适配器；它可能含本地路径，永不上传。
- 纯本地 contract/binding 只留在 session，不上传本地代码，也不伪造远端实现；用户明确接平台后才按 `cli.md` 处理远端映射。

`uses.local.json` 示例：

```json
{
  "uses": [
    {
      "key": "account_status",
      "contract": {
        "name": "account_status",
        "description": "读取指定测试账号当前套餐、下次扣款与取消状态",
        "params": {
          "account_id": {"type": "string", "description": "case 自己的测试账号"}
        }
      },
      "binding": {
        "kind": "command",
        "argv": ["python3", "adapter.py", "status", "{account_id}"],
        "cwd": "/workspace/session/case-a",
        "timeout_s": 20
      },
      "exposure": {
        "kind": "command",
        "path": "tools/account_status",
        "usage": "tools/account_status --account-id <id>"
      }
    }
  ]
}
```

`binding` 只供主代理装配；`exposure` 是给子代理的 case-local 接口。主代理可生成最小 command wrapper，也可映射到宿主原生 tool。Packet 只暴露 contract 与 exposure，不暴露凭据、内部路径或实现源码：

```json
{
  "persona": "persona.json",
  "scenario": "scenario.json",
  "target": "target.json",
  "uses": [
    {
      "name": "account_status",
      "description": "读取指定测试账号的套餐、扣款与取消状态",
      "params": {"account_id": "case-a"},
      "invoke": {"kind": "command", "argv": ["tools/account_status", "--account-id", "case-a"]}
    }
  ]
}
```

Exposure 默认用 command wrapper；仅当宿主真支持注册原生 tool 时才写 `invoke: {"kind":"native","name":"account_status"}`，原生调用也必须进入 runner log。主代理先在一次性状态副本上安全 preflight，确认 binding、exposure、参数替换和输出可观察，再派发 packet。Trace 的 `do` 记录 exposure 名和实际参数，runner log 记录真实调用。

Use 只封装稳定能力，不指定人物下一步，也不返回评价答案。若人物本来就能通过目标公开入口完成任务，不要额外造 Use。

## 现实性与后门闸

Local Use 只能代表 persona 在该环境中现实可用的周边能力，不能绕过被验证入口。例如验证“新用户能否运行 CLI”时，不能给一个直接返回 CLI 结果的 Use；验证客服处理退款时，可以给真实映射到测试账户的“查询账单”能力。便捷程度必须与现实界面或授权一致。

每个 Use 派发前逐项确认：

- 不在本次验证焦点路径上；
- 这位 persona 现实中确实会拥有并使用；
- binding 指向运行中的产品或可信装置，不绑定仓库脚本/源码函数来伪造产品能力；
- preflight 成功且结果可观察；
- packet 不泄露 binding、凭据或内部实现；
- 不会替人物完成本应由目标承担的工作。
