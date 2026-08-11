# 微信公众号采集与 `web-content-fetcher` skill

本文说明 FlyWiki 如何使用仓库内置的 `web-content-fetcher` skill 采集微信公众号文章，包括职责边界、调用协议、部署依赖、验收方法、降级行为和故障排查。

适用范围是公开的 `https://mp.weixin.qq.com/s/...` 文章。该能力不负责登录、绕过验证码、采集公众号历史列表或下载文中视频。

## 1. Skill 与 Adapter 的职责

`web-content-fetcher` 是“网页正文提取实现”，`WeChatPublicAccountFetcher` 是“接入 FlyWiki 采集领域的 Adapter”。两者不能混为一个模块。

| 组件 | 位置 | 负责内容 |
|---|---|---|
| Skill 说明 | `skills/web-content-fetcher/SKILL.md` | 告诉人工或 Agent 如何独立运行正文提取脚本 |
| Skill 脚本 | `skills/web-content-fetcher/scripts/fetch.py` | HTTP/浏览器抓取、微信选择器、懒加载图片修复、HTML 转 Markdown、元数据提取 |
| 微信 Adapter | `backend/src/flywiki/sources/wechat.py` | 微信 URL 路由、子进程资源限制、JSON 校验、错误映射、`WebFetcher` 输出标准化 |
| Acquisition 组合 | `backend/src/flywiki/sources/acquisition.py` | 把微信 Adapter 放入统一采集回退链 |
| Capture Pipeline | `backend/src/flywiki/sources/service.py` | 幂等、Source Version、Artifact、Editable Note 和任务状态 |

正常产品请求不由大模型阅读 `SKILL.md` 后临时决定怎么执行。Capture Worker 会确定性地调用 Adapter，Adapter 再调用 skill 脚本。因此：

- 修改选择器、浏览器模式或 Markdown 转换逻辑，应修改 skill；
- 修改 URL 路由、超时、大小限制、错误语义或 FlyWiki 返回类型，应修改 Adapter；
- 修改证据落库、幂等或任务状态，应修改 Capture Pipeline；
- DeepAgents 只调用 `acquire_source(url)`，不获得这个脚本的 Shell 执行权。

## 2. 完整调用链

```text
POST /captures
  -> Celery Capture Worker
  -> RoutedWebFetcher
       1. AgentReachSocialFetcher
       2. WeChatPublicAccountFetcher
            -> python scripts/fetch.py <url> <max_chars> --json
                 -> Scrapling Fetcher（快速 HTTP）
                 -> 正文不足时自动切换 StealthyFetcher（Patchright Chromium）
                 -> 微信正文与元数据提取
                 -> JSON stdout
            -> 校验 JSON、大小与正文
            -> FetchedWebPage(text/markdown)
       3. AgentReachWebFetcher（Jina Reader 回退）
       4. SafeWebFetcher（安全 HTTP 回退）
  -> Source Version + Editable Note
```

微信专用 Adapter 只接受主机名严格等于 `mp.weixin.qq.com`，且路径为 `/s` 或以 `/s/` 开头的 URL。其他微信页面不会误进入该 Adapter。

## 3. Skill 如何提取公众号文章

### 3.1 快速模式与 stealth 模式

FlyWiki 不强制传入 `--stealth`。脚本先用 Scrapling `Fetcher` 发起快速 HTTP 请求；如果提取后的正文少于 200 个字符，再自动使用 `StealthyFetcher` 和 Chromium 重试。

这样处理有两个原因：

- 公众号文章在可直接返回正文时，快速模式更快，且通常比浏览器 DOM 包含更少播放器和交互控件噪声；
- 出现 JavaScript 渲染或反爬差异时，stealth 模式仍可作为同一 skill 内部的回退。

只有在独立排障时，确认快速响应不完整，才建议手工传入 `--stealth` 强制浏览器模式。

### 3.2 正文选择器与 Markdown 转换

脚本优先查找微信正文容器：

1. `div#js_content`
2. `div.rich_media_content`

如果两个选择器都未命中，才退回通用正文候选选择器。转换前会把图片的 `data-src` 提升为 `src`，以保留微信公众号常见的懒加载图片链接。随后使用 `html2text` 转成 Markdown，保留标题、段落、列表、链接、图片、强调和代码等结构。

注意：Markdown 中保留远程图片链接，不等于 FlyWiki 已下载图片文件。当前微信 Adapter 不返回 `attachment_urls`，因此这条路径不会把公众号图片另存为附件 Artifact。

### 3.3 元数据

Skill 会尝试提取：

| 字段 | 主要来源 |
|---|---|
| `title` | `#activity-name` 或 `og:title` |
| `author` | `#js_name` 或 `.rich_media_meta_nickname` |
| `published_at` | `#publish_time`、`em#publish_time`，或页面中的 `ct` Unix 时间戳 |

`ct` 时间戳按中国时区转换为 ISO 8601。Adapter 只接受上述三个非空字符串字段，忽略其他未知元数据。如果正文第一行不是一级标题，Adapter 会用 `title` 补一个 `# 标题`。

## 4. Adapter 调用协议

FlyWiki 当前固定执行：

```bash
python <skill_root>/scripts/fetch.py <url> <max_chars> --json
```

其中：

- 配置值 `skill_root` 默认为相对项目根目录的 `skills/web-content-fetcher`；
- Docker Compose 使用同一个相对路径，运行时再以容器内的项目根目录解析；
- `max_chars` 取 `FLYWIKI_CAPTURE_MAX_BYTES / 4`，用于先限制 Unicode 正文长度；
- Adapter 还会独立限制 JSON stdout 和最终 Markdown 的字节数；
- 子进程超时不会低于 60 秒，以容纳快速抓取和浏览器回退。

成功时 stdout 必须是一个 JSON 对象，协议如下：

```json
{
  "url": "https://mp.weixin.qq.com/s/example",
  "mode": "fast",
  "selector": "div#js_content",
  "content_length": 12345,
  "metadata": {
    "title": "文章标题",
    "author": "公众号名称",
    "published_at": "2026-08-11T12:30:00+08:00"
  },
  "content": "文章 Markdown 正文"
}
```

FlyWiki 的硬性依赖只有 `content`；`metadata` 可选。`mode`、`selector` 和 `content_length` 主要用于独立诊断，当前不会写入 Source metadata。失败时脚本应退出非零，或者返回带 `error` 字段的 JSON：

```json
{
  "url": "https://mp.weixin.qq.com/s/example",
  "error": "Unable to extract meaningful content"
}
```

维护 skill 时必须保持 `scripts/fetch.py <url> <max_chars> --json` 和上述字段向后兼容，否则 Adapter 会把结果判为 provider unavailable 并进入通用回退。

## 5. 两种使用方式

### 5.1 在 FlyWiki 中使用（推荐）

产品代码、后台任务和 Agent 都应提交 Capture 请求，让统一 Pipeline 处理权限、幂等、回退和证据落库：

```bash
CTX=$(curl -fsS http://localhost:8000/api/context)
WS=$(echo "$CTX" | jq -r .workspace_id)
KB=$(echo "$CTX" | jq -r .knowledge_base_id)

curl -fsS -X POST \
  -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://mp.weixin.qq.com/s/7Ba1GI5JfAzltSh0pbYamg",
    "idempotency_key": "manual:wechat:7Ba1GI5JfAzltSh0pbYamg"
  }' \
  "http://localhost:8000/api/workspaces/$WS/knowledge-bases/$KB/captures" | jq
```

成功结果应满足：

- Capture 状态最终为 `ready_for_compile`；
- `metadata.json` 中 `capture_backend` 为 `web-content-fetcher:wechat`；
- 元数据中存在可提取到的 `title`、`author` 和 `published_at`；
- `content.md` 第一行是文章标题，后续为 Markdown 正文；
- 创建了不可变 Source Version 和对应 Editable Note。

### 5.2 直接运行 skill（仅开发和排障）

直接调用脚本不会创建 Capture Job、Source Version 或 Editable Note，只适合验证 skill 自身：

```bash
# 自动 fast -> stealth 回退，直接输出 Markdown
python3 skills/web-content-fetcher/scripts/fetch.py \
  "https://mp.weixin.qq.com/s/7Ba1GI5JfAzltSh0pbYamg"

# 查看 Adapter 使用的 JSON 协议
python3 skills/web-content-fetcher/scripts/fetch.py \
  "https://mp.weixin.qq.com/s/7Ba1GI5JfAzltSh0pbYamg" 30000 --json | jq

# 已确认快速模式不完整时，强制浏览器模式
python3 skills/web-content-fetcher/scripts/fetch.py \
  "https://mp.weixin.qq.com/s/7Ba1GI5JfAzltSh0pbYamg" 30000 --stealth --json | jq
```

在 Worker 容器中验证的是最终部署环境，最适合定位“本机成功、任务失败”的问题：

```bash
docker compose exec worker python \
  ../skills/web-content-fetcher/scripts/fetch.py \
  "https://mp.weixin.qq.com/s/7Ba1GI5JfAzltSh0pbYamg" 30000 --json | jq
```

## 6. 安装与部署

Skill 运行依赖：

```bash
pip install 'scrapling[fetchers]' html2text
python3 -m patchright install chromium
```

标准 backend 镜像已经完成这些工作，并把项目 skill 一同复制进镜像。Compose 通过以下相对路径告诉 API 和 Worker Adapter 到哪里查找 skill：

```text
FLYWIKI_WEB_CONTENT_FETCHER_SKILL_PATH=skills/web-content-fetcher
```

Skill 的源码位于项目自身的 `skills/web-content-fetcher`，应与 `skills-lock.json` 一并提交到 Git，不依赖开发者个人目录下的 `.agents`、`.codex` 或 `.claude` 安装。其他人重新克隆代码后，Docker 构建会直接从该项目目录复制 skill；本地运行 backend 时，默认配置也会从同一相对路径读取。只有显式设置 `FLYWIKI_WEB_CONTENT_FETCHER_SKILL_PATH` 时才会覆盖这个默认路径。

仓库只维护 `skills/web-content-fetcher` 这一份源码，不在 `.agents` 下保存副本，避免两个目录的选择器或 JSON 协议随时间产生差异。

修改 skill、Python 依赖、Dockerfile 或该环境变量后，需要重建并重启 API/Worker，而不是只重启已有容器：

```bash
docker compose up -d --build api worker
```

## 7. 失败、回退与日志判读

下列情况会让微信 Adapter 报 `ProviderUnavailableError`，随后继续尝试 Jina Reader 和安全 HTTP 回退：

- URL 不是受支持的公众号文章路径；
- skill 路径或 `scripts/fetch.py` 不存在；
- Python、Scrapling、Patchright 或 Chromium 不可用；
- 子进程超时或退出码非零；
- stdout 不是合法 JSON；
- JSON 包含 `error`，或 `content` 为空。

不安全 URL 和最终正文超过大小上限属于确定性拒绝，不应靠换 provider 绕过。

下面这组日志不表示 Jina 已经成功采集正文：

```text
GET https://r.jina.ai/https://mp.weixin.qq.com/s/... 200 OK
GET https://mp.weixin.qq.com/s/... 302 Found
GET https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha... 200 OK
Task ... succeeded ...: 'failed'
```

它表示微信专用 Adapter 没有产出可接受结果，系统已经进入 Jina 和安全 HTTP 回退；Jina 的 HTTP 200 只代表 Reader 请求成功，不代表返回的是有效文章。原站随后重定向到 `wappoc_appmsgcaptcha`，挑战页会被识别为 blocked content，最终 Capture 失败。Celery 的 `Task ... succeeded: 'failed'` 表示任务函数正常完成了“把 Capture 标记为 failed”的业务流程，不表示采集成功。

按以下顺序排查：

1. 查看 Worker 启动环境中的 `FLYWIKI_WEB_CONTENT_FETCHER_SKILL_PATH`；
2. 确认该目录下存在 `scripts/fetch.py`；
3. 在 Worker 容器中直接运行上一节的 `--json` 命令；
4. 若快速模式失败，再运行一次 `--stealth --json`，确认 Chromium 是否可启动；
5. 查看 stderr 中的缺包、浏览器、超时或选择器错误；
6. 若代码或 skill 刚更新，执行 `docker compose up -d --build api worker`；
7. 重新提交时使用新的 `idempotency_key`，并确认成功版本的 `capture_backend`。

## 8. 当前限制

- 仅支持公开的 `mp.weixin.qq.com/s...` 文章 URL；不负责公众号搜索、历史文章列表或私有预览链接。
- 不绕过登录墙、验证码、访问频率限制或平台风控；持续出现挑战页时应失败，而不是把挑战页保存为证据。
- Markdown 会保留远程图片地址，但微信 Adapter 当前不下载图片为独立 Artifact。
- 浏览器模式可能带入播放器或交互控件文本；因此默认先尝试通常更干净的快速模式。
- `raw_html` 是 Artifact 的历史角色名；当采集后端直接返回 Markdown 时，该 Artifact 的内容也可能是 Markdown，并非真实原始 HTML。
- 上游页面结构变化时，优先在 skill 内更新选择器和提取逻辑，保持 Adapter JSON 协议不变。

## 9. 修改后的最低验收

修改 skill 或 Adapter 后至少执行：

```bash
cd backend
uv run pytest tests/test_wechat_fetcher.py tests/test_capture_pipeline.py
```

然后用一篇可公开访问的真实公众号文章完成端到端 Capture，验证：

1. 正文长度合理且不是验证码/环境异常页；
2. 标题、作者、发布时间正确；
3. Markdown 图片仍使用可解析的 URL；
4. `capture_backend=web-content-fetcher:wechat`；
5. skill 失败时，通用回退和最终错误码仍符合预期。
