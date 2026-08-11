import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.agents.gateway import SourceAcquisitionGateway
from flywiki.agents.interface import AgentRunRequest
from flywiki.agents.schemas import (
    AcquiredSourceView,
    AgentRunView,
    StartAgentRunRequest,
)
from flywiki.sources.acquisition import SourceAcquisitionService
from flywiki.sources.extractor import WebPageExtractor
from flywiki.workspaces.repository import WorkspaceRepository, WorkspaceResourceNotFound
from flywiki.workspaces.routes import get_session, require_workspace_scope

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["agents"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/agent-runs",
    response_model=AgentRunView,
)
async def start_agent_run(
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    payload: StartAgentRunRequest,
    request: Request,
    _: Annotated[uuid.UUID, Depends(require_workspace_scope)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRunView:
    try:
        await WorkspaceRepository(session).get_knowledge_base(
            workspace_id,
            knowledge_base_id,
        )
    except WorkspaceResourceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge Base not found") from exc

    run_id = uuid.uuid4()
    acquisition = SourceAcquisitionService(
        session,
        request.app.state.object_store,
        request.app.state.source_fetcher_factory(request.app.state.settings),
        WebPageExtractor(),
    )
    gateway = SourceAcquisitionGateway(
        acquisition,
        workspace_id=workspace_id,
        run_id=run_id,
    )
    result = await request.app.state.agent_runtime.run(
        AgentRunRequest(
            run_id=run_id,
            workspace_id=workspace_id,
            prompt=payload.prompt,
            source_urls=tuple(payload.source_urls),
        ),
        gateway,
    )
    return AgentRunView(
        run_id=run_id,
        answer=result.answer,
        acquired_sources=[
            AcquiredSourceView(
                canonical_url=item.canonical_url,
                backend=item.backend,
                source_version_id=item.source_version_id,
            )
            for item in result.acquired_sources
        ],
    )
