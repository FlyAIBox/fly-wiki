import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.sources.models import (
    Source,
    SourceArtifact,
    SourceArtifactRole,
    SourceCaptureReceipt,
    SourceKind,
    SourceVersion,
)
from flywiki.sources.repository import SourceRepository, SourceResourceNotFound
from flywiki.sources.storage import ObjectStore
from flywiki.workspaces.models import Workspace

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class AttachmentInput:
    name: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass(frozen=True)
class CaptureWebSnapshot:
    workspace_id: uuid.UUID
    url: str
    idempotency_key: str
    raw_html: bytes
    markdown: bytes
    metadata: dict[str, object]
    locator_map: dict[str, object]
    attachments: tuple[AttachmentInput, ...] = ()
    raw_content_type: str = "text/html; charset=utf-8"


@dataclass(frozen=True)
class CaptureResult:
    source: Source
    version: SourceVersion
    artifacts: tuple[SourceArtifact, ...]
    created: bool


@dataclass(frozen=True)
class _ArtifactInput:
    role: SourceArtifactRole
    name: str
    content: bytes
    content_type: str


class SourceRegistry:
    def __init__(self, session: AsyncSession, object_store: ObjectStore) -> None:
        self._session = session
        self._repository = SourceRepository(session)
        self._object_store = object_store

    async def capture_web_snapshot(self, command: CaptureWebSnapshot) -> CaptureResult:
        self._validate_command(command)
        try:
            return await self._capture_web_snapshot(command)
        except IntegrityError:
            # A concurrent replay may win any of the unique constraints. Retry
            # once after rollback so the loser returns the committed snapshot.
            await self._session.rollback()
            try:
                return await self._capture_web_snapshot(command)
            except Exception:
                await self._session.rollback()
                raise
        except Exception:
            await self._session.rollback()
            raise

    async def _capture_web_snapshot(self, command: CaptureWebSnapshot) -> CaptureResult:
        existing = await self._repository.find_version_by_idempotency_key(
            command.workspace_id, command.idempotency_key
        )
        if existing is not None:
            return await self._result_for_existing(command.workspace_id, existing)

        if (
            await self._session.scalar(
                select(Workspace.id).where(Workspace.id == command.workspace_id)
            )
            is None
        ):
            raise SourceResourceNotFound("Workspace not found")

        canonical_uri = normalize_web_url(command.url)
        identity_key = hashlib.sha256(f"web:{canonical_uri}".encode()).hexdigest()
        source = await self._repository.find_source(
            command.workspace_id, SourceKind.WEB, identity_key
        )
        if source is None:
            source = Source(
                workspace_id=command.workspace_id,
                kind=SourceKind.WEB,
                identity_key=identity_key,
                canonical_uri=canonical_uri,
            )
            self._session.add(source)
            await self._session.flush()

        content_sha256 = hashlib.sha256(command.raw_html).hexdigest()
        version = await self._repository.find_version_by_content(
            command.workspace_id, source.id, content_sha256
        )
        if version is not None:
            self._session.add(
                SourceCaptureReceipt(
                    workspace_id=command.workspace_id,
                    source_version_id=version.id,
                    idempotency_key=command.idempotency_key,
                )
            )
            await self._session.commit()
            return await self._result_for_existing(command.workspace_id, version)

        version_id = uuid.uuid5(source.id, content_sha256)
        version = SourceVersion(
            id=version_id,
            workspace_id=command.workspace_id,
            source_id=source.id,
            content_sha256=content_sha256,
        )
        self._session.add(version)

        artifacts = tuple(
            self._make_artifact(command.workspace_id, source.id, version_id, item)
            for item in self._artifact_inputs(command)
        )
        self._session.add_all(artifacts)
        self._session.add(
            SourceCaptureReceipt(
                workspace_id=command.workspace_id,
                source_version_id=version_id,
                idempotency_key=command.idempotency_key,
            )
        )

        for artifact, item in zip(artifacts, self._artifact_inputs(command), strict=True):
            await self._object_store.put_if_absent(
                artifact.object_key,
                item.content,
                content_type=item.content_type,
                content_sha256=artifact.content_sha256,
            )

        await self._session.commit()
        return CaptureResult(source, version, artifacts, created=True)

    async def _result_for_existing(
        self, workspace_id: uuid.UUID, version: SourceVersion
    ) -> CaptureResult:
        source = await self._repository.get_source(workspace_id, version.source_id)
        artifacts = await self._repository.list_artifacts(workspace_id, version.id)
        return CaptureResult(source, version, tuple(artifacts), created=False)

    @staticmethod
    def _validate_command(command: CaptureWebSnapshot) -> None:
        if not command.idempotency_key or len(command.idempotency_key) > 255:
            raise ValueError("idempotency_key must contain 1-255 characters")
        if not command.raw_html:
            raise ValueError("raw_html must not be empty")
        names = [attachment.name for attachment in command.attachments]
        if any(not name for name in names):
            raise ValueError("attachment name must not be empty")
        if len(names) != len(set(names)):
            raise ValueError("attachment names must be unique within a Source Version")

    @staticmethod
    def _artifact_inputs(command: CaptureWebSnapshot) -> tuple[_ArtifactInput, ...]:
        metadata = json.dumps(
            command.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        locator_map = json.dumps(
            command.locator_map, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        fixed = (
            _ArtifactInput(
                SourceArtifactRole.RAW_HTML,
                "raw.html",
                command.raw_html,
                command.raw_content_type,
            ),
            _ArtifactInput(
                SourceArtifactRole.MARKDOWN,
                "content.md",
                command.markdown,
                "text/markdown; charset=utf-8",
            ),
            _ArtifactInput(
                SourceArtifactRole.METADATA,
                "metadata.json",
                metadata,
                "application/json",
            ),
            _ArtifactInput(
                SourceArtifactRole.LOCATOR_MAP,
                "locators.json",
                locator_map,
                "application/json",
            ),
        )
        attachments = tuple(
            _ArtifactInput(
                SourceArtifactRole.ATTACHMENT,
                attachment.name,
                attachment.content,
                attachment.content_type,
            )
            for attachment in command.attachments
        )
        return fixed + attachments

    @staticmethod
    def _make_artifact(
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        version_id: uuid.UUID,
        item: _ArtifactInput,
    ) -> SourceArtifact:
        artifact_id = uuid.uuid5(version_id, f"{item.role.value}:{item.name}")
        safe_name = _SAFE_NAME.sub("_", item.name).strip("._") or "artifact"
        object_key = (
            f"{workspace_id}/sources/{source_id}/versions/{version_id}/"
            f"{item.role.value}/{artifact_id}-{safe_name}"
        )
        return SourceArtifact(
            id=artifact_id,
            workspace_id=workspace_id,
            source_version_id=version_id,
            role=item.role,
            name=item.name,
            object_key=object_key,
            content_type=item.content_type,
            content_sha256=hashlib.sha256(item.content).hexdigest(),
            size_bytes=len(item.content),
        )


def normalize_web_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("URL scheme must be http or https")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL userinfo is not allowed")
    if parts.hostname is None:
        raise ValueError("URL host is required")

    host = parts.hostname.encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"
    normalized = SplitResult(
        scheme=scheme,
        netloc=netloc,
        path=parts.path or "/",
        query=parts.query,
        fragment="",
    )
    return urlunsplit(normalized)
