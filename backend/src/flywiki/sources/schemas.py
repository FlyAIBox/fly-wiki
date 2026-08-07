import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from flywiki.sources.models import CaptureStatus, SourceArtifactRole


class CaptureRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    idempotency_key: str = Field(min_length=1, max_length=255)


class CaptureJobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    canonical_url: str
    idempotency_key: str
    status: CaptureStatus
    attempts: int
    source_version_id: uuid.UUID | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class SourceArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: SourceArtifactRole
    name: str
    content_type: str
    content_sha256: str
    size_bytes: int


class SourceVersionView(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    source_id: uuid.UUID
    canonical_uri: str
    content_sha256: str
    captured_at: datetime
    artifacts: list[SourceArtifactView]
    editable_note_id: uuid.UUID | None


class NoteVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    markdown: str
    created_at: datetime


class EditableNoteView(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    source_version_id: uuid.UUID
    current_version: NoteVersionView
    history: list[NoteVersionView]


class SaveEditableNoteRequest(BaseModel):
    markdown: str = Field(min_length=1)
    base_version_number: int = Field(ge=1)
