from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from collections.abc import Iterable

import httpx

from flywiki.compilation.interface import (
    CompilationDocument,
    CompilationSnapshot,
    OpenKBError,
    OpenKBUnavailable,
    OpenKBWorkspaceNotFound,
    WikiPage,
)

_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


class FakeOpenKBAdapter:
    """Deterministic in-memory Adapter used through the production Interface."""

    def __init__(self, *, delay_seconds: float = 0) -> None:
        self._documents: dict[str, dict[str, CompilationDocument]] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._delay_seconds = delay_seconds
        self._active: defaultdict[str, int] = defaultdict(int)
        self.max_active: defaultdict[str, int] = defaultdict(int)
        self.compile_calls = 0
        self.replace_calls = 0

    async def compile(
        self, workspace_key: str, document: CompilationDocument
    ) -> CompilationSnapshot:
        async with self._locks[workspace_key]:
            await self._enter(workspace_key)
            try:
                documents = self._documents.setdefault(workspace_key, {})
                existing = documents.get(document.id)
                if existing is not None and existing.content_sha256 != document.content_sha256:
                    raise OpenKBError("immutable document id was reused with different content")
                documents[document.id] = document
                self.compile_calls += 1
                return self._make_snapshot(documents.values())
            finally:
                self._leave(workspace_key)

    async def replace(
        self, workspace_key: str, documents: tuple[CompilationDocument, ...]
    ) -> CompilationSnapshot:
        async with self._locks[workspace_key]:
            await self._enter(workspace_key)
            try:
                self._documents[workspace_key] = {document.id: document for document in documents}
                self.replace_calls += 1
                return self._make_snapshot(documents)
            finally:
                self._leave(workspace_key)

    async def snapshot(self, workspace_key: str) -> CompilationSnapshot:
        documents = self._documents.get(workspace_key)
        if documents is None:
            raise OpenKBWorkspaceNotFound("OpenKB Workspace not found")
        return self._make_snapshot(documents.values())

    async def delete_workspace(self, workspace_key: str) -> None:
        async with self._locks[workspace_key]:
            self._documents.pop(workspace_key, None)

    async def _enter(self, workspace_key: str) -> None:
        self._active[workspace_key] += 1
        self.max_active[workspace_key] = max(
            self.max_active[workspace_key], self._active[workspace_key]
        )
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)

    def _leave(self, workspace_key: str) -> None:
        self._active[workspace_key] -= 1

    @staticmethod
    def _make_snapshot(documents: Iterable[CompilationDocument]) -> CompilationSnapshot:
        ordered = sorted(documents, key=lambda item: item.id)
        pages = [
            WikiPage(
                path=f"summaries/{document.id}.md",
                markdown=f"# {document.title}\n\n{document.markdown}\n",
                wikilinks=tuple(_WIKILINK.findall(document.markdown)),
            )
            for document in ordered
        ]
        index_links = tuple(f"summaries/{document.id}" for document in ordered)
        pages.insert(
            0,
            WikiPage(
                path="index.md",
                markdown="# Index\n\n" + "\n".join(f"- [[{link}]]" for link in index_links),
                wikilinks=index_links,
            ),
        )
        return CompilationSnapshot(worker_version="fake-openkb", pages=tuple(pages))


class HttpOpenKBAdapter:
    """HTTP Adapter for one fixed Worker with an optional rollback Worker."""

    def __init__(
        self,
        primary_url: str,
        *,
        fallback_url: str | None = None,
        timeout_seconds: float = 1800,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        urls = [primary_url.rstrip("/")]
        if fallback_url and fallback_url.rstrip("/") not in urls:
            urls.append(fallback_url.rstrip("/"))
        self._urls = tuple(urls)
        self._timeout = timeout_seconds
        self._transport = transport

    async def compile(
        self, workspace_key: str, document: CompilationDocument
    ) -> CompilationSnapshot:
        return await self._request(
            "POST",
            f"/v1/workspaces/{workspace_key}/compile",
            json={"document": _document_payload(document)},
        )

    async def replace(
        self, workspace_key: str, documents: tuple[CompilationDocument, ...]
    ) -> CompilationSnapshot:
        return await self._request(
            "PUT",
            f"/v1/workspaces/{workspace_key}",
            json={"documents": [_document_payload(document) for document in documents]},
        )

    async def snapshot(self, workspace_key: str) -> CompilationSnapshot:
        return await self._request("GET", f"/v1/workspaces/{workspace_key}")

    async def delete_workspace(self, workspace_key: str) -> None:
        await self._request("DELETE", f"/v1/workspaces/{workspace_key}", expect_snapshot=False)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        expect_snapshot: bool = True,
    ) -> CompilationSnapshot:
        last_error: Exception | None = None
        for base_url in self._urls:
            try:
                async with httpx.AsyncClient(
                    base_url=base_url,
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.request(method, path, json=json)
            except httpx.TransportError as exc:
                last_error = exc
                continue

            if response.status_code == 404:
                raise OpenKBWorkspaceNotFound("OpenKB Workspace not found")
            if response.status_code in {502, 503, 504}:
                last_error = OpenKBUnavailable(f"OpenKB Worker returned {response.status_code}")
                continue
            if response.is_error:
                raise OpenKBError(f"OpenKB Worker rejected request ({response.status_code})")
            if not expect_snapshot:
                return CompilationSnapshot(worker_version="unknown", pages=())
            return _snapshot_from_payload(response.json())
        raise OpenKBUnavailable("No configured OpenKB Worker is available") from last_error


def _document_payload(document: CompilationDocument) -> dict[str, str]:
    return {
        "id": document.id,
        "title": document.title,
        "markdown": document.markdown,
        "content_sha256": document.content_sha256,
    }


def _snapshot_from_payload(payload: dict[str, object]) -> CompilationSnapshot:
    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list):
        raise OpenKBError("OpenKB Worker returned an invalid snapshot")
    pages: list[WikiPage] = []
    for raw_page in raw_pages:
        if not isinstance(raw_page, dict):
            raise OpenKBError("OpenKB Worker returned an invalid page")
        pages.append(
            WikiPage(
                path=str(raw_page["path"]),
                markdown=str(raw_page["markdown"]),
                wikilinks=tuple(str(item) for item in raw_page.get("wikilinks", [])),
            )
        )
    return CompilationSnapshot(
        worker_version=str(payload.get("worker_version", "unknown")),
        pages=tuple(pages),
    )
