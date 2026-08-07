import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flywiki.db.base import Base


class SourceKind(enum.StrEnum):
    WEB = "web"


class SourceArtifactRole(enum.StrEnum):
    RAW_HTML = "raw_html"
    MARKDOWN = "markdown"
    METADATA = "metadata"
    LOCATOR_MAP = "locator_map"
    ATTACHMENT = "attachment"


class CaptureStatus(enum.StrEnum):
    ACCEPTED = "accepted"
    FETCHING = "fetching"
    READY_FOR_COMPILE = "ready_for_compile"
    FAILED = "failed"


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "identity_key",
            name="uq_sources_workspace_id_identity_key",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_sources_workspace_id_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, native_enum=False, length=32), nullable=False
    )
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    versions: Mapped[list["SourceVersion"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceVersion(Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "source_id"],
            ["sources.workspace_id", "sources.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workspace_id",
            "source_id",
            "content_sha256",
            name="uq_source_versions_workspace_source_content",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_source_versions_workspace_id_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="versions")
    artifacts: Mapped[list["SourceArtifact"]] = relationship(
        back_populates="source_version",
        cascade="all, delete-orphan",
        order_by="SourceArtifact.created_at, SourceArtifact.id",
    )
    receipts: Mapped[list["SourceCaptureReceipt"]] = relationship(
        back_populates="source_version", cascade="all, delete-orphan"
    )


class SourceArtifact(Base):
    __tablename__ = "source_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workspace_id",
            "source_version_id",
            "role",
            "name",
            name="uq_source_artifacts_version_role_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    role: Mapped[SourceArtifactRole] = mapped_column(
        Enum(SourceArtifactRole, native_enum=False, length=32), nullable=False
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    object_key: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_version: Mapped[SourceVersion] = relationship(back_populates="artifacts")


class SourceCaptureReceipt(Base):
    __tablename__ = "source_capture_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_source_capture_receipts_workspace_id_idempotency_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_version: Mapped[SourceVersion] = relationship(back_populates="receipts")


class CaptureJob(Base):
    __tablename__ = "capture_jobs"
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
        UniqueConstraint("workspace_id", "id", name="uq_capture_jobs_workspace_id_id"),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_capture_jobs_workspace_id_idempotency_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(index=True)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CaptureStatus] = mapped_column(
        Enum(CaptureStatus, native_enum=False, length=32),
        default=CaptureStatus.ACCEPTED,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EditableNote(Base):
    __tablename__ = "editable_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_editable_notes_workspace_id_id"),
        UniqueConstraint(
            "workspace_id",
            "source_version_id",
            name="uq_editable_notes_workspace_id_source_version_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    versions: Mapped[list["NoteVersion"]] = relationship(
        back_populates="note",
        cascade="all, delete-orphan",
        order_by="NoteVersion.version_number",
    )


class NoteVersion(Base):
    __tablename__ = "note_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "note_id"],
            ["editable_notes.workspace_id", "editable_notes.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_note_versions_workspace_id_id"),
        UniqueConstraint(
            "workspace_id",
            "note_id",
            "version_number",
            name="uq_note_versions_workspace_note_version_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    note_id: Mapped[uuid.UUID] = mapped_column(index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    note: Mapped[EditableNote] = relationship(back_populates="versions")


def _reject_immutable_update(_mapper: object, _connection: object, target: object) -> None:
    raise ValueError(f"{type(target).__name__} is immutable")


event.listen(SourceVersion, "before_update", _reject_immutable_update)
event.listen(SourceArtifact, "before_update", _reject_immutable_update)
event.listen(NoteVersion, "before_update", _reject_immutable_update)
