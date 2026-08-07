from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.config import Settings
from flywiki.workspaces.models import KnowledgeBase, Owner, Workspace


@dataclass(frozen=True)
class BootstrapContext:
    owner: Owner
    workspace: Workspace
    knowledge_base: KnowledgeBase


async def bootstrap_default_context(
    session: AsyncSession, settings: Settings
) -> BootstrapContext:
    owner = await session.scalar(select(Owner).where(Owner.email == settings.default_owner_email))
    if owner is None:
        owner = Owner(email=settings.default_owner_email)
        session.add(owner)
        await session.flush()

    workspace = await session.scalar(
        select(Workspace).where(
            Workspace.owner_id == owner.id,
            Workspace.slug == settings.default_workspace_slug,
        )
    )
    if workspace is None:
        workspace = Workspace(
            owner_id=owner.id,
            slug=settings.default_workspace_slug,
            name=settings.default_workspace_name,
        )
        session.add(workspace)
        await session.flush()

    knowledge_base = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.workspace_id == workspace.id,
            KnowledgeBase.slug == settings.default_knowledge_base_slug,
        )
    )
    if knowledge_base is None:
        knowledge_base = KnowledgeBase(
            workspace_id=workspace.id,
            slug=settings.default_knowledge_base_slug,
            name=settings.default_knowledge_base_name,
        )
        session.add(knowledge_base)
        await session.flush()

    await session.commit()
    return BootstrapContext(owner=owner, workspace=workspace, knowledge_base=knowledge_base)

