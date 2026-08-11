import asyncio
import json
import sys
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from flywiki.sources.fetcher import (
    BlockedContentError,
    FetchedAttachment,
    FetchedWebPage,
    ProviderUnavailableError,
    ResponseTooLargeError,
    UnsafeUrlError,
    is_challenge_content,
)
from flywiki.sources.service import normalize_web_url


class WeChatSkillRunner(Protocol):
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes: ...


class LocalWeChatSkillRunner:
    async def run(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes:
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise ProviderUnavailableError("WeChat collector runtime is unavailable") from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ProviderUnavailableError("WeChat collector timed out") from exc

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[-300:].strip()
            raise ProviderUnavailableError(
                f"WeChat collector exited with {process.returncode}: {detail}"
            )
        if len(stdout) > max_bytes:
            raise ResponseTooLargeError("WeChat collector output exceeds capture_max_bytes")
        return stdout


class WeChatPublicAccountFetcher:
    """Use web-content-fetcher as the dedicated WeChat article Adapter.

    The skill owns Scrapling, browser behavior, WeChat selectors, and Markdown
    conversion. FlyWiki only owns URL routing, process limits, output validation,
    fallback semantics, and the WebFetcher contract.
    """

    def __init__(
        self,
        *,
        skill_root: Path,
        timeout_seconds: float,
        max_bytes: int,
        runner: WeChatSkillRunner | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._script_path = skill_root / "scripts" / "fetch.py"
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._runner = runner or LocalWeChatSkillRunner()
        self._python_executable = python_executable

    async def fetch(self, url: str) -> FetchedWebPage:
        try:
            target_url = normalize_web_url(url)
        except ValueError as exc:
            raise UnsafeUrlError(str(exc)) from exc
        if not _is_wechat_article_url(target_url):
            raise ProviderUnavailableError("URL is not a WeChat public-account article")
        if not self._script_path.is_file():
            raise ProviderUnavailableError("web-content-fetcher skill is not installed")

        # JSON escaping can make stdout larger than the final Markdown. Limit the
        # article by Unicode characters, then independently enforce the byte limit.
        max_chars = max(1, self._max_bytes // 4)
        output = await self._runner.run(
            (
                self._python_executable,
                str(self._script_path),
                target_url,
                str(max_chars),
                "--json",
            ),
            timeout_seconds=self._timeout_seconds,
            max_bytes=self._max_bytes * 2 + 64 * 1024,
        )
        content, metadata = _parse_skill_output(output, max_bytes=self._max_bytes)
        return FetchedWebPage(
            target_url,
            content,
            "text/markdown",
            backend="web-content-fetcher:wechat",
            metadata=metadata,
        )

    async def fetch_attachment(self, _url: str) -> FetchedAttachment:
        raise ProviderUnavailableError("WeChat Adapter does not download attachments")


def _is_wechat_article_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.hostname == "mp.weixin.qq.com" and (
        parts.path == "/s" or parts.path.startswith("/s/")
    )


def _parse_skill_output(
    output: bytes, *, max_bytes: int
) -> tuple[bytes, dict[str, object]]:
    try:
        payload = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderUnavailableError("WeChat collector returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ProviderUnavailableError("WeChat collector returned an invalid payload")
    if payload.get("error"):
        raise ProviderUnavailableError(str(payload["error"]))

    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderUnavailableError("WeChat collector returned empty content")

    raw_metadata = payload.get("metadata")
    metadata: dict[str, object] = {}
    if isinstance(raw_metadata, dict):
        for key in ("title", "author", "published_at"):
            value = raw_metadata.get(key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
    title = metadata.get("title")
    markdown = content.strip()
    if isinstance(title, str) and title.strip() and not markdown.startswith("# "):
        markdown = f"# {title.strip()}\n\n{markdown}"
    encoded = (markdown + "\n").encode()
    if is_challenge_content(encoded):
        raise BlockedContentError("WeChat collector returned a challenge page")
    if len(encoded) > max_bytes:
        raise ResponseTooLargeError("WeChat article exceeds capture_max_bytes")
    return encoded, metadata
