import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from flywiki.compilation.models import CompilationOperation, CompilationStatus


class SubmitCompilationRequest(BaseModel):
    source_version_id: uuid.UUID
    use_editable_note: bool = True


class SubmitRebuildRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)


class CompilationJobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    operation: CompilationOperation
    source_version_id: uuid.UUID | None
    note_version_id: uuid.UUID | None
    idempotency_key: str
    status: CompilationStatus
    attempts: int
    worker_version: str | None
    page_count: int | None
    wikilink_count: int | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class WikiPageView(BaseModel):
    path: str
    markdown: str
    wikilinks: list[str]


class CompilationSnapshotView(BaseModel):
    worker_version: str
    pages: list[WikiPageView]
