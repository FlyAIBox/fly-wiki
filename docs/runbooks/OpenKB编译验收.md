# OpenKB 编译验收

本清单验证固定 OpenKB Worker、编译任务、Wiki 查询和从 FlyWiki 规范数据重建。只在本地测试实例执行删除步骤。

## 1. 启动

在 `.env` 中配置可用的 `OPENAI_API_KEY`、`OPENKB_MODEL`，然后启动核心服务和 OpenKB profile：

```bash
docker compose --profile openkb up -d --build
curl --fail http://localhost:8100/health/live
```

健康响应必须报告 `openkb-0.4.5@ac118407eacd`。密钥不得出现在响应、普通日志或数据库领域表中。

## 2. 编译 Source Version

先通过 Web 或 Capture API 得到 `workspace_id`、`knowledge_base_id` 和状态为 `ready_for_compile` 的 `source_version_id`，再提交编译：

```bash
curl --request POST \
  --header "Content-Type: application/json" \
  --header "X-Workspace-ID: WORKSPACE_ID" \
  --data '{"source_version_id":"SOURCE_VERSION_ID","use_editable_note":true}' \
  http://localhost:8000/api/workspaces/WORKSPACE_ID/knowledge-bases/KNOWLEDGE_BASE_ID/compilations
```

轮询返回的任务 ID：

```bash
curl --header "X-Workspace-ID: WORKSPACE_ID" \
  http://localhost:8000/api/workspaces/WORKSPACE_ID/compilations/COMPILATION_JOB_ID
```

验收结果：状态为 `succeeded`，`worker_version`、`page_count` 和 `wikilink_count` 已记录。重复提交同一个 Source Version 和 Note Version 必须返回同一个任务，不产生重复编译。

## 3. 查询 Wiki

```bash
curl --header "X-Workspace-ID: WORKSPACE_ID" \
  http://localhost:8000/api/workspaces/WORKSPACE_ID/knowledge-bases/KNOWLEDGE_BASE_ID/compiled-wiki
```

响应至少包含 `index.md` 和一篇 Markdown 知识页；页面中的 `wikilinks` 可解析。

## 4. Note 更新与原子替换

编辑对应 Editable Note 后再次提交编译。新任务必须成功，Compiled Wiki 包含新 Note，且不保留旧 Note 文本。Worker 在 staging Workspace 完成重编译后才替换当前目录；失败时原 Wiki 仍可查询。

## 5. 删除与重建演练

Worker Workspace key 为 `WORKSPACE_ID-KNOWLEDGE_BASE_ID`。确认 Source Version 与 Note Version 仍在 FlyWiki 后，删除派生 Workspace：

```bash
curl --request DELETE \
  http://localhost:8100/v1/workspaces/WORKSPACE_ID-KNOWLEDGE_BASE_ID
```

提交重建任务：

```bash
curl --request POST \
  --header "Content-Type: application/json" \
  --header "X-Workspace-ID: WORKSPACE_ID" \
  --data '{"idempotency_key":"manual-rebuild-1"}' \
  http://localhost:8000/api/workspaces/WORKSPACE_ID/knowledge-bases/KNOWLEDGE_BASE_ID/rebuilds
```

重建成功后再次查询 Wiki。原始 Source Version、Source Artifact 和 Note Version 的哈希与内容必须保持不变。

## 6. 自动化门禁

```bash
cd backend
uv run ruff check src tests ../openkb-worker
uv run pytest -q
cd ..
docker compose build openkb-worker
docker run --rm \
  -v "$PWD/openkb-worker/check_contract.py:/tmp/check_contract.py:ro" \
  flywiki/openkb-worker:0.4.5-flywiki.1 \
  python /tmp/check_contract.py
```

CI 中固定版失败会阻断；最新稳定版和上游 `main` 只产生兼容性预警。
