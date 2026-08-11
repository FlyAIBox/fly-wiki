import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.config import Settings
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import (
    AgentReachWebFetcher,
    CaptureFetchError,
    RoutedWebFetcher,
    SafeWebFetcher,
    WebFetcher,
)
from flywiki.sources.notes import EditableNoteService
from flywiki.sources.service import AttachmentInput, CaptureWebSnapshot, SourceRegistry
from flywiki.sources.social import AgentReachSocialFetcher
from flywiki.sources.storage import ObjectStore
from flywiki.sources.wechat import WeChatPublicAccountFetcher


@dataclass(frozen=True)
class SourceAcquisitionResult:
    canonical_url: str
    markdown: str
    backend: str
    source_version_id: uuid.UUID


class SourceAcquisitionService:
    """Deterministically acquire a URL and persist its immutable evidence."""

    def __init__(
        self,
        session: AsyncSession,
        object_store: ObjectStore,
        fetcher: WebFetcher,
        extractor: WebPageExtractor,
    ) -> None:
        self._session = session
        self._object_store = object_store
        self._fetcher = fetcher
        self._extractor = extractor

    async def acquire(
        self,
        *,
        workspace_id: uuid.UUID,
        url: str,
        idempotency_key: str,
    ) -> SourceAcquisitionResult:
        page = await self._fetcher.fetch(url)
        extracted = self._extractor.extract(
            page.content,
            page.final_url,
            content_type=page.content_type,
        )
        if not extracted.markdown.strip():
            raise ValueError("page contains no extractable text")

        attachments: list[AttachmentInput] = []
        attachment_failures = 0
        used_names: set[str] = set()
        for index, attachment_url in enumerate(extracted.attachment_urls, start=1):
            try:
                fetched_attachment = await self._fetcher.fetch_attachment(attachment_url)
            except CaptureFetchError:
                attachment_failures += 1
                continue
            name = fetched_attachment.name
            if name in used_names:
                name = f"{index}-{name}"
            used_names.add(name)
            attachments.append(
                AttachmentInput(
                    name=name,
                    content=fetched_attachment.content,
                    content_type=fetched_attachment.content_type,
                )
            )

        metadata = dict(extracted.metadata)
        if page.metadata is not None:
            metadata.update(page.metadata)
        metadata["capture_backend"] = page.backend
        metadata["attachment_count"] = len(attachments)
        metadata["attachment_failures"] = attachment_failures
        captured = await SourceRegistry(
            self._session, self._object_store
        ).capture_web_snapshot(
            CaptureWebSnapshot(
                workspace_id=workspace_id,
                url=page.final_url,
                idempotency_key=idempotency_key,
                raw_html=page.content,
                markdown=extracted.markdown,
                metadata=metadata,
                locator_map=extracted.locator_map,
                attachments=tuple(attachments),
                raw_content_type=page.content_type,
            )
        )
        markdown = extracted.markdown.decode()
        await EditableNoteService(self._session).create_initial(
            workspace_id,
            captured.version.id,
            markdown,
        )
        return SourceAcquisitionResult(
            canonical_url=captured.source.canonical_uri,
            markdown=markdown,
            backend=page.backend,
            source_version_id=captured.version.id,
        )


def create_capture_fetcher(settings: Settings) -> WebFetcher:
    safe_web = SafeWebFetcher(
        timeout_seconds=settings.capture_timeout_seconds,
        max_bytes=settings.capture_max_bytes,
        max_attachment_bytes=settings.capture_max_attachment_bytes,
        max_redirects=settings.capture_max_redirects,
    )
    agent_reach_web = AgentReachWebFetcher(
        timeout_seconds=settings.capture_timeout_seconds,
        max_bytes=settings.capture_max_bytes,
        max_redirects=settings.capture_max_redirects,
    )
    agent_reach_social = AgentReachSocialFetcher(
        timeout_seconds=settings.capture_timeout_seconds,
        max_bytes=settings.capture_max_bytes,
    )
    wechat_public_account = WeChatPublicAccountFetcher(
        skill_root=settings.resolved_web_content_fetcher_skill_path,
        timeout_seconds=max(settings.capture_timeout_seconds, 60.0),
        max_bytes=settings.capture_max_bytes,
    )

    # Each adapter owns one capability family. The capture pipeline only sees
    # this chain and can therefore survive a skill/runtime replacement.
    return RoutedWebFetcher(
        agent_reach_social,
        RoutedWebFetcher(
            wechat_public_account,
            RoutedWebFetcher(agent_reach_web, safe_web),
        ),
    )
