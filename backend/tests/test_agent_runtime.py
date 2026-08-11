import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.agents.gateway import SourceAcquisitionGateway
from flywiki.agents.interface import (
    AcquiredSource,
    AgentRunRequest,
)
from flywiki.agents.runtime import DeepAgentsRuntime
from flywiki.config import Settings
from flywiki.sources.acquisition import SourceAcquisitionService
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import FetchedAttachment, FetchedWebPage
from flywiki.sources.repository import SourceRepository
from flywiki.sources.storage import InMemoryObjectStore
from flywiki.workspaces.bootstrap import bootstrap_default_context


class FakeCapability:
    def __init__(self) -> None:
        self._acquired: list[AcquiredSource] = []

    @property
    def acquired_sources(self) -> tuple[AcquiredSource, ...]:
        return tuple(self._acquired)

    async def acquire_source(self, url: str) -> AcquiredSource:
        acquired = AcquiredSource(
            canonical_url=url,
            markdown="# Captured\n\nEvidence.\n",
            backend="agent-reach:twitter",
            source_version_id=uuid.uuid4(),
        )
        self._acquired.append(acquired)
        return acquired


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeGraph:
    def __init__(self) -> None:
        self.tool = None
        self.invocation = None

    async def ainvoke(self, payload, *, config):  # type: ignore[no-untyped-def]
        self.invocation = (payload, config)
        assert self.tool is not None
        tool_output = await self.tool("https://x.com/flywiki/status/123")
        assert "Evidence." in tool_output
        return {"messages": [FakeMessage("Research answer with evidence.")]}


class FakeSourceFetcher:
    async def fetch(self, url: str) -> FetchedWebPage:
        return FetchedWebPage(
            url,
            b"# Captured source\n\nEvidence from Agent Reach.\n",
            "text/markdown",
            backend="agent-reach:twitter",
        )

    async def fetch_attachment(self, url: str) -> FetchedAttachment:
        return FetchedAttachment(url, b"asset", "image/png", "asset.png")


async def test_deep_agents_runtime_loads_agent_reach_skill_and_uses_gateway_tool(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "agent-reach"
    references = skill_root / "references"
    references.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: agent-reach\ndescription: acquire internet sources\n---\n# Agent Reach\n"
    )
    (references / "social.md").write_text("# Social routes\n")
    (skill_root / ".DS_Store").write_bytes(b"\x00\xff")

    graph = FakeGraph()
    factory_arguments = {}

    def agent_factory(**kwargs):  # type: ignore[no-untyped-def]
        factory_arguments.update(kwargs)
        graph.tool = kwargs["tools"][0]
        return graph

    runtime = DeepAgentsRuntime(
        model="openai:test-model",
        skill_root=skill_root,
        agent_factory=agent_factory,
        file_data_factory=lambda content: {"content": content},
    )
    run_id = uuid.uuid4()
    capability = FakeCapability()

    result = await runtime.run(
        AgentRunRequest(
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            prompt="Read the supplied source and summarize it.",
            source_urls=("https://x.com/flywiki/status/123",),
        ),
        capability,
    )

    assert result.answer == "Research answer with evidence."
    assert result.acquired_sources == capability.acquired_sources
    assert factory_arguments["model"] == "openai:test-model"
    assert factory_arguments["skills"] == ["/skills/"]
    payload, config = graph.invocation
    assert "/skills/agent-reach/SKILL.md" in payload["files"]
    assert "/skills/agent-reach/references/social.md" in payload["files"]
    assert "/skills/agent-reach/.DS_Store" not in payload["files"]
    assert config["configurable"]["thread_id"] == str(run_id)


async def test_source_acquisition_gateway_creates_immutable_evidence_before_returning(
    session: AsyncSession,
) -> None:
    context = await bootstrap_default_context(session, Settings())
    store = InMemoryObjectStore()
    capability = SourceAcquisitionGateway(
        SourceAcquisitionService(
            session,
            store,
            FakeSourceFetcher(),
            WebPageExtractor(),
        ),
        workspace_id=context.workspace.id,
        run_id=uuid.uuid4(),
    )

    acquired = await capability.acquire_source("https://x.com/flywiki/status/123")

    version = await SourceRepository(session).get_version(
        context.workspace.id,
        acquired.source_version_id,
    )
    note = await SourceRepository(session).find_note_by_source_version(
        context.workspace.id,
        version.id,
    )
    assert acquired.backend == "agent-reach:twitter"
    assert "Evidence from Agent Reach." in acquired.markdown
    assert note is not None
    assert capability.acquired_sources == (acquired,)
