import json
import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.config import Settings
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import (
    FetchedAttachment,
    FetchedWebPage,
    ResponseTooLargeError,
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
