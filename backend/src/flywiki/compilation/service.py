from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.compilation.interface import (
    CompilationDocument,
    CompilationSnapshot,
    OpenKBAdapter,
    OpenKBUnavailable,
    OpenKBWorkspaceNotFound,
)
from flywiki.compilation.models import (
    CompilationJob,
    CompilationOperation,
    CompilationStatus,
    KnowledgeDocument,
)
from flywiki.compilation.repository import CompilationRepository
from flywiki.sources.models import CaptureJob, CaptureStatus, NoteVersion, SourceArtifactRole
from flywiki.sources.repository import SourceRepository
from flywiki.sources.storage import ObjectStore
from flywiki.workspaces.repository import WorkspaceRepository


class CompilationIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class SubmittedCompilation:
    job: CompilationJob
    created: bool


class KnowledgeCompilation:
    """Deep Module for submission, compilation, replacement, and rebuild."""

    def __init__(
        self,
        session: AsyncSession,
        object_store: ObjectStore,
        adapter: OpenKBAdapter,
    ) -> None:
        self._session = session
        self._object_store = object_store
        self._adapter = adapter
        self._repository = CompilationRepository(session)
        self._sources = SourceRepository(session)

    async def submit(
        self,
        *,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        source_version_id: uuid.UUID,
        use_editable_note: bool = True,
    ) -> SubmittedCompilation:
        await WorkspaceRepository(self._session).get_knowledge_base(
            workspace_id, knowledge_base_id
        )
        await self._sources.get_version(workspace_id, source_version_id)
        await self._require_capture_membership(
            workspace_id, knowledge_base_id, source_version_id
        )
        note_version = (
            await self._latest_note_version(workspace_id, source_version_id)
            if use_editable_note
            else None
        )
        note_token = str(note_version.id) if note_version else "source-only"
        key = f"compile:{knowledge_base_id}:{source_version_id}:{note_token}"
        return await self._submit_job(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            operation=CompilationOperation.COMPILE,
            source_version_id=source_version_id,
            note_version_id=note_version.id if note_version else None,
            idempotency_key=key,
        )

    async def submit_rebuild(
        self,
        *,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        idempotency_key: str,
    ) -> SubmittedCompilation:
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValueError("idempotency_key must contain 1-255 characters")
        await WorkspaceRepository(self._session).get_knowledge_base(
            workspace_id, knowledge_base_id
        )
        return await self._submit_job(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            operation=CompilationOperation.REBUILD,
            source_version_id=None,
            note_version_id=None,
            idempotency_key=f"rebuild:{knowledge_base_id}:{idempotency_key}",
        )

    async def run(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> CompilationJob:
        job = await self._repository.get_job(workspace_id, job_id)
        if job.status == CompilationStatus.SUCCEEDED:
            return job

        job.status = CompilationStatus.RUNNING
        job.attempts += 1
        job.error_code = None
        job.error_detail = None
        await self._session.commit()

        try:
            await self._repository.lock_knowledge_base(workspace_id, job.knowledge_base_id)
            if job.operation == CompilationOperation.REBUILD:
                snapshot = await self._replace_from_registry(
                    workspace_id, job.knowledge_base_id
                )
            else:
                snapshot = await self._compile_one(job)
            job = await self._repository.get_job(workspace_id, job_id)
            self._record_success(job, snapshot)
            await self._session.commit()
            await self._session.refresh(job)
            return job
        except Exception as exc:
            await self._session.rollback()
            job = await self._repository.get_job(workspace_id, job_id)
            job.status = CompilationStatus.FAILED
            job.error_code = (
                "openkb_unavailable"
                if isinstance(exc, (OpenKBUnavailable, OpenKBWorkspaceNotFound))
                else "compilation_failed"
            )
            job.error_detail = type(exc).__name__
            await self._session.commit()
            await self._session.refresh(job)
            return job

    async def snapshot(
        self, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> CompilationSnapshot:
        await WorkspaceRepository(self._session).get_knowledge_base(
            workspace_id, knowledge_base_id
        )
        return await self._adapter.snapshot(_workspace_key(workspace_id, knowledge_base_id))

    async def _compile_one(self, job: CompilationJob) -> CompilationSnapshot:
        if job.source_version_id is None:
            raise RuntimeError("compile job is missing Source Version")
        document = await self._build_document(
            job.workspace_id, job.source_version_id, job.note_version_id
        )
        existing = await self._repository.get_document(
            job.workspace_id, job.knowledge_base_id, job.source_version_id
        )
        workspace_key = _workspace_key(job.workspace_id, job.knowledge_base_id)

        if existing is None:
            registered = await self._repository.list_documents(
                job.workspace_id, job.knowledge_base_id
            )
            if registered:
                try:
                    await self._adapter.snapshot(workspace_key)
                except OpenKBWorkspaceNotFound:
                    documents = tuple(
                        [
                            await self._build_document(
                                item.workspace_id,
                                item.source_version_id,
                                item.note_version_id,
                            )
                            for item in registered
                        ]
                    ) + (document,)
                    snapshot = await self._adapter.replace(workspace_key, documents)
                else:
                    snapshot = await self._adapter.compile(workspace_key, document)
            else:
                snapshot = await self._adapter.compile(workspace_key, document)
            existing = KnowledgeDocument(
                workspace_id=job.workspace_id,
                knowledge_base_id=job.knowledge_base_id,
                source_version_id=job.source_version_id,
                note_version_id=job.note_version_id,
                input_sha256=document.content_sha256,
                openkb_document_id=document.id,
            )
            self._session.add(existing)
            await self._session.flush()
            return snapshot

        if existing.input_sha256 == document.content_sha256:
            try:
                return await self._adapter.snapshot(workspace_key)
            except OpenKBWorkspaceNotFound:
                return await self._replace_with_document(job, document)

        return await self._replace_with_document(job, document)

    async def _replace_with_document(
        self, job: CompilationJob, replacement: CompilationDocument
    ) -> CompilationSnapshot:
        registered = await self._repository.list_documents(
            job.workspace_id, job.knowledge_base_id
        )
        documents: list[CompilationDocument] = []
        for item in registered:
            if item.source_version_id == job.source_version_id:
                documents.append(replacement)
            else:
                documents.append(
                    await self._build_document(
                        item.workspace_id, item.source_version_id, item.note_version_id
                    )
                )
        snapshot = await self._adapter.replace(
            _workspace_key(job.workspace_id, job.knowledge_base_id), tuple(documents)
        )
        current = await self._repository.get_document(
            job.workspace_id, job.knowledge_base_id, job.source_version_id
        )
        if current is None:
            raise RuntimeError("Knowledge Document disappeared while locked")
        current.note_version_id = job.note_version_id
        current.input_sha256 = replacement.content_sha256
        current.openkb_document_id = replacement.id
        return snapshot

    async def _replace_from_registry(
        self, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> CompilationSnapshot:
        registered = await self._repository.list_documents(workspace_id, knowledge_base_id)
        if not registered:
            raise ValueError("Knowledge Base has no compiled Source Versions to rebuild")
        documents = tuple(
            [
                await self._build_document(
                    item.workspace_id, item.source_version_id, item.note_version_id
                )
                for item in registered
            ]
        )
        return await self._adapter.replace(
            _workspace_key(workspace_id, knowledge_base_id), documents
        )

    async def _build_document(
        self,
        workspace_id: uuid.UUID,
        source_version_id: uuid.UUID,
        note_version_id: uuid.UUID | None,
    ) -> CompilationDocument:
        version = await self._sources.get_version(workspace_id, source_version_id)
        source = await self._sources.get_source(workspace_id, version.source_id)
        artifacts = await self._sources.list_artifacts(workspace_id, source_version_id)
        markdown_artifact = next(
            (item for item in artifacts if item.role == SourceArtifactRole.MARKDOWN), None
        )
        if markdown_artifact is None:
            raise RuntimeError("Source Version has no Markdown artifact")
        original = (await self._object_store.get(markdown_artifact.object_key)).decode("utf-8")
        sections = [
            f"# {source.canonical_uri}",
            f"> FlyWiki Source Version: `{source_version_id}`",
            "## Original Source Snapshot",
            original.strip(),
        ]
        if note_version_id is not None:
            note_version = await self._session.scalar(
                select(NoteVersion).where(
                    NoteVersion.workspace_id == workspace_id,
                    NoteVersion.id == note_version_id,
                )
            )
            if note_version is None:
                raise RuntimeError("Selected Note Version not found")
            sections.extend(
                [
                    "## User Editable Note",
                    f"> FlyWiki Note Version: `{note_version.version_number}`",
                    note_version.markdown.strip(),
                ]
            )
        markdown = "\n\n".join(sections).strip() + "\n"
        digest = hashlib.sha256(markdown.encode()).hexdigest()
        return CompilationDocument(
            id=str(source_version_id),
            title=source.canonical_uri,
            markdown=markdown,
            content_sha256=digest,
        )

    async def _latest_note_version(
        self, workspace_id: uuid.UUID, source_version_id: uuid.UUID
    ) -> NoteVersion | None:
        note = await self._sources.find_note_by_source_version(
            workspace_id, source_version_id
        )
        if note is None:
            return None
        return await self._sources.get_latest_note_version(workspace_id, note.id)

    async def _require_capture_membership(
        self,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        source_version_id: uuid.UUID,
    ) -> None:
        capture = await self._session.scalar(
            select(CaptureJob.id).where(
                CaptureJob.workspace_id == workspace_id,
                CaptureJob.knowledge_base_id == knowledge_base_id,
                CaptureJob.source_version_id == source_version_id,
                CaptureJob.status == CaptureStatus.READY_FOR_COMPILE,
            )
        )
        if capture is None:
            raise ValueError("Source Version was not captured into this Knowledge Base")

    async def _submit_job(
        self,
        *,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        operation: CompilationOperation,
        source_version_id: uuid.UUID | None,
        note_version_id: uuid.UUID | None,
        idempotency_key: str,
    ) -> SubmittedCompilation:
        existing = await self._repository.find_job(workspace_id, idempotency_key)
        if existing is not None:
            if (
                existing.knowledge_base_id != knowledge_base_id
                or existing.operation != operation
                or existing.source_version_id != source_version_id
                or existing.note_version_id != note_version_id
            ):
                raise CompilationIdempotencyConflict(
                    "idempotency key was already used for a different compilation"
                )
            return SubmittedCompilation(existing, created=False)

        job = CompilationJob(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            operation=operation,
            source_version_id=source_version_id,
            note_version_id=note_version_id,
            idempotency_key=idempotency_key,
            status=CompilationStatus.QUEUED,
        )
        self._session.add(job)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            existing = await self._repository.find_job(workspace_id, idempotency_key)
            if existing is None:
                raise
            if (
                existing.knowledge_base_id != knowledge_base_id
                or existing.operation != operation
                or existing.source_version_id != source_version_id
                or existing.note_version_id != note_version_id
            ):
                raise CompilationIdempotencyConflict(
                    "idempotency key was already used for a different compilation"
                ) from exc
            return SubmittedCompilation(existing, created=False)
        return SubmittedCompilation(job, created=True)

    @staticmethod
    def _record_success(job: CompilationJob, snapshot: CompilationSnapshot) -> None:
        job.status = CompilationStatus.SUCCEEDED
        job.worker_version = snapshot.worker_version
        job.page_count = len(snapshot.pages)
        job.wikilink_count = snapshot.wikilink_count
        job.error_code = None
        job.error_detail = None


def _workspace_key(workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID) -> str:
    return f"{workspace_id}-{knowledge_base_id}"
