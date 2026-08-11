import json
import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.config import Settings
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import (
    AgentReachWebFetcher,
    CaptureFetchError,
    FetchedAttachment,
    FetchedWebPage,
    ProviderUnavailableError,
    ResponseTooLargeError,
    RoutedWebFetcher,
    SafeWebFetcher,
    UnsafeUrlError,
)
from flywiki.sources.models import (
    CaptureStatus,
    EditableNote,
    NoteVersion,
    SourceVersion,
)
from flywiki.sources.notes import EditableNoteService, NoteVersionConflict
from flywiki.sources.pipeline import CaptureJobService, CapturePipeline
from flywiki.sources.repository import SourceRepository
from flywiki.sources.storage import InMemoryObjectStore
from flywiki.workspaces.bootstrap import bootstrap_default_context


class FakeFetcher:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls = 0

    async def fetch(self, url: str) -> FetchedWebPage:
        self.calls += 1
        return FetchedWebPage(url, self.content, "text/html")

    async def fetch_attachment(self, url: str) -> FetchedAttachment:
        return FetchedAttachment(url, b"PNG", "image/png", "image.png")


class FailingFetcher:
    async def fetch(self, _url: str) -> FetchedWebPage:
        raise UnsafeUrlError("blocked")

    async def fetch_attachment(self, _url: str) -> FetchedAttachment:
        raise UnsafeUrlError("blocked")


class StubProvider:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.page_calls = 0
        self.attachment_calls = 0

    async def fetch(self, url: str) -> FetchedWebPage:
        self.page_calls += 1
        if self.error is not None:
            raise self.error
        return FetchedWebPage(url, b"<html><body><p>Agent Reach</p></body></html>", "text/html")

    async def fetch_attachment(self, url: str) -> FetchedAttachment:
        self.attachment_calls += 1
        return FetchedAttachment(url, b"fallback", "image/png", "fallback.png")


async def test_capture_fetcher_prefers_agent_reach_and_falls_back_when_unavailable() -> None:
    agent_reach = StubProvider()
    fallback = StubProvider()
    fetcher = RoutedWebFetcher(agent_reach, fallback)

    page = await fetcher.fetch("https://example.com/article")
    attachment = await fetcher.fetch_attachment("https://example.com/image.png")

    assert page.content == b"<html><body><p>Agent Reach</p></body></html>"
    assert agent_reach.page_calls == 1
    assert fallback.page_calls == 0
    assert attachment.content == b"fallback"
    assert agent_reach.attachment_calls == 0
    assert fallback.attachment_calls == 1


async def test_capture_fetcher_uses_fallback_for_a_missing_agent_reach_capability() -> None:
    agent_reach = StubProvider(error=ProviderUnavailableError("not installed"))
    fallback = StubProvider()
    fetcher = RoutedWebFetcher(agent_reach, fallback)

    page = await fetcher.fetch("https://unsupported.example/article")

    assert page.content == b"<html><body><p>Agent Reach</p></body></html>"
    assert agent_reach.page_calls == 1
    assert fallback.page_calls == 1


async def test_agent_reach_web_reader_returns_normalized_markdown() -> None:
    async def public_resolver(_host: str, _port: int) -> list[str]:
        return ["93.184.216.34"]

    reader = AgentReachWebFetcher(
        timeout_seconds=1,
        max_bytes=100,
        max_redirects=1,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8"},
                content=b"# Agent Reach\n\nReader output.",
                request=request,
            )
        ),
    )

    page = await reader.fetch("https://example.com/article#fragment")
    extracted = WebPageExtractor().extract(
        page.content,
        page.final_url,
        content_type=page.content_type,
    )

    assert page.final_url == "https://example.com/article"
    assert page.content_type == "text/markdown"
    assert page.backend == "agent-reach"
    assert extracted.markdown == b"# Agent Reach\n\nReader output.\n"
    assert extracted.metadata["capture_content_type"] == "text/markdown"
    assert extracted.locator_map["blocks"][0]["text"] == "Agent Reach"


async def test_agent_reach_web_reader_rejects_upstream_block_pages() -> None:
    async def public_resolver(_host: str, _port: int) -> list[str]:
        return ["151.101.1.140"]

    reader = AgentReachWebFetcher(
        timeout_seconds=1,
        max_bytes=1_000,
        max_redirects=1,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8"},
                content=(
                    b"Warning: Target URL returned error 403: Forbidden\n\n"
                    b"You've been blocked by network security.\n\n"
                    b"To continue, log in to your Reddit account or use your developer token."
                ),
                request=request,
            )
        ),
    )

    with pytest.raises(ProviderUnavailableError, match="upstream returned 403"):
        await reader.fetch(
            "https://www.reddit.com/r/ObsidianMD/comments/1g9ir90/example/"
        )


async def test_agent_reach_web_reader_rejects_captcha_challenge_pages() -> None:
    async def public_resolver(_host: str, _port: int) -> list[str]:
        return ["101.91.22.57"]

    reader = AgentReachWebFetcher(
        timeout_seconds=1,
        max_bytes=1_000,
        max_redirects=1,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=utf-8"},
                content=(
                    b"Warning: This page maybe requiring CAPTCHA, please make sure "
                    b"you are authorized to access this page.\n\n" +
                    "## 环境异常\n\n当前环境异常，完成验证后即可继续访问。\n".encode()
                ),
                request=request,
            )
        ),
    )

    with pytest.raises(ProviderUnavailableError, match="challenge page"):
        await reader.fetch("https://mp.weixin.qq.com/s/example")


async def test_capture_pipeline_is_idempotent_and_creates_editable_note(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    submitted = await CaptureJobService(session).submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        url="https://example.com/article#fragment",
        idempotency_key="web:article:1",
    )
    replay = await CaptureJobService(session).submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        url="https://example.com/article",
        idempotency_key="web:article:1",
    )
    fetcher = FakeFetcher(
        b"""
        <html><head><title>Captured</title></head>
        <body><h1>Captured</h1><p>Evidence text.</p></body></html>
        """
    )
    store = InMemoryObjectStore()
    pipeline = CapturePipeline(
        session,
        store,
        fetcher,
        WebPageExtractor(),
    )

    completed = await pipeline.run(context.workspace.id, submitted.job.id)
    completed_again = await pipeline.run(context.workspace.id, submitted.job.id)

    assert submitted.created is True
    assert replay.created is False
    assert replay.job.id == submitted.job.id
    assert completed.status == CaptureStatus.READY_FOR_COMPILE
    assert completed_again.source_version_id == completed.source_version_id
    assert fetcher.calls == 1
    assert await session.scalar(select(func.count()).select_from(SourceVersion)) == 1
    assert await session.scalar(select(func.count()).select_from(EditableNote)) == 1
    assert await session.scalar(select(func.count()).select_from(NoteVersion)) == 1

    note = await SourceRepository(session).find_note_by_source_version(
        context.workspace.id, completed.source_version_id
    )
    assert note is not None
    view = await EditableNoteService(session).get(context.workspace.id, note.id)
    assert view.current_version.version_number == 1
    assert "Evidence text." in view.current_version.markdown
    artifacts = await SourceRepository(session).list_artifacts(
        context.workspace.id, completed.source_version_id
    )
    locator = next(item for item in artifacts if item.role.value == "locator_map")
    locator_map = json.loads(await store.get(locator.object_key))
    assert any(block["text"] == "Evidence text." for block in locator_map["blocks"])


async def test_capture_pipeline_downloads_page_images_as_immutable_attachments(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    job = (
        await CaptureJobService(session).submit(
            workspace_id=context.workspace.id,
            knowledge_base_id=context.knowledge_base.id,
            url="https://example.com/with-image",
            idempotency_key="web:image:1",
        )
    ).job
    store = InMemoryObjectStore()
    completed = await CapturePipeline(
        session,
        store,
        FakeFetcher(
            b'<html><body><p>Text.</p><img src="/assets/image.png"></body></html>'
        ),
        WebPageExtractor(),
    ).run(context.workspace.id, job.id)

    artifacts = await SourceRepository(session).list_artifacts(
        context.workspace.id, completed.source_version_id
    )
    attachment = next(item for item in artifacts if item.role.value == "attachment")
    assert await store.get(attachment.object_key) == b"PNG"


async def test_editing_note_creates_history_without_changing_source_version(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    job = (
        await CaptureJobService(session).submit(
            workspace_id=context.workspace.id,
            knowledge_base_id=context.knowledge_base.id,
            url="https://example.com/edit",
            idempotency_key="web:edit:1",
        )
    ).job
    completed = await CapturePipeline(
        session,
        InMemoryObjectStore(),
        FakeFetcher(b"<html><body><p>Original</p></body></html>"),
        WebPageExtractor(),
    ).run(context.workspace.id, job.id)
    source_version = await SourceRepository(session).get_version(
        context.workspace.id, completed.source_version_id
    )
    original_hash = source_version.content_sha256
    note = await SourceRepository(session).find_note_by_source_version(
        context.workspace.id, source_version.id
    )
    assert note is not None

    updated = await EditableNoteService(session).save(
        context.workspace.id,
        note.id,
        "# Edited\n",
        base_version_number=1,
    )

    assert [version.version_number for version in updated.history] == [1, 2]
    assert updated.current_version.markdown == "# Edited\n"
    assert source_version.content_sha256 == original_hash
    with pytest.raises(NoteVersionConflict):
        await EditableNoteService(session).save(
            context.workspace.id,
            note.id,
            "# Stale edit\n",
            base_version_number=1,
        )


async def test_capture_failure_is_recorded_and_can_be_retried(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    job = (
        await CaptureJobService(session).submit(
            workspace_id=context.workspace.id,
            knowledge_base_id=context.knowledge_base.id,
            url="https://example.com/retry",
            idempotency_key="web:retry:1",
        )
    ).job
    failed = await CapturePipeline(
        session,
        InMemoryObjectStore(),
        FailingFetcher(),
        WebPageExtractor(),
    ).run(context.workspace.id, job.id)

    assert failed.status == CaptureStatus.FAILED
    assert failed.error_code == "unsafe_url"
    assert failed.attempts == 1

    completed = await CapturePipeline(
        session,
        InMemoryObjectStore(),
        FakeFetcher(b"<html><body><p>Recovered.</p></body></html>"),
        WebPageExtractor(),
    ).run(context.workspace.id, job.id)
    assert completed.status == CaptureStatus.READY_FOR_COMPILE
    assert completed.attempts == 2


async def test_safe_fetcher_blocks_private_addresses_and_large_responses() -> None:
    async def private_resolver(_host: str, _port: int) -> list[str]:
        return ["127.0.0.1"]

    private_fetcher = SafeWebFetcher(
        timeout_seconds=1,
        max_bytes=100,
        max_redirects=1,
        resolver=private_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"not reached", request=request)
        ),
    )
    with pytest.raises(UnsafeUrlError):
        await private_fetcher.fetch("http://localhost/admin")

    async def public_resolver(_host: str, _port: int) -> list[str]:
        return ["93.184.216.34"]

    large_fetcher = SafeWebFetcher(
        timeout_seconds=1,
        max_bytes=4,
        max_redirects=1,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"12345",
                request=request,
            )
        ),
    )
    with pytest.raises(ResponseTooLargeError):
        await large_fetcher.fetch("https://example.com/")


async def test_safe_fetcher_rejects_http_200_challenge_pages() -> None:
    async def public_resolver(_host: str, _port: int) -> list[str]:
        return ["101.91.22.57"]

    fetcher = SafeWebFetcher(
        timeout_seconds=1,
        max_bytes=1_000,
        max_redirects=1,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=(
                    "<html><head><title>环境异常</title></head>"
                    "<body><h2>环境异常</h2>"
                    "<p>当前环境异常，完成验证后即可继续访问。</p></body></html>"
                ).encode(),
                request=request,
            )
        ),
    )

    with pytest.raises(CaptureFetchError) as caught:
        await fetcher.fetch("https://mp.weixin.qq.com/s/example")

    assert caught.value.code == "blocked_content"


async def test_repository_hides_capture_job_and_note_across_workspaces(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    other_workspace_id = uuid.uuid4()
    job = (
        await CaptureJobService(session).submit(
            workspace_id=context.workspace.id,
            knowledge_base_id=context.knowledge_base.id,
            url="https://example.com/private",
            idempotency_key="web:private:1",
        )
    ).job

    from flywiki.sources.repository import SourceResourceNotFound

    with pytest.raises(SourceResourceNotFound):
        await SourceRepository(session).get_capture_job(other_workspace_id, job.id)
