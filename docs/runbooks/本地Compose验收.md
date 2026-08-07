# 本地 Compose 骨架验收

> 对应 M0 验收：「单命令 Docker Compose 可启动 Web、API、Worker、PostgreSQL、Redis、对象存储」。  
> 本文只验**核心骨架**（不含 `--profile observability` / `openkb`）。

## 前置

- Docker Desktop 已启动（`docker version` 能看到 Server）
- 仓库根目录有 `.env`（从 `.env.example` 复制，密码与密钥已改成随机值）
- 端口空闲：`5432`、`6379`、`8000`、`8080`、`9000`、`9001`

若尚无 `.env`：

```bash
cp .env.example .env
# 至少改掉 POSTGRES_PASSWORD、MINIO_ROOT_PASSWORD、CLICKHOUSE_PASSWORD
# 以及三条 LANGFUSE_* 密钥（即便本轮不启 observability，compose 模板也会读它们）
```

生成随机值示例：

```bash
openssl rand -hex 24          # 密码类
openssl rand -hex 32          # LANGFUSE_SALT
openssl rand -base64 32       # LANGFUSE_ENCRYPTION_KEY / NEXTAUTH_SECRET
```

## 启动

在仓库根目录：

```bash
docker compose up -d --build
docker compose ps -a
```

期望容器状态大致如下：

| 服务 | 期望 |
|------|------|
| `postgres` / `redis` / `minio` / `api` | `Up` 且 `(healthy)` |
| `worker` | `Up` |
| `web` | `Up`，映射 `8080→80` |
| `minio-init` | `Exited (0)`（一次性建桶，正常退出） |

首次构建可能较慢（拉基础镜像 + 编 api/web）。若某步长时间无进度，可先单独 `docker pull` 卡住的镜像再重试 `compose up`。

## 验收清单

在仓库根目录执行；全部通过即视为骨架可用。

### 1. API 存活

```bash
curl -fsS http://127.0.0.1:8000/health/live
```

期望：`{"status":"alive"}`

### 2. API 就绪（核心依赖）

```bash
curl -fsS http://127.0.0.1:8000/health/ready | python3 -m json.tool
```

期望：

- HTTP 200
- `"status": "ready"`
- `components` 中至少包含且均为 `healthy: true`：
  - `database`
  - `redis`
  - `object_storage`

说明：默认 `FLYWIKI_OBSERVABILITY_BACKEND=noop` 时，**不会**把 Langfuse 算进就绪条件（符合 ADR-0006：观测降级不阻断核心）。

### 3. 默认 Workspace / Knowledge Base 已引导

```bash
curl -fsS http://127.0.0.1:8000/api/context | python3 -m json.tool
```

期望字段示例（UUID 每次环境不同，slug/name 固定）：

```json
{
  "owner_email": "owner@flywiki.local",
  "workspace_slug": "personal",
  "workspace_name": "Personal Workspace",
  "knowledge_base_slug": "inbox",
  "knowledge_base_name": "Inbox"
}
```

再请求一次应返回同一组 id（引导幂等）。

### 4. Web 首页

浏览器打开：<http://localhost:8080>

或：

```bash
curl -fsS -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8080/
```

期望：`200 text/html`，页面标题含 FlyWiki。

### 5. Web 反代到 API

```bash
curl -fsS http://127.0.0.1:8080/health/ready | python3 -m json.tool
curl -fsS http://127.0.0.1:8080/api/context | python3 -m json.tool
```

期望与直接打 `:8000` 一致（nginx 把 `/health/`、`/api/` 转到 api）。

### 6. Worker 在线（可选抽查）

```bash
docker compose logs worker --tail 30
```

期望日志含 `celery@... ready`。

## 端口速查

| 地址 | 用途 |
|------|------|
| <http://localhost:8080> | Web |
| <http://localhost:8000> | API（直连） |
| <http://localhost:9001> | MinIO Console |
| `localhost:5432` | Postgres |
| `localhost:6379` | Redis |

## 常见问题

**`/health/ready` 返回 503，且 `langfuse` 为 `ConnectError`**  
说明跑的是旧 API 镜像：noop 观测下仍硬探 Langfuse。拉最新代码后 `docker compose up -d --build api`。

**Web 构建失败：`Cannot find matching keyid` / Node 版本过低**  
需 Node ≥ 22.13，且用仓库里的 `web/Dockerfile`（经 npm 安装固定版 pnpm，并在 `pnpm-workspace.yaml` 允许 `esbuild` 构建脚本）。

**`apt-get` / `deb.debian.org` 超时**  
当前 API 镜像已不再在构建期装 curl；若仍看到该步骤，说明在用旧 Dockerfile。

**端口占用**  
`lsof -nP -iTCP:8080 -sTCP:LISTEN`（换端口改 `.env` 里 `WEB_PORT` / `API_PORT` 等）。

**看日志**

```bash
docker compose logs api --tail 80
docker compose logs web --tail 40
```

## 停机

```bash
docker compose down          # 停容器，保留数据卷
docker compose down -v       # 连同 Postgres/Redis/MinIO 数据一并删除（慎用）
```

## 本轮不验（有意排除）

- `docker compose --profile observability`（Langfuse / ClickHouse）
- `docker compose --profile openkb`（OpenKB Worker 镜像尚未就绪）
- 微信绑定等后续领域能力

Capture 与 Source Version 请按[网页采集与 Editable Note 验收](网页采集验收.md)单独验证。
