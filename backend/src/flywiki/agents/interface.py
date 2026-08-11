import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AcquiredSource:
    canonical_url: str
    markdown: str
    backend: str
    source_version_id: uuid.UUID


@dataclass(frozen=True)
class AgentRunRequest:
    run_id: uuid.UUID
    workspace_id: uuid.UUID
    prompt: str
    source_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentRunResult:
    answer: str
    acquired_sources: tuple[AcquiredSource, ...]


class SourceAcquisitionCapability(Protocol):
    @property
    def acquired_sources(self) -> tuple[AcquiredSource, ...]: ...

    async def acquire_source(self, url: str) -> AcquiredSource: ...


class AgentRuntime(Protocol):
    async def run(
        self,
        request: AgentRunRequest,
        capability: SourceAcquisitionCapability,
    ) -> AgentRunResult: ...
