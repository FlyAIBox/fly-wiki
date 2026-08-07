import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.sources.models import (
    CaptureJob,
    EditableNote,
    NoteVersion,
    Source,
    SourceArtifact,
    SourceCaptureReceipt,
    SourceKind,
    SourceVersion,
)


class SourceResourceNotFound(LookupError):
    """Raised without disclosing whether a resource exists in another Workspace."""


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_source(
        self, workspace_id: uuid.UUID, kind: SourceKind, identity_key: str
    ) -> Source | None:
        return await self._session.scalar(
            select(Source).where(
                Source.workspace_id == workspace_id,
                Source.kind == kind,
                Source.identity_key == identity_key,
            )
        )

    async def get_source(self, workspace_id: uuid.UUID, source_id: uuid.UUID) -> Source:
        source = await self._session.scalar(
            select(Source).where(
                Source.workspace_id == workspace_id,
                Source.id == source_id,
            )
        )
        if source is None:
            raise SourceResourceNotFound("Source not found")
        return source

    async def find_version_by_content(
        self,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        content_sha256: str,
    ) -> SourceVersion | None:
        return await self._session.scalar(
            select(SourceVersion).where(
                SourceVersion.workspace_id == workspace_id,
                SourceVersion.source_id == source_id,
                SourceVersion.content_sha256 == content_sha256,
            )
        )

    async def get_version(
        self, workspace_id: uuid.UUID, source_version_id: uuid.UUID
    ) -> SourceVersion:
        version = await self._session.scalar(
            select(SourceVersion).where(
                SourceVersion.workspace_id == workspace_id,
                SourceVersion.id == source_version_id,
            )
        )
        if version is None:
            raise SourceResourceNotFound("Source Version not found")
        return version

    async def find_version_by_idempotency_key(
        self, workspace_id: uuid.UUID, idempotency_key: str
    ) -> SourceVersion | None:
        return await self._session.scalar(
            select(SourceVersion)
            .join(
                SourceCaptureReceipt,
                (SourceCaptureReceipt.workspace_id == SourceVersion.workspace_id)
                & (SourceCaptureReceipt.source_version_id == SourceVersion.id),
            )
            .where(
                SourceCaptureReceipt.workspace_id == workspace_id,
                SourceCaptureReceipt.idempotency_key == idempotency_key,
            )
        )

    async def list_artifacts(
        self, workspace_id: uuid.UUID, source_version_id: uuid.UUID
    ) -> list[SourceArtifact]:
        if (
            await self._session.scalar(
                select(SourceVersion.id).where(
                    SourceVersion.workspace_id == workspace_id,
                    SourceVersion.id == source_version_id,
                )
            )
            is None
        ):
            raise SourceResourceNotFound("Source Version not found")
        artifacts = await self._session.scalars(
            select(SourceArtifact)
            .where(
                SourceArtifact.workspace_id == workspace_id,
                SourceArtifact.source_version_id == source_version_id,
            )
            .order_by(SourceArtifact.created_at, SourceArtifact.id)
        )
        return list(artifacts)

    async def get_artifact(
        self,
        workspace_id: uuid.UUID,
        source_version_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> SourceArtifact:
        artifact = await self._session.scalar(
            select(SourceArtifact).where(
                SourceArtifact.workspace_id == workspace_id,
                SourceArtifact.source_version_id == source_version_id,
                SourceArtifact.id == artifact_id,
            )
        )
        if artifact is None:
            raise SourceResourceNotFound("Source Artifact not found")
        return artifact

    async def find_capture_job(
        self, workspace_id: uuid.UUID, idempotency_key: str
    ) -> CaptureJob | None:
        return await self._session.scalar(
            select(CaptureJob).where(
                CaptureJob.workspace_id == workspace_id,
                CaptureJob.idempotency_key == idempotency_key,
            )
        )

    async def get_capture_job(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> CaptureJob:
        job = await self._session.scalar(
            select(CaptureJob).where(
                CaptureJob.workspace_id == workspace_id,
                CaptureJob.id == job_id,
            )
        )
        if job is None:
            raise SourceResourceNotFound("Capture Job not found")
        return job

    async def find_note_by_source_version(
        self, workspace_id: uuid.UUID, source_version_id: uuid.UUID
    ) -> EditableNote | None:
        return await self._session.scalar(
            select(EditableNote).where(
                EditableNote.workspace_id == workspace_id,
                EditableNote.source_version_id == source_version_id,
            )
        )

    async def get_note(self, workspace_id: uuid.UUID, note_id: uuid.UUID) -> EditableNote:
        note = await self._session.scalar(
            select(EditableNote).where(
                EditableNote.workspace_id == workspace_id,
                EditableNote.id == note_id,
            )
        )
        if note is None:
            raise SourceResourceNotFound("Editable Note not found")
        return note

    async def list_note_versions(
        self, workspace_id: uuid.UUID, note_id: uuid.UUID
    ) -> list[NoteVersion]:
        await self.get_note(workspace_id, note_id)
        versions = await self._session.scalars(
            select(NoteVersion)
            .where(
                NoteVersion.workspace_id == workspace_id,
                NoteVersion.note_id == note_id,
            )
            .order_by(NoteVersion.version_number)
        )
        return list(versions)

    async def get_latest_note_version(
        self, workspace_id: uuid.UUID, note_id: uuid.UUID
    ) -> NoteVersion:
        await self.get_note(workspace_id, note_id)
        version = await self._session.scalar(
            select(NoteVersion)
            .where(
                NoteVersion.workspace_id == workspace_id,
                NoteVersion.note_id == note_id,
            )
            .order_by(NoteVersion.version_number.desc())
            .limit(1)
        )
        if version is None:
            raise SourceResourceNotFound("Note Version not found")
        return version
