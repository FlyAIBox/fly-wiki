import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.sources.models import CaptureJob, CaptureStatus
from flywiki.sources.notes import (
    EditableNoteService,
    NoteVersionConflict,
)
from flywiki.sources.notes import (
    EditableNoteView as EditableNoteResult,
)
from flywiki.sources.pipeline import CaptureJobService, IdempotencyConflict
from flywiki.sources.repository import SourceRepository, SourceResourceNotFound
from flywiki.sources.schemas import (
    CaptureJobView,
    CaptureRequest,
    EditableNoteView,
    NoteVersionView,
    SaveEditableNoteRequest,
    SourceArtifactView,
    SourceVersionView,
)
from flywiki.workspaces.repository import WorkspaceResourceNotFound
from flywiki.workspaces.routes import get_session, require_workspace_scope

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["sources"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/captures",
    response_model=CaptureJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_capture(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    payload: CaptureRequest,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptureJobView:
    try:
        submitted = await CaptureJobService(session).submit(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            url=payload.url,
            idempotency_key=payload.idempotency_key,
        )
    except WorkspaceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge Base not found") from exc
    except IdempotencyConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    if submitted.created:
        await _dispatch_or_fail(request, session, submitted.job)
    return CaptureJobView.model_validate(submitted.job)


@router.get("/captures/{job_id}", response_model=CaptureJobView)
async def get_capture(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptureJobView:
    try:
        job = await SourceRepository(session).get_capture_job(workspace_id, job_id)
    except SourceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capture Job not found") from exc
    return CaptureJobView.model_validate(job)


@router.post(
    "/captures/{job_id}/retry",
    response_model=CaptureJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_capture(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptureJobView:
    try:
        job = await SourceRepository(session).get_capture_job(workspace_id, job_id)
    except SourceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capture Job not found") from exc
    if job.status != CaptureStatus.FAILED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed captures can be retried")
    if job.attempts >= 3:
        raise HTTPException(status.HTTP_409_CONFLICT, "Capture retry limit reached")
    job.status = CaptureStatus.ACCEPTED
    job.error_code = None
    job.error_detail = None
    await session.commit()
    await _dispatch_or_fail(request, session, job)
    return CaptureJobView.model_validate(job)


@router.get("/source-versions/{source_version_id}", response_model=SourceVersionView)
async def get_source_version(
    workspace_id: uuid.UUID,
    source_version_id: uuid.UUID,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceVersionView:
    repository = SourceRepository(session)
    try:
        version = await repository.get_version(workspace_id, source_version_id)
        source = await repository.get_source(workspace_id, version.source_id)
        artifacts = await repository.list_artifacts(workspace_id, version.id)
    except SourceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source Version not found") from exc
    note = await repository.find_note_by_source_version(workspace_id, version.id)
    return SourceVersionView(
        id=version.id,
        workspace_id=version.workspace_id,
        source_id=version.source_id,
        canonical_uri=source.canonical_uri,
        content_sha256=version.content_sha256,
        captured_at=version.captured_at,
        artifacts=[SourceArtifactView.model_validate(item) for item in artifacts],
        editable_note_id=note.id if note else None,
    )


@router.get("/source-versions/{source_version_id}/artifacts/{artifact_id}")
async def download_source_artifact(
    workspace_id: uuid.UUID,
    source_version_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        artifact = await SourceRepository(session).get_artifact(
            workspace_id, source_version_id, artifact_id
        )
    except SourceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source Artifact not found") from exc
    content = await request.app.state.object_store.get(artifact.object_key)
    return Response(content, media_type=artifact.content_type)


@router.get("/editable-notes/{note_id}", response_model=EditableNoteView)
async def get_editable_note(
    workspace_id: uuid.UUID,
    note_id: uuid.UUID,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EditableNoteView:
    try:
        view = await EditableNoteService(session).get(workspace_id, note_id)
    except SourceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Editable Note not found") from exc
    return _note_view(view)


@router.put("/editable-notes/{note_id}", response_model=EditableNoteView)
async def save_editable_note(
    workspace_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: SaveEditableNoteRequest,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EditableNoteView:
    try:
        view = await EditableNoteService(session).save(
            workspace_id,
            note_id,
            payload.markdown,
            base_version_number=payload.base_version_number,
        )
    except SourceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Editable Note not found") from exc
    except NoteVersionConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _note_view(view)


def _note_view(view: EditableNoteResult) -> EditableNoteView:
    return EditableNoteView(
        id=view.note.id,
        workspace_id=view.note.workspace_id,
        source_version_id=view.note.source_version_id,
        current_version=NoteVersionView.model_validate(view.current_version),
        history=[NoteVersionView.model_validate(item) for item in view.history],
    )


async def _dispatch_or_fail(
    request: Request, session: AsyncSession, job: CaptureJob
) -> None:
    try:
        request.app.state.capture_dispatcher(job.workspace_id, job.id)
    except Exception as exc:
        job.status = CaptureStatus.FAILED
        job.error_code = "dispatch_failed"
        job.error_detail = type(exc).__name__
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Capture queue is unavailable",
        ) from exc
