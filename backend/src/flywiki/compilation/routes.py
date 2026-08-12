import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.compilation.interface import OpenKBError, OpenKBWorkspaceNotFound
from flywiki.compilation.models import CompilationJob, CompilationStatus
from flywiki.compilation.repository import CompilationRepository, CompilationResourceNotFound
from flywiki.compilation.schemas import (
    CompilationJobView,
    CompilationSnapshotView,
    SubmitCompilationRequest,
    SubmitRebuildRequest,
    WikiPageView,
)
from flywiki.compilation.service import (
    CompilationIdempotencyConflict,
    KnowledgeCompilation,
)
from flywiki.sources.repository import SourceResourceNotFound
from flywiki.workspaces.repository import WorkspaceResourceNotFound
from flywiki.workspaces.routes import get_session, require_workspace_scope

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["compilation"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/compilations",
    response_model=CompilationJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_compilation(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    payload: SubmitCompilationRequest,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompilationJobView:
    module = KnowledgeCompilation(
        session, request.app.state.object_store, request.app.state.openkb_adapter
    )
    try:
        submitted = await module.submit(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            source_version_id=payload.source_version_id,
            use_editable_note=payload.use_editable_note,
        )
    except (WorkspaceResourceNotFound, SourceResourceNotFound) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compilation input not found") from exc
    except CompilationIdempotencyConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if submitted.created:
        await _dispatch_or_fail(request, session, submitted.job)
    return CompilationJobView.model_validate(submitted.job)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/rebuilds",
    response_model=CompilationJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_rebuild(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    payload: SubmitRebuildRequest,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompilationJobView:
    try:
        submitted = await KnowledgeCompilation(
            session, request.app.state.object_store, request.app.state.openkb_adapter
        ).submit_rebuild(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            idempotency_key=payload.idempotency_key,
        )
    except WorkspaceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge Base not found") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if submitted.created:
        await _dispatch_or_fail(request, session, submitted.job)
    return CompilationJobView.model_validate(submitted.job)


@router.get("/compilations/{job_id}", response_model=CompilationJobView)
async def get_compilation(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompilationJobView:
    try:
        job = await CompilationRepository(session).get_job(workspace_id, job_id)
    except CompilationResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compilation Job not found") from exc
    return CompilationJobView.model_validate(job)


@router.post(
    "/compilations/{job_id}/retry",
    response_model=CompilationJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_compilation(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompilationJobView:
    try:
        job = await CompilationRepository(session).get_job(workspace_id, job_id)
    except CompilationResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compilation Job not found") from exc
    if job.status != CompilationStatus.FAILED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed compilations can be retried")
    if job.attempts >= 3:
        raise HTTPException(status.HTTP_409_CONFLICT, "Compilation retry limit reached")
    job.status = CompilationStatus.QUEUED
    job.error_code = None
    job.error_detail = None
    await session.commit()
    await session.refresh(job)
    await _dispatch_or_fail(request, session, job)
    return CompilationJobView.model_validate(job)


@router.get(
    "/knowledge-bases/{knowledge_base_id}/compiled-wiki",
    response_model=CompilationSnapshotView,
)
async def get_compiled_wiki(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompilationSnapshotView:
    try:
        snapshot = await KnowledgeCompilation(
            session, request.app.state.object_store, request.app.state.openkb_adapter
        ).snapshot(workspace_id, knowledge_base_id)
    except OpenKBWorkspaceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compiled Wiki not found") from exc
    except OpenKBError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OpenKB unavailable") from exc
    return CompilationSnapshotView(
        worker_version=snapshot.worker_version,
        pages=[
            WikiPageView(
                path=page.path,
                markdown=page.markdown,
                wikilinks=list(page.wikilinks),
            )
            for page in snapshot.pages
        ],
    )


async def _dispatch_or_fail(
    request: Request, session: AsyncSession, job: CompilationJob
) -> None:
    try:
        request.app.state.compilation_dispatcher(job.workspace_id, job.id)
    except Exception as exc:
        job.status = CompilationStatus.FAILED
        job.error_code = "dispatch_failed"
        job.error_detail = type(exc).__name__
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Compilation queue is unavailable",
        ) from exc
