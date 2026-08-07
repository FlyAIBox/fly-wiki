import uuid

from httpx import ASGITransport, AsyncClient

from flywiki.app import create_app
from flywiki.config import Settings
from flywiki.db.database import Database
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import FetchedWebPage
from flywiki.sources.pipeline import CapturePipeline
from flywiki.sources.storage import InMemoryObjectStore
from flywiki.workspaces.bootstrap import bootstrap_default_context


class FakeFetcher:
    async def fetch(self, url: str) -> FetchedWebPage:
        return FetchedWebPage(
            url,
            b"<html><head><title>API</title></head><body><p>API evidence.</p></body></html>",
            "text/html",
        )


async def test_capture_and_editable_note_api(database: Database) -> None:
    settings = Settings(bootstrap_on_start=False)
    async with database.sessions() as session:
        context = await bootstrap_default_context(session, settings)
    object_store = InMemoryObjectStore()
    dispatched: list[tuple[uuid.UUID, uuid.UUID]] = []
    app = create_app(
        settings,
        database=database,
        object_store=object_store,
        capture_dispatcher=lambda workspace_id, job_id: dispatched.append((workspace_id, job_id)),
    )
    base = f"/api/workspaces/{context.workspace.id}"
    headers = {"X-Workspace-ID": str(context.workspace.id)}
    payload = {
        "url": "https://example.com/api#fragment",
        "idempotency_key": "api:capture:1",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        submitted = await client.post(
            f"{base}/knowledge-bases/{context.knowledge_base.id}/captures",
            json=payload,
            headers=headers,
        )
        replay = await client.post(
            f"{base}/knowledge-bases/{context.knowledge_base.id}/captures",
            json=payload,
            headers=headers,
        )

        assert submitted.status_code == 202
        assert replay.status_code == 202
        job_id = uuid.UUID(submitted.json()["id"])
        assert replay.json()["id"] == str(job_id)
        assert dispatched == [(context.workspace.id, job_id)]

        async with database.sessions() as session:
            completed = await CapturePipeline(
                session,
                object_store,
                FakeFetcher(),
                WebPageExtractor(),
            ).run(context.workspace.id, job_id)
        job = await client.get(f"{base}/captures/{job_id}", headers=headers)
        assert job.json()["status"] == "ready_for_compile"

        source_version = await client.get(
            f"{base}/source-versions/{completed.source_version_id}",
            headers=headers,
        )
        assert source_version.status_code == 200
        version_payload = source_version.json()
        assert version_payload["canonical_uri"] == "https://example.com/api"
        assert version_payload["editable_note_id"]
        raw_artifact = next(
            item for item in version_payload["artifacts"] if item["role"] == "raw_html"
        )
        raw = await client.get(
            f"{base}/source-versions/{completed.source_version_id}/artifacts/{raw_artifact['id']}",
            headers=headers,
        )
        assert raw.status_code == 200
        assert b"API evidence." in raw.content

        note_id = version_payload["editable_note_id"]
        note = await client.get(f"{base}/editable-notes/{note_id}", headers=headers)
        assert note.json()["current_version"]["version_number"] == 1
        saved = await client.put(
            f"{base}/editable-notes/{note_id}",
            headers=headers,
            json={"markdown": "# User edit\n", "base_version_number": 1},
        )
        assert saved.status_code == 200
        assert [item["version_number"] for item in saved.json()["history"]] == [1, 2]


async def test_source_api_does_not_disclose_cross_workspace_resources(
    database: Database,
) -> None:
    settings = Settings(bootstrap_on_start=False)
    async with database.sessions() as session:
        context = await bootstrap_default_context(session, settings)
    app = create_app(
        settings,
        database=database,
        object_store=InMemoryObjectStore(),
        capture_dispatcher=lambda _workspace_id, _job_id: None,
    )
    unknown_workspace = uuid.uuid4()
    path = f"/api/workspaces/{unknown_workspace}/captures/{uuid.uuid4()}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mismatched = await client.get(
            path,
            headers={"X-Workspace-ID": str(context.workspace.id)},
        )
        scoped_but_missing = await client.get(
            path,
            headers={"X-Workspace-ID": str(unknown_workspace)},
        )

    assert mismatched.status_code == 403
    assert scoped_but_missing.status_code == 404


async def test_submit_records_queue_failure(database: Database) -> None:
    settings = Settings(bootstrap_on_start=False)
    async with database.sessions() as session:
        context = await bootstrap_default_context(session, settings)

    def fail_dispatch(_workspace_id: uuid.UUID, _job_id: uuid.UUID) -> None:
        raise ConnectionError("broker unavailable")

    app = create_app(
        settings,
        database=database,
        object_store=InMemoryObjectStore(),
        capture_dispatcher=fail_dispatch,
    )
    base = f"/api/workspaces/{context.workspace.id}"
    headers = {"X-Workspace-ID": str(context.workspace.id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"{base}/knowledge-bases/{context.knowledge_base.id}/captures",
            headers=headers,
            json={
                "url": "https://example.com/queue-failure",
                "idempotency_key": "api:queue-failure:1",
            },
        )

    assert response.status_code == 503
