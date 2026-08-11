# FlyWiki

单用户自托管的 LLM Wiki：把持续进入的资料编译为可追溯、可演化的知识，并管理证据、冲突和用户确认的认知。

- [当前产品基线](docs/product/产品基线.md)
- [M0：微信驱动的自进化 Wiki 闭环](docs/product/首个里程碑.md)
- [互联网与社交平台采集能力](docs/product/互联网采集能力.md)
- [领域词汇表](CONTEXT.md)
- [架构决策](docs/adr/)

## 本地运行

单命令启动核心骨架（Postgres + Redis + MinIO + API + Worker + Web）：

```bash
cp .env.example .env   # 修改其中的密码与密钥
docker compose up -d
```

- Web：<http://localhost:8080>
- API 健康检查：<http://localhost:8000/health/ready>
- 默认 Workspace / Knowledge Base 由 API 启动时自动引导（幂等）。
- 手动验收清单：[docs/runbooks/本地Compose验收.md](docs/runbooks/本地Compose验收.md)

按需追加可选服务（profile 控制，保持核心骨架轻量）：

```bash
docker compose --profile observability up -d   # 自托管 Langfuse 观测/评估面
docker compose --profile openkb up -d          # 固定版本 OpenKB 编译 Worker（镜像就绪后启用）
```

### 后端开发（不经容器）

```bash
cd backend
uv run alembic upgrade head
uv run pytest
uv run uvicorn flywiki.main:app --reload
```

License: [Apache-2.0](LICENSE)
