import asyncio
import ipaddress
import posixpath
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from flywiki.sources.service import normalize_web_url

Resolver = Callable[[str, int], Awaitable[list[str]]]

_READER_UPSTREAM_ERROR = re.compile(
    rb"(?im)^Warning:\s*Target URL returned error\s+([45]\d\d)\b"
)
_CHALLENGE_MARKER_GROUPS = (
    (b"warning: this page maybe requiring captcha",),
    ("环境异常".encode(), "完成验证后即可继续访问".encode()),
    (b"you've been blocked by network security", b"log in to your reddit account"),
)


class CaptureFetchError(RuntimeError):
    code = "fetch_failed"


class UnsafeUrlError(CaptureFetchError):
    code = "unsafe_url"


class UnsupportedMediaTypeError(CaptureFetchError):
    code = "unsupported_media_type"


class ResponseTooLargeError(CaptureFetchError):
    code = "response_too_large"


class ProviderUnavailableError(CaptureFetchError):
    """The selected external capability cannot handle this capture right now."""

    code = "provider_unavailable"


class BlockedContentError(ProviderUnavailableError):
    """The provider returned a login wall, CAPTCHA, or network challenge."""

    code = "blocked_content"


@dataclass(frozen=True)
class FetchedWebPage:
    final_url: str
    content: bytes
    content_type: str
    backend: str = "unknown"
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class FetchedAttachment:
    final_url: str
    content: bytes
    content_type: str
    name: str


class WebFetcher(Protocol):
    async def fetch(self, url: str) -> FetchedWebPage: ...

    async def fetch_attachment(self, url: str) -> FetchedAttachment: ...


class RoutedWebFetcher:
    """Prefer an external capability and use a local provider as its fallback."""

    def __init__(self, primary: WebFetcher, fallback: WebFetcher) -> None:
        self._primary = primary
        self._fallback = fallback

    async def fetch(self, url: str) -> FetchedWebPage:
        try:
            return await self._primary.fetch(url)
        except ProviderUnavailableError:
            return await self._fallback.fetch(url)

    async def fetch_attachment(self, url: str) -> FetchedAttachment:
        # Agent Reach's reader returns normalized page content. Binary assets are
        # deliberately downloaded by the fallback provider, which has the same
        # SSRF and size guards as ordinary web capture.
        return await self._fallback.fetch_attachment(url)


async def resolve_host(host: str, port: int) -> list[str]:
    def resolve() -> list[str]:
        return list(
            {
                item[4][0]
                for item in socket.getaddrinfo(
                    host,
                    port,
                    type=socket.SOCK_STREAM,
                )
            }
        )

    return await asyncio.to_thread(resolve)


class AgentReachWebFetcher:
    """Read public web URLs through Agent Reach's Jina Reader route.

    Agent Reach is a skill-level routing contract rather than a Python library.
    Its zero-config web route is the Jina Reader endpoint, so this adapter keeps
    that route behind FlyWiki's WebFetcher seam. Platform-specific CLIs can be
    added as another primary provider without changing the capture pipeline.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_bytes: int,
        max_redirects: int,
        resolver: Resolver = resolve_host,
        transport: httpx.AsyncBaseTransport | None = None,
        reader_base_url: str = "https://r.jina.ai",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects
        self._resolver = resolver
        self._transport = transport
        self._reader_base_url = reader_base_url.rstrip("/")

    async def fetch(self, url: str) -> FetchedWebPage:
        try:
            target_url = normalize_web_url(url)
        except ValueError as exc:
            raise UnsafeUrlError(str(exc)) from exc
        await self._assert_public_url(target_url)
        reader_url = f"{self._reader_base_url}/{target_url}"
        timeout = httpx.Timeout(self._timeout_seconds)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                max_redirects=self._max_redirects,
                transport=self._transport,
            ) as client:
                async with client.stream(
                    "GET",
                    reader_url,
                    headers={
                        "Accept": "text/markdown,text/plain",
                        "User-Agent": "FlyWikiCapture/0.1",
                    },
                ) as response:
                    response.raise_for_status()
                    content_type = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if not content_type.startswith("text/"):
                        raise ProviderUnavailableError(
                            f"Agent Reach returned unsupported Content-Type: "
                            f"{content_type or 'missing'}"
                        )
                    declared_size = response.headers.get("content-length")
                    if declared_size is not None and int(declared_size) > self._max_bytes:
                        raise ResponseTooLargeError("response exceeds capture_max_bytes")

                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > self._max_bytes:
                            raise ResponseTooLargeError("response exceeds capture_max_bytes")
                        chunks.append(chunk)
        except ResponseTooLargeError:
            raise
        except UnsafeUrlError:
            raise
        except ProviderUnavailableError:
            raise
        except (httpx.HTTPError, UnicodeError) as exc:
            raise ProviderUnavailableError(type(exc).__name__) from exc

        content = b"".join(chunks)
        if not content.strip():
            raise ProviderUnavailableError("Agent Reach returned an empty page")
        upstream_error = _READER_UPSTREAM_ERROR.search(content)
        if upstream_error is not None:
            status_code = upstream_error.group(1).decode()
            raise BlockedContentError(f"Agent Reach upstream returned {status_code}")
        if is_challenge_content(content):
            raise BlockedContentError("Agent Reach returned a challenge page")
        return FetchedWebPage(target_url, content, "text/markdown", backend="agent-reach")

    async def fetch_attachment(self, _url: str) -> FetchedAttachment:
        raise ProviderUnavailableError("Agent Reach web reader does not download attachments")

    async def _assert_public_url(self, url: str) -> None:
        parts = urlsplit(url)
        assert parts.hostname is not None
        port = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            addresses = await self._resolver(parts.hostname, port)
        except OSError as exc:
            raise ProviderUnavailableError("DNS resolution failed") from exc
        if not addresses:
            raise ProviderUnavailableError("DNS returned no addresses")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise UnsafeUrlError("DNS returned an invalid address") from exc
            if not ip.is_global:
                raise UnsafeUrlError("URL resolves to a non-public address")


class SafeWebFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_bytes: int,
        max_redirects: int,
        max_attachment_bytes: int | None = None,
        resolver: Resolver = resolve_host,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._max_attachment_bytes = max_attachment_bytes or max_bytes
        self._max_redirects = max_redirects
        self._resolver = resolver
        self._transport = transport

    async def fetch(self, url: str) -> FetchedWebPage:
        try:
            final_url, content, content_type = await self._fetch(
                url,
                max_bytes=self._max_bytes,
                accepted_content_type=lambda value: value
                in {"text/html", "application/xhtml+xml"},
            )
        except httpx.HTTPError as exc:
            raise CaptureFetchError(type(exc).__name__) from exc
        if is_challenge_content(content):
            raise BlockedContentError("web origin returned a challenge page")
        return FetchedWebPage(final_url, content, content_type, backend="safe-web")

    async def fetch_attachment(self, url: str) -> FetchedAttachment:
        try:
            final_url, content, content_type = await self._fetch(
                url,
                max_bytes=self._max_attachment_bytes,
                accepted_content_type=lambda value: value.startswith("image/")
                or value == "application/pdf",
            )
        except httpx.HTTPError as exc:
            raise CaptureFetchError(type(exc).__name__) from exc
        name = unquote(posixpath.basename(urlsplit(final_url).path)) or "attachment"
        return FetchedAttachment(final_url, content, content_type, name)

    async def _fetch(
        self,
        url: str,
        *,
        max_bytes: int,
        accepted_content_type: Callable[[str], bool],
    ) -> tuple[str, bytes, str]:
        try:
            current_url = normalize_web_url(url)
        except ValueError as exc:
            raise UnsafeUrlError(str(exc)) from exc
        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            for redirect_count in range(self._max_redirects + 1):
                await self._assert_public_url(current_url)
                async with client.stream(
                    "GET",
                    current_url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "User-Agent": "FlyWikiCapture/0.1",
                    },
                ) as response:
                    if response.is_redirect:
                        if redirect_count == self._max_redirects:
                            raise CaptureFetchError("too many redirects")
                        location = response.headers.get("location")
                        if not location:
                            raise CaptureFetchError("redirect has no Location")
                        current_url = normalize_web_url(urljoin(current_url, location))
                        continue

                    response.raise_for_status()
                    content_type = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    if not accepted_content_type(content_type):
                        raise UnsupportedMediaTypeError(
                            f"unsupported Content-Type: {content_type or 'missing'}"
                        )
                    declared_size = response.headers.get("content-length")
                    if declared_size is not None and int(declared_size) > max_bytes:
                        raise ResponseTooLargeError("response exceeds capture_max_bytes")

                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ResponseTooLargeError("response exceeds capture_max_bytes")
                        chunks.append(chunk)
                    return current_url, b"".join(chunks), content_type
        raise CaptureFetchError("redirect handling did not terminate")

    async def _assert_public_url(self, url: str) -> None:
        parts = urlsplit(url)
        assert parts.hostname is not None
        port = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            addresses = await self._resolver(parts.hostname, port)
        except OSError as exc:
            raise CaptureFetchError("DNS resolution failed") from exc
        if not addresses:
            raise CaptureFetchError("DNS returned no addresses")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise UnsafeUrlError("DNS returned an invalid address") from exc
            if not ip.is_global:
                raise UnsafeUrlError("URL resolves to a non-public address")


def is_challenge_content(content: bytes) -> bool:
    normalized = content.lower()
    return any(
        all(marker in normalized for marker in marker_group)
        for marker_group in _CHALLENGE_MARKER_GROUPS
    )
