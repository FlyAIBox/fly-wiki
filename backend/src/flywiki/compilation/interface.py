from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class OpenKBError(RuntimeError):
    """Base error raised at the OpenKBAdapter seam."""


class OpenKBUnavailable(OpenKBError):
    """The configured Worker cannot currently serve requests."""


class OpenKBWorkspaceNotFound(OpenKBError):
    """The derived OpenKB Workspace does not exist."""


@dataclass(frozen=True)
class CompilationDocument:
    id: str
    title: str
    markdown: str
    content_sha256: str


@dataclass(frozen=True)
class WikiPage:
    path: str
    markdown: str
    wikilinks: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompilationSnapshot:
    worker_version: str
    pages: tuple[WikiPage, ...]

    @property
    def wikilink_count(self) -> int:
        return sum(len(page.wikilinks) for page in self.pages)


class OpenKBAdapter(Protocol):
    """Small Interface hiding Worker transport, storage layout, and OpenKB internals."""

    async def compile(
        self, workspace_key: str, document: CompilationDocument
    ) -> CompilationSnapshot: ...

    async def replace(
        self, workspace_key: str, documents: tuple[CompilationDocument, ...]
    ) -> CompilationSnapshot: ...

    async def snapshot(self, workspace_key: str) -> CompilationSnapshot: ...

    async def delete_workspace(self, workspace_key: str) -> None: ...
