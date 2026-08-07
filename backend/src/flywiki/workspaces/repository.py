import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.workspaces.models import KnowledgeBase, Workspace


class WorkspaceResourceNotFound(LookupError):
    """Raised without disclosing whether a resource exists in another Workspace."""


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def workspace_exists(self, workspace_id: uuid.UUID) -> bool:
        result = await self._session.scalar(
            select(Workspace.id).where(Workspace.id == workspace_id)
        )
        return result is not None

    async def list_knowledge_bases(self, workspace_id: uuid.UUID) -> list[KnowledgeBase]:
        result = await self._session.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.workspace_id == workspace_id)
            .order_by(KnowledgeBase.created_at, KnowledgeBase.id)
        )
        return list(result)

    async def get_knowledge_base(
        self, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> KnowledgeBase:
        item = await self._session.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.id == knowledge_base_id,
            )
        )
        if item is None:
            raise WorkspaceResourceNotFound("Knowledge Base not found")
        return item

