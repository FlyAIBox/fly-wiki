from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.config import Settings
from flywiki.workspaces.bootstrap import bootstrap_default_context
from flywiki.workspaces.models import KnowledgeBase, Owner, Workspace


async def test_default_context_bootstrap_is_idempotent(session: AsyncSession) -> None:
    settings = Settings()

    first = await bootstrap_default_context(session, settings)
    second = await bootstrap_default_context(session, settings)

    assert first.owner.id == second.owner.id
    assert first.workspace.id == second.workspace.id
    assert first.knowledge_base.id == second.knowledge_base.id
    assert await session.scalar(select(func.count()).select_from(Owner)) == 1
    assert await session.scalar(select(func.count()).select_from(Workspace)) == 1
    assert await session.scalar(select(func.count()).select_from(KnowledgeBase)) == 1

