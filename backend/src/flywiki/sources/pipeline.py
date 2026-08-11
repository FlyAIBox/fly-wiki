import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.sources.acquisition import SourceAcquisitionService
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import CaptureFetchError, WebFetcher
from flywiki.sources.models import CaptureJob, CaptureStatus
from flywiki.sources.repository import SourceRepository
from flywiki.sources.service import normalize_web_url
from flywiki.sources.storage import ObjectStore
from flywiki.workspaces.repository import WorkspaceRepository


class IdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class SubmittedCapture:
    job: CaptureJob
    created: bool


class CaptureJobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = SourceRepository(session)

    async def submit(
        self,
        *,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        url: str,
        idempotency_key: str,
    ) -> SubmittedCapture:
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValueError("idempotency_key must contain 1-255 characters")
        canonical_url = normalize_web_url(url)
        await WorkspaceRepository(self._session).get_knowledge_base(workspace_id, knowledge_base_id)
        existing = await self._repository.find_capture_job(workspace_id, idempotency_key)
        if existing is not None:
            if (
                existing.knowledge_base_id != knowledge_base_id
                or existing.canonical_url != canonical_url
            ):
                raise IdempotencyConflict(
                    "idempotency key was already used for a different capture"
                )
            return SubmittedCapture(existing, created=False)

        job = CaptureJob(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            canonical_url=canonical_url,
            idempotency_key=idempotency_key,
            status=CaptureStatus.ACCEPTED,
        )
        self._session.add(job)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            existing = await self._repository.find_capture_job(workspace_id, idempotency_key)
            if existing is None:
                raise
            if (
                existing.knowledge_base_id != knowledge_base_id
                or existing.canonical_url != canonical_url
            ):
                raise IdempotencyConflict(
                    "idempotency key was already used for a different capture"
                ) from exc
            return SubmittedCapture(existing, created=False)
        return SubmittedCapture(job, created=True)


class CapturePipeline:
    def __init__(
        self,
        session: AsyncSession,
        object_store: ObjectStore,
        fetcher: WebFetcher,
        extractor: WebPageExtractor,
    ) -> None:
        self._session = session
        self._repository = SourceRepository(session)
        self._acquisition = SourceAcquisitionService(
            session,
            object_store,
            fetcher,
            extractor,
        )

    async def run(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> CaptureJob:
        job = await self._repository.get_capture_job(workspace_id, job_id)
        if job.status == CaptureStatus.READY_FOR_COMPILE:
            return job

        job.status = CaptureStatus.FETCHING
        job.attempts += 1
        job.error_code = None
        job.error_detail = None
        await self._session.commit()

        try:
            acquired = await self._acquisition.acquire(
                workspace_id=workspace_id,
                url=job.canonical_url,
                idempotency_key=job.idempotency_key,
            )
            job = await self._repository.get_capture_job(workspace_id, job_id)
            job.status = CaptureStatus.READY_FOR_COMPILE
            job.source_version_id = acquired.source_version_id
            await self._session.commit()
            return job
        except Exception as exc:
            await self._session.rollback()
            job = await self._repository.get_capture_job(workspace_id, job_id)
            job.status = CaptureStatus.FAILED
            job.error_code = exc.code if isinstance(exc, CaptureFetchError) else "processing_failed"
            job.error_detail = type(exc).__name__
            await self._session.commit()
            return job
