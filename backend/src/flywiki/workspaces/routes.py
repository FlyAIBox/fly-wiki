import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.workspaces.models import KnowledgeBase, Owner, Workspace
from flywiki.workspaces.repository import WorkspaceRepository, WorkspaceResourceNotFound
from flywiki.workspaces.schemas import BootstrapContextView, KnowledgeBaseView

router = APIRouter(prefix="/api", tags=["workspaces"])


async def get_session(request: Request):  # type: ignore[no-untyped-def]
    async with request.app.state.database.sessions() as session:
        yield session


def require_workspace_scope(
    workspace_id: uuid.UUID,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-ID")] = None,
) -> uuid.UUID:
    if x_workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID header is required",
        )
    try:
        header_workspace_id = uuid.UUID(x_workspace_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID must be a UUID",
        ) from exc
    if header_workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace mismatch")
    return workspace_id


@router.get("/context", response_model=BootstrapContextView)
async def get_default_context(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BootstrapContextView:
    row = (
        await session.execute(
            select(Owner, Workspace, KnowledgeBase)
            .join(Workspace, Workspace.owner_id == Owner.id)
            .join(KnowledgeBase, KnowledgeBase.workspace_id == Workspace.id)
            .order_by(Owner.created_at, Workspace.created_at, KnowledgeBase.created_at)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not bootstrapped",
        )
    owner, workspace, knowledge_base = row
    return BootstrapContextView(
        owner_id=owner.id,
        owner_email=owner.email,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_name=workspace.name,
        knowledge_base_id=knowledge_base.id,
        knowledge_base_slug=knowledge_base.slug,
        knowledge_base_name=knowledge_base.name,
    )


@router.get(
    "/workspaces/{workspace_id}/knowledge-bases",
    response_model=list[KnowledgeBaseView],
)
async def list_knowledge_bases(
    workspace_id: uuid.UUID,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[KnowledgeBase]:
    repository = WorkspaceRepository(session)
    if not await repository.workspace_exists(workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return await repository.list_knowledge_bases(workspace_id)


@router.get(
    "/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}",
    response_model=KnowledgeBaseView,
)
async def get_knowledge_base(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeBase:
    try:
        return await WorkspaceRepository(session).get_knowledge_base(
            workspace_id, knowledge_base_id
        )
    except WorkspaceResourceNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge Base not found"
        ) from exc
