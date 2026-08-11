import uuid

from httpx import ASGITransport, AsyncClient

from flywiki.agents.interface import AgentRunRequest, AgentRunResult
from flywiki.app import create_app
from flywiki.config import Settings
from flywiki.db.database import Database
from flywiki.sources.fetcher import FetchedAttachment, FetchedWebPage
from flywiki.sources.repository import SourceRepository
from flywiki.sources.storage import InMemoryObjectStore
from flywiki.workspaces.bootstrap import bootstrap_default_context


class FakeSourceFetcher:
    async def fetch(self, url: str) -> FetchedWebPage:
        return FetchedWebPage(
            url,
            b"# Agent source\n\nEvidence acquired by the gateway.\n",
            "text/markdown",
            backend="agent-reach:twitter",
        )

    async def fetch_attachment(self, url: str) -> FetchedAttachment:
        return FetchedAttachment(url, b"asset", "image/png", "asset.png")


class FakeAgentRuntime:
    def __init__(self) -> None:
        self.requests: list[AgentRunRequest] = []

    async def run(self, request, capability):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        acquired = await capability.acquire_source(request.source_urls[0])
        return AgentRunResult(
            answer="Grounded answer.",
            acquired_sources=(acquired,),
        )


async def test_agent_run_api_uses_runtime_and_persists_acquired_sources(
    database: Database,
) -> None:
    settings = Settings(bootstrap_on_start=False)
    async with database.sessions() as session:
        context = await bootstrap_default_context(session, settings)
    runtime = FakeAgentRuntime()
    app = create_app(
        settings,
        database=database,
        object_store=InMemoryObjectStore(),
        agent_runtime=runtime,
        source_fetcher_factory=lambda _settings: FakeSourceFetcher(),
    )
    base = f"/api/workspaces/{context.workspace.id}"
    headers = {"X-Workspace-ID": str(context.workspace.id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"{base}/knowledge-bases/{context.knowledge_base.id}/agent-runs",
            headers=headers,
            json={
                "prompt": "Summarize the supplied source.",
                "source_urls": ["https://x.com/flywiki/status/123"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Grounded answer."
    assert payload["run_id"] == str(runtime.requests[0].run_id)
    assert payload["acquired_sources"][0]["backend"] == "agent-reach:twitter"
    source_version_id = uuid.UUID(payload["acquired_sources"][0]["source_version_id"])
    async with database.sessions() as session:
        version = await SourceRepository(session).get_version(
            context.workspace.id,
            source_version_id,
        )
    assert version.id == source_version_id
