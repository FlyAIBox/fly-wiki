import json
from pathlib import Path

import pytest

from flywiki.sources.fetcher import (
    BlockedContentError,
    ProviderUnavailableError,
    ResponseTooLargeError,
)
from flywiki.sources.wechat import WeChatPublicAccountFetcher


class FakeRunner:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, ...]] = []

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes:
        del timeout_seconds, max_bytes
        self.calls.append(argv)
        return json.dumps(self.payload, ensure_ascii=False).encode()


def skill_root(tmp_path: Path) -> Path:
    root = tmp_path / "web-content-fetcher"
    script = root / "scripts" / "fetch.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# adapter fixture\n")
    return root


async def test_wechat_adapter_routes_article_through_skill_json(tmp_path: Path) -> None:
    runner = FakeRunner(
        {
            "url": "https://mp.weixin.qq.com/s/article-id",
            "mode": "stealth",
            "metadata": {
                "title": "一篇微信文章",
                "author": "公众号作者",
                "published_at": "2026年8月8日 10:44",
            },
            "content": "正文内容",
        }
    )
    fetcher = WeChatPublicAccountFetcher(
        skill_root=skill_root(tmp_path),
        timeout_seconds=30,
        max_bytes=10_000,
        runner=runner,
        python_executable="python3",
    )

    page = await fetcher.fetch("https://mp.weixin.qq.com/s/article-id")

    assert page.backend == "web-content-fetcher:wechat"
    assert page.content_type == "text/markdown"
    assert page.content == "# 一篇微信文章\n\n正文内容\n".encode()
    assert page.metadata == {
        "title": "一篇微信文章",
        "author": "公众号作者",
        "published_at": "2026年8月8日 10:44",
    }
    assert runner.calls == [
        (
            "python3",
            str(tmp_path / "web-content-fetcher" / "scripts" / "fetch.py"),
            "https://mp.weixin.qq.com/s/article-id",
            "2500",
            "--json",
        )
    ]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/s/article-id",
        "https://mp.weixin.qq.com/profile",
        "https://evil.example/?url=https://mp.weixin.qq.com/s/article-id",
    ],
)
async def test_wechat_adapter_rejects_non_article_urls(tmp_path: Path, url: str) -> None:
    runner = FakeRunner({"content": "unused"})
    fetcher = WeChatPublicAccountFetcher(
        skill_root=skill_root(tmp_path),
        timeout_seconds=30,
        max_bytes=10_000,
        runner=runner,
    )

    with pytest.raises(ProviderUnavailableError, match="not a WeChat"):
        await fetcher.fetch(url)

    assert runner.calls == []


async def test_wechat_adapter_falls_back_when_skill_is_missing(tmp_path: Path) -> None:
    fetcher = WeChatPublicAccountFetcher(
        skill_root=tmp_path / "missing",
        timeout_seconds=30,
        max_bytes=10_000,
        runner=FakeRunner({"content": "unused"}),
    )

    with pytest.raises(ProviderUnavailableError, match="not installed"):
        await fetcher.fetch("https://mp.weixin.qq.com/s/article-id")


async def test_wechat_adapter_rejects_malformed_or_oversized_output(tmp_path: Path) -> None:
    malformed = WeChatPublicAccountFetcher(
        skill_root=skill_root(tmp_path),
        timeout_seconds=30,
        max_bytes=10_000,
        runner=FakeRunner(["not", "an", "object"]),
    )
    with pytest.raises(ProviderUnavailableError, match="invalid payload"):
        await malformed.fetch("https://mp.weixin.qq.com/s/article-id")

    oversized = WeChatPublicAccountFetcher(
        skill_root=skill_root(tmp_path),
        timeout_seconds=30,
        max_bytes=8,
        runner=FakeRunner({"content": "这段正文超过限制"}),
    )
    with pytest.raises(ResponseTooLargeError):
        await oversized.fetch("https://mp.weixin.qq.com/s/article-id")


async def test_wechat_adapter_rejects_challenge_content(tmp_path: Path) -> None:
    fetcher = WeChatPublicAccountFetcher(
        skill_root=skill_root(tmp_path),
        timeout_seconds=30,
        max_bytes=10_000,
        runner=FakeRunner(
            {
                "content": (
                    "# 环境异常\n\n"
                    "当前环境异常，请完成验证后即可继续访问。"
                )
            }
        ),
    )

    with pytest.raises(BlockedContentError, match="challenge page") as caught:
        await fetcher.fetch("https://mp.weixin.qq.com/s/article-id")

    assert caught.value.code == "blocked_content"
