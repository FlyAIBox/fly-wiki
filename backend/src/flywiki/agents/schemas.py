import uuid

from pydantic import BaseModel, Field


class StartAgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8_000)
    source_urls: list[str] = Field(default_factory=list, max_length=20)


class AcquiredSourceView(BaseModel):
    canonical_url: str
    backend: str
    source_version_id: uuid.UUID


class AgentRunView(BaseModel):
    run_id: uuid.UUID
    answer: str
    acquired_sources: list[AcquiredSourceView]
