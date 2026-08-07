import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.workspaces.models import KnowledgeBase, Owner, Workspace
from flywiki.workspaces.repository import WorkspaceRepository, WorkspaceResourceNotFound


async def test_repository_never_returns_a_resource_from_another_workspace(
    session: AsyncSession,
) -> None:
    owner = Owner(email="owner@example.com")
    session.add(owner)
    await session.flush()
    first = Workspace(owner_id=owner.id, slug="first", name="First")
    second = Workspace(owner_id=owner.id, slug="second", name="Second")
    session.add_all([first, second])
    await session.flush()
    knowledge_base = KnowledgeBase(workspace_id=first.id, slug="inbox", name="Inbox")
    session.add(knowledge_base)
    await session.commit()

    repository = WorkspaceRepository(session)

    with pytest.raises(WorkspaceResourceNotFound):
        await repository.get_knowledge_base(second.id, knowledge_base.id)
    with pytest.raises(WorkspaceResourceNotFound):
        await repository.get_knowledge_base(uuid.uuid4(), knowledge_base.id)
    assert await repository.get_knowledge_base(first.id, knowledge_base.id) == knowledge_base

