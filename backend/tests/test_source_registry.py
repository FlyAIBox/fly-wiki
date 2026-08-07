import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.sources.models import (
    Source,
    SourceArtifact,
    SourceArtifactRole,
    SourceCaptureReceipt,
    SourceVersion,
)
from flywiki.sources.repository import SourceRepository, SourceResourceNotFound
from flywiki.sources.service import (
    AttachmentInput,
    CaptureWebSnapshot,
    SourceRegistry,
)
from flywiki.sources.storage import InMemoryObjectStore
from flywiki.workspaces.models import Owner, Workspace


async def create_workspaces(session: AsyncSession) -> tuple[Workspace, Workspace]:
    owner = Owner(email="source-owner@example.com")
    session.add(owner)
    await session.flush()
    first = Workspace(owner_id=owner.id, slug="first", name="First")
    second = Workspace(owner_id=owner.id, slug="second", name="Second")
    session.add_all([first, second])
    await session.commit()
    return first, second


def snapshot(
    workspace_id: uuid.UUID,
    *,
    idempotency_key: str = "web:request-1",
    raw_html: bytes = b"<html><body>Hello</body></html>",
) -> CaptureWebSnapshot:
    return CaptureWebSnapshot(
        workspace_id=workspace_id,
        url="HTTPS://Example.COM:443/article#section",
        idempotency_key=idempotency_key,
        raw_html=raw_html,
        markdown=b"# Hello\n",
        metadata={"title": "Hello"},
        locator_map={"blocks": [{"markdown": [0, 7], "html": "body"}]},
        attachments=(
            AttachmentInput(
                name="diagram.png",
                content=b"PNG",
                content_type="image/png",
            ),
        ),
    )


async def test_capture_persists_an_immutable_snapshot_and_all_artifacts(
    session: AsyncSession,
) -> None:
    workspace, _ = await create_workspaces(session)
    object_store = InMemoryObjectStore()
    registry = SourceRegistry(session, object_store)

    result = await registry.capture_web_snapshot(snapshot(workspace.id))

    assert result.created is True
    assert result.source.canonical_uri == "https://example.com/article"
    assert result.version.workspace_id == workspace.id
    assert result.version.content_sha256
    assert {artifact.role for artifact in result.artifacts} == {
        SourceArtifactRole.RAW_HTML,
        SourceArtifactRole.MARKDOWN,
        SourceArtifactRole.METADATA,
        SourceArtifactRole.LOCATOR_MAP,
        SourceArtifactRole.ATTACHMENT,
    }
    assert all(artifact.object_key in object_store.objects for artifact in result.artifacts)
    assert all(
        artifact.object_key.startswith(f"{workspace.id}/sources/{result.source.id}/versions/")
        for artifact in result.artifacts
    )


async def test_message_replay_and_same_content_do_not_duplicate_versions(
    session: AsyncSession,
) -> None:
    workspace, _ = await create_workspaces(session)
    registry = SourceRegistry(session, InMemoryObjectStore())

    first = await registry.capture_web_snapshot(snapshot(workspace.id))
    replay = await registry.capture_web_snapshot(snapshot(workspace.id))
    same_content_new_message = await registry.capture_web_snapshot(
        snapshot(workspace.id, idempotency_key="weixin:message-2")
    )

    assert replay.created is False
    assert replay.version.id == first.version.id
    assert same_content_new_message.created is False
    assert same_content_new_message.version.id == first.version.id
    assert await session.scalar(select(func.count()).select_from(Source)) == 1
    assert await session.scalar(select(func.count()).select_from(SourceVersion)) == 1
    assert await session.scalar(select(func.count()).select_from(SourceCaptureReceipt)) == 2


async def test_changed_web_content_creates_a_new_version_but_replay_stays_stable(
    session: AsyncSession,
) -> None:
    workspace, _ = await create_workspaces(session)
    registry = SourceRegistry(session, InMemoryObjectStore())

    first = await registry.capture_web_snapshot(snapshot(workspace.id))
    changed = await registry.capture_web_snapshot(
        snapshot(
            workspace.id,
            idempotency_key="web:request-2",
            raw_html=b"<html><body>Changed</body></html>",
        )
    )
    replay_of_first_message = await registry.capture_web_snapshot(snapshot(workspace.id))

    assert changed.created is True
    assert changed.source.id == first.source.id
    assert changed.version.id != first.version.id
    assert replay_of_first_message.version.id == first.version.id
    assert await session.scalar(select(func.count()).select_from(SourceVersion)) == 2


async def test_repository_never_discloses_sources_from_another_workspace(
    session: AsyncSession,
) -> None:
    first_workspace, second_workspace = await create_workspaces(session)
    captured = await SourceRegistry(session, InMemoryObjectStore()).capture_web_snapshot(
        snapshot(first_workspace.id)
    )
    repository = SourceRepository(session)

    with pytest.raises(SourceResourceNotFound):
        await repository.get_source(second_workspace.id, captured.source.id)
    with pytest.raises(SourceResourceNotFound):
        await repository.get_version(second_workspace.id, captured.version.id)
    with pytest.raises(SourceResourceNotFound):
        await repository.list_artifacts(second_workspace.id, captured.version.id)

    assert await repository.get_source(first_workspace.id, captured.source.id) == captured.source
    assert await repository.get_version(first_workspace.id, captured.version.id) == captured.version


async def test_source_version_and_artifact_rows_cannot_be_updated(
    session: AsyncSession,
) -> None:
    workspace, _ = await create_workspaces(session)
    captured = await SourceRegistry(session, InMemoryObjectStore()).capture_web_snapshot(
        snapshot(workspace.id)
    )
    version_id = captured.version.id

    captured.version.content_sha256 = "0" * 64
    with pytest.raises(ValueError, match="immutable"):
        await session.flush()
    await session.rollback()

    artifact = await session.scalar(
        select(SourceArtifact).where(SourceArtifact.source_version_id == version_id)
    )
    assert artifact is not None
    artifact.object_key = "changed"
    with pytest.raises(ValueError, match="immutable"):
        await session.flush()
