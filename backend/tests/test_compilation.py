import asyncio
import hashlib
import uuid
from pathlib import Path

import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.app import create_app
from flywiki.compilation.adapters import FakeOpenKBAdapter, HttpOpenKBAdapter
from flywiki.compilation.interface import CompilationDocument, OpenKBUnavailable
from flywiki.compilation.models import CompilationStatus
from flywiki.compilation.repository import CompilationRepository
from flywiki.compilation.service import KnowledgeCompilation
from flywiki.config import Settings
from flywiki.db.database import Database
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import FetchedWebPage
from flywiki.sources.notes import EditableNoteService
from flywiki.sources.pipeline import CaptureJobService, CapturePipeline
from flywiki.sources.repository import SourceRepository
from flywiki.sources.storage import InMemoryObjectStore
from flywiki.workspaces.bootstrap import BootstrapContext, bootstrap_default_context


class FakeFetcher:
    def __init__(self, body: str) -> None:
        self._body = body

    async def fetch(self, url: str) -> FetchedWebPage:
        html = f"<html><head><title>Compile</title></head><body>{self._body}</body></html>"
        return FetchedWebPage(url, html.encode(), "text/html")


class UnavailableOpenKBAdapter(FakeOpenKBAdapter):
    async def compile(self, workspace_key: str, document: CompilationDocument):  # type: ignore[no-untyped-def]
        raise OpenKBUnavailable("secret upstream detail must not be persisted")


async def _capture(
    session: AsyncSession,
    store: InMemoryObjectStore,
    context: BootstrapContext,
    *,
    suffix: str,
    body: str = "<p>Evidence with [[Related Topic]].</p>",
) -> uuid.UUID:
    job = (
        await CaptureJobService(session).submit(
            workspace_id=context.workspace.id,
            knowledge_base_id=context.knowledge_base.id,
            url=f"https://example.com/{suffix}",
            idempotency_key=f"capture:{suffix}",
        )
    ).job
    completed = await CapturePipeline(
        session,
        store,
        FakeFetcher(body),
        WebPageExtractor(),
    ).run(context.workspace.id, job.id)
    assert completed.source_version_id is not None
    return completed.source_version_id


async def test_compiles_source_and_note_through_adapter_interface(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    workspace_id = context.workspace.id
    knowledge_base_id = context.knowledge_base.id
    store = InMemoryObjectStore()
    source_version_id = await _capture(session, store, context, suffix="first")
    adapter = FakeOpenKBAdapter()
    module = KnowledgeCompilation(session, store, adapter)

    submitted = await module.submit(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_version_id=source_version_id,
    )
    replay = await module.submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        source_version_id=source_version_id,
    )
    completed = await module.run(context.workspace.id, submitted.job.id)
    snapshot = await module.snapshot(context.workspace.id, context.knowledge_base.id)

    assert submitted.created is True
    assert replay.created is False
    assert replay.job.id == submitted.job.id
    assert completed.status == CompilationStatus.SUCCEEDED
    assert completed.worker_version == "fake-openkb"
    assert completed.page_count == 2
    assert completed.wikilink_count >= 1
    assert adapter.compile_calls == 1
    assert any("Original Source Snapshot" in page.markdown for page in snapshot.pages)
    assert any("User Editable Note" in page.markdown for page in snapshot.pages)


async def test_new_note_version_replaces_workspace_without_stale_note(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    store = InMemoryObjectStore()
    source_version_id = await _capture(session, store, context, suffix="edited")
    adapter = FakeOpenKBAdapter()
    module = KnowledgeCompilation(session, store, adapter)
    first = await module.submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        source_version_id=source_version_id,
    )
    first_result = await module.run(context.workspace.id, first.job.id)
    assert first_result.status == CompilationStatus.SUCCEEDED

    note = await SourceRepository(session).find_note_by_source_version(
        context.workspace.id, source_version_id
    )
    assert note is not None
    await EditableNoteService(session).save(
        context.workspace.id,
        note.id,
        "# Revised note\n\nOnly the current note belongs in Compiled Knowledge.\n",
        base_version_number=1,
    )
    second = await module.submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        source_version_id=source_version_id,
    )
    completed = await module.run(context.workspace.id, second.job.id)
    snapshot = await module.snapshot(context.workspace.id, context.knowledge_base.id)

    assert completed.status == CompilationStatus.SUCCEEDED
    assert second.job.id != first.job.id
    assert adapter.replace_calls == 1
    combined = "\n".join(page.markdown for page in snapshot.pages)
    assert "Only the current note" in combined


async def test_deleted_openkb_workspace_rebuilds_from_canonical_registry(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    store = InMemoryObjectStore()
    source_version_id = await _capture(session, store, context, suffix="rebuild")
    adapter = FakeOpenKBAdapter()
    module = KnowledgeCompilation(session, store, adapter)
    compile_job = await module.submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        source_version_id=source_version_id,
    )
    await module.run(context.workspace.id, compile_job.job.id)

    workspace_key = f"{context.workspace.id}-{context.knowledge_base.id}"
    await adapter.delete_workspace(workspace_key)
    rebuild = await module.submit_rebuild(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        idempotency_key="after-delete-1",
    )
    completed = await module.run(context.workspace.id, rebuild.job.id)
    snapshot = await module.snapshot(context.workspace.id, context.knowledge_base.id)

    assert completed.status == CompilationStatus.SUCCEEDED
    assert adapter.replace_calls == 1
    assert any(page.path.startswith("summaries/") for page in snapshot.pages)


async def test_failed_compilation_can_be_retried_without_partial_domain_state(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    workspace_id = context.workspace.id
    knowledge_base_id = context.knowledge_base.id
    store = InMemoryObjectStore()
    source_version_id = await _capture(session, store, context, suffix="retry")
    unavailable = KnowledgeCompilation(session, store, UnavailableOpenKBAdapter())
    submitted = await unavailable.submit(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_version_id=source_version_id,
    )

    failed = await unavailable.run(workspace_id, submitted.job.id)
    assert failed.status == CompilationStatus.FAILED
    assert failed.error_code == "openkb_unavailable"
    assert failed.error_detail == "OpenKBUnavailable"
    assert await CompilationRepository(session).get_document(
        workspace_id, knowledge_base_id, source_version_id
    ) is None

    recovered = await KnowledgeCompilation(session, store, FakeOpenKBAdapter()).run(
        workspace_id, submitted.job.id
    )
    assert recovered.status == CompilationStatus.SUCCEEDED
    assert recovered.attempts == 2


async def test_fake_adapter_serializes_same_workspace_but_allows_two_documents() -> None:
    adapter = FakeOpenKBAdapter(delay_seconds=0.01)

    def document(name: str) -> CompilationDocument:
        markdown = f"# {name}\n"
        return CompilationDocument(
            id=str(uuid.uuid4()),
            title=name,
            markdown=markdown,
            content_sha256=hashlib.sha256(markdown.encode()).hexdigest(),
        )

    await asyncio.gather(
        adapter.compile("workspace", document("one")),
        adapter.compile("workspace", document("two")),
    )
    snapshot = await adapter.snapshot("workspace")

    assert adapter.max_active["workspace"] == 1
    assert len([page for page in snapshot.pages if page.path.startswith("summaries/")]) == 2


async def test_http_adapter_falls_back_only_when_primary_is_unavailable() -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "primary":
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "worker_version": "openkb-0.4.4@rollback",
                "pages": [
                    {"path": "index.md", "markdown": "# Index", "wikilinks": []}
                ],
            },
        )

    adapter = HttpOpenKBAdapter(
        "http://primary",
        fallback_url="http://fallback",
        transport=httpx.MockTransport(handler),
    )
    snapshot = await adapter.snapshot("workspace")

    assert requested_hosts == ["primary", "fallback"]
    assert snapshot.worker_version == "openkb-0.4.4@rollback"


def test_business_packages_do_not_import_openkb_or_openai_agents() -> None:
    source_root = Path(__file__).parents[1] / "src" / "flywiki"
    violations: list[str] = []
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import openkb" in text or "from openkb" in text or "from agents" in text:
            violations.append(str(path.relative_to(source_root)))
    assert violations == []


async def test_compilation_job_is_workspace_scoped(session: AsyncSession) -> None:
    context = await bootstrap_default_context(session, Settings())
    store = InMemoryObjectStore()
    source_version_id = await _capture(session, store, context, suffix="private")
    submitted = await KnowledgeCompilation(session, store, FakeOpenKBAdapter()).submit(
        workspace_id=context.workspace.id,
        knowledge_base_id=context.knowledge_base.id,
        source_version_id=source_version_id,
    )

    from flywiki.compilation.repository import CompilationResourceNotFound

    try:
        await CompilationRepository(session).get_job(uuid.uuid4(), submitted.job.id)
    except CompilationResourceNotFound:
        pass
    else:
        raise AssertionError("cross-Workspace compilation job was disclosed")


async def test_compilation_api_dispatches_and_reports_compiled_wiki(
    database: Database,
) -> None:
    settings = Settings(bootstrap_on_start=False)
    store = InMemoryObjectStore()
    adapter = FakeOpenKBAdapter()
    dispatched: list[tuple[uuid.UUID, uuid.UUID]] = []
    async with database.sessions() as session:
        context = await bootstrap_default_context(session, settings)
        source_version_id = await _capture(session, store, context, suffix="api-compile")
    app = create_app(
        settings,
        database=database,
        object_store=store,
        openkb_adapter=adapter,
        capture_dispatcher=lambda _workspace_id, _job_id: None,
        compilation_dispatcher=lambda workspace_id, job_id: dispatched.append(
            (workspace_id, job_id)
        ),
    )
    base = f"/api/workspaces/{context.workspace.id}"
    headers = {"X-Workspace-ID": str(context.workspace.id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        submitted = await client.post(
            f"{base}/knowledge-bases/{context.knowledge_base.id}/compilations",
            headers=headers,
            json={"source_version_id": str(source_version_id)},
        )
        assert submitted.status_code == 202
        job_id = uuid.UUID(submitted.json()["id"])
        assert dispatched == [(context.workspace.id, job_id)]

        async with database.sessions() as session:
            completed = await KnowledgeCompilation(session, store, adapter).run(
                context.workspace.id, job_id
            )
            assert completed.status == CompilationStatus.SUCCEEDED

        job = await client.get(f"{base}/compilations/{job_id}", headers=headers)
        wiki = await client.get(
            f"{base}/knowledge-bases/{context.knowledge_base.id}/compiled-wiki",
            headers=headers,
        )

    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"
    assert wiki.status_code == 200
    assert any(page["path"] == "index.md" for page in wiki.json()["pages"])
