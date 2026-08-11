import httpx
import pytest

from flywiki.sources.fetcher import ProviderUnavailableError
from flywiki.sources.social import AgentReachSocialFetcher


class FakeCommandRunner:
    def __init__(self, *, available: set[str]) -> None:
        self.available = available
        self.calls: list[tuple[str, ...]] = []

    def exists(self, command: str) -> bool:
        return command in self.available

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes:
        del timeout_seconds, max_bytes
        self.calls.append(argv)
        return b'{"title":"Captured","body":"Platform output"}'


@pytest.mark.parametrize(
    ("url", "available", "expected"),
    [
        (
            "https://www.xiaohongshu.com/explore/note-1?xsec_token=token",
            {"opencli"},
            (
                "opencli",
                "xiaohongshu",
                "note",
                "https://www.xiaohongshu.com/explore/note-1?xsec_token=token",
                "-f",
                "yaml",
            ),
        ),
        (
            "https://x.com/flywiki/status/123",
            {"twitter"},
            ("twitter", "tweet", "https://x.com/flywiki/status/123"),
        ),
        (
            "https://www.bilibili.com/video/BV1xx411c7mD",
            {"bili"},
            ("bili", "video", "BV1xx411c7mD"),
        ),
        (
            "https://www.reddit.com/r/python/comments/abc123/title/",
            {"opencli"},
            ("opencli", "reddit", "read", "abc123", "-f", "yaml"),
        ),
        (
            "https://www.facebook.com/zuck",
            {"opencli"},
            ("opencli", "facebook", "profile", "zuck", "-f", "yaml"),
        ),
        (
            "https://www.instagram.com/nasa/",
            {"opencli"},
            ("opencli", "instagram", "user", "nasa", "--limit", "12", "-f", "yaml"),
        ),
    ],
)
async def test_social_fetcher_uses_the_agent_reach_route_for_each_platform(
    url: str,
    available: set[str],
    expected: tuple[str, ...],
) -> None:
    runner = FakeCommandRunner(available=available)
    fetcher = AgentReachSocialFetcher(
        command_runner=runner,
        command_exists=runner.exists,
    )

    page = await fetcher.fetch(url)

    assert runner.calls == [expected]
    assert page.content_type == "text/markdown"
    assert page.backend.startswith("agent-reach:")
    assert b"Platform output" in page.content


async def test_social_fetcher_uses_v2ex_read_only_api_for_topic_urls() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/topics/show.json"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 123456,
                        "title": "A topic",
                        "content": "Topic body",
                        "member": {"username": "author"},
                        "node": {"title": "Python"},
                        "replies": 1,
                    }
                ],
                request=request,
            )
        return httpx.Response(
            200,
            json=[{"member": {"username": "reply-author"}, "content": "Reply body"}],
            request=request,
        )

    fetcher = AgentReachSocialFetcher(
        transport=httpx.MockTransport(respond),
    )

    page = await fetcher.fetch("https://www.v2ex.com/t/123456")

    assert page.backend == "agent-reach:v2ex"
    assert b"A topic" in page.content
    assert b"Reply body" in page.content


async def test_social_fetcher_falls_back_when_platform_command_is_missing() -> None:
    fetcher = AgentReachSocialFetcher(
        command_runner=FakeCommandRunner(available=set()),
        command_exists=lambda _command: False,
    )

    with pytest.raises(ProviderUnavailableError):
        await fetcher.fetch("https://x.com/flywiki/status/123")


async def test_social_fetcher_rejects_urls_without_a_supported_platform_route() -> None:
    fetcher = AgentReachSocialFetcher(
        command_runner=FakeCommandRunner(available={"opencli"}),
        command_exists=lambda _command: True,
    )

    with pytest.raises(ProviderUnavailableError):
        await fetcher.fetch("https://example.com/article")
