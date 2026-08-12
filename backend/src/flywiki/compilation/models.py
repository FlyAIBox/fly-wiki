import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKeyConstraint, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from flywiki.db.base import Base


class CompilationOperation(enum.StrEnum):
    COMPILE = "compile"
    REBUILD = "rebuild"


class CompilationStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "note_version_id"],
            ["note_versions.workspace_id", "note_versions.id"],
        ),
        UniqueConstraint("workspace_id", "id", name="uq_knowledge_documents_workspace_id_id"),
        UniqueConstraint(
            "workspace_id",
            "knowledge_base_id",
            "source_version_id",
            name="uq_knowledge_documents_kb_source_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    note_version_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    openkb_document_id: Mapped[str] = mapped_column(String(160), nullable=False)
    compiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CompilationJob(Base):
    __tablename__ = "compilation_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "note_version_id"],
            ["note_versions.workspace_id", "note_versions.id"],
        ),
        UniqueConstraint("workspace_id", "id", name="uq_compilation_jobs_workspace_id_id"),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_compilation_jobs_workspace_id_idempotency_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(index=True)
    operation: Mapped[CompilationOperation] = mapped_column(
        Enum(CompilationOperation, native_enum=False, length=24), nullable=False
    )
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    note_version_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CompilationStatus] = mapped_column(
        Enum(CompilationStatus, native_enum=False, length=24),
        default=CompilationStatus.QUEUED,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worker_version: Mapped[str | None] = mapped_column(String(160))
    page_count: Mapped[int | None] = mapped_column(Integer)
    wikilink_count: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
