import asyncio
import json
import re
import shutil
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from flywiki.sources.fetcher import (
    FetchedAttachment,
    FetchedWebPage,
    ProviderUnavailableError,
    ResponseTooLargeError,
    UnsafeUrlError,
)
from flywiki.sources.service import normalize_web_url


class CommandRunner(Protocol):
    def exists(self, command: str) -> bool: ...

    async def run(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes: ...


class LocalCommandRunner:
    def exists(self, command: str) -> bool:
        return shutil.which(command) is not None

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
            raise ProviderUnavailableError(f"command unavailable: {argv[0]}") from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ProviderUnavailableError(f"command timed out: {argv[0]}") from exc

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[-300:]
            raise ProviderUnavailableError(
                f"{argv[0]} exited with {process.returncode}: {detail}"
            )
        if len(stdout) > max_bytes:
            raise ResponseTooLargeError("social capture exceeds capture_max_bytes")
        return stdout


class AgentReachSocialFetcher:
    """Agent Reach adapter for read-only social and community URLs.

    The capture pipeline only sees the WebFetcher interface. Platform command
    names, URL parsing, login-state requirements, and output normalization stay
    inside this adapter so Agent Reach can be upgraded or replaced independently.
    """

    def __init__(
        self,
        *,
        command_runner: CommandRunner | None = None,
        command_exists: Callable[[str], bool] | None = None,
        timeout_seconds: float = 30.0,
        max_bytes: int = 10 * 1024 * 1024,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        runner = command_runner or LocalCommandRunner()
        self._command_runner = runner
        self._command_exists = command_exists or runner.exists
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport

    async def fetch(self, url: str) -> FetchedWebPage:
        try:
            target_url = normalize_web_url(url)
        except ValueError as exc:
            raise UnsafeUrlError(str(exc)) from exc

        parts = urlsplit(target_url)
        host = (parts.hostname or "").lower()
        if host in {"v2ex.com", "www.v2ex.com"}:
            return await self._fetch_v2ex(target_url, parts.path)

        route = self._command_route(target_url, host, parts.path)
        if route is None:
            raise ProviderUnavailableError("no Agent Reach social route")
        platform, argv = route
        if not self._command_exists(argv[0]):
            raise ProviderUnavailableError(f"{argv[0]} is not installed")

        output = await self._command_runner.run(
            argv,
            timeout_seconds=self._timeout_seconds,
            max_bytes=self._max_bytes,
        )
        content = _command_output_to_markdown(platform, output)
        if not content.strip():
            raise ProviderUnavailableError("social provider returned empty content")
        return FetchedWebPage(
            target_url,
            content,
            "text/markdown",
            backend=f"agent-reach:{platform}",
        )

    async def fetch_attachment(self, _url: str) -> FetchedAttachment:
        raise ProviderUnavailableError("social provider does not download attachments")

    def _command_route(
        self,
        target_url: str,
        host: str,
        path: str,
    ) -> tuple[str, tuple[str, ...]] | None:
        if host in {"x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
            if self._command_exists("twitter"):
                return "twitter", ("twitter", "tweet", target_url)
            return None

        if host in {"xiaohongshu.com", "www.xiaohongshu.com"}:
            if "/explore/" not in path:
                return None
            if self._command_exists("opencli"):
                return "xiaohongshu", (
                    "opencli",
                    "xiaohongshu",
                    "note",
                    target_url,
                    "-f",
                    "yaml",
                )
            if self._command_exists("xhs"):
                return "xiaohongshu", ("xhs", "read", target_url)
            return None

        if host in {"bilibili.com", "www.bilibili.com"}:
            match = re.search(r"/video/(BV[0-9A-Za-z]+)", path)
            if match is None:
                return None
            if self._command_exists("bili"):
                return "bilibili", ("bili", "video", match.group(1))
            if self._command_exists("opencli"):
                return "bilibili", ("opencli", "bilibili", "video", match.group(1), "-f", "yaml")
            return None

        if host in {"reddit.com", "www.reddit.com", "old.reddit.com"}:
            match = re.search(r"/comments/([^/]+)", path)
            if match is None:
                return None
            if self._command_exists("opencli"):
                return "reddit", ("opencli", "reddit", "read", match.group(1), "-f", "yaml")
            if self._command_exists("rdt"):
                return "reddit", ("rdt", "read", match.group(1))
            return None

        if host in {"facebook.com", "www.facebook.com"}:
            username = _first_path_segment(path)
            if username is None or username in {"groups", "profile.php"}:
                return None
            if self._command_exists("opencli"):
                return "facebook", ("opencli", "facebook", "profile", username, "-f", "yaml")
            return None

        if host in {"instagram.com", "www.instagram.com"}:
            username = _first_path_segment(path)
            if username is None or username in {"explore", "accounts", "p", "reels"}:
                return None
            if not self._command_exists("opencli"):
                return None
            return "instagram", (
                "opencli",
                "instagram",
                "user",
                username,
                "--limit",
                "12",
                "-f",
                "yaml",
            )

        return None

    async def _fetch_v2ex(self, target_url: str, path: str) -> FetchedWebPage:
        match = re.fullmatch(r"/t/(\d+)", path.rstrip("/"))
        if match is None:
            raise ProviderUnavailableError("no V2EX topic route")
        topic_id = match.group(1)
        timeout = httpx.Timeout(self._timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                topic_response = await client.get(
                    f"https://www.v2ex.com/api/topics/show.json?id={topic_id}",
                    headers={"User-Agent": "agent-reach/1.0"},
                )
                topic_response.raise_for_status()
                replies_response = await client.get(
                    f"https://www.v2ex.com/api/replies/show.json?topic_id={topic_id}&page=1",
                    headers={"User-Agent": "agent-reach/1.0"},
                )
                replies_response.raise_for_status()
                topic = topic_response.json()
                replies = replies_response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError("V2EX API unavailable") from exc

        content = _v2ex_to_markdown(topic, replies)
        if len(content) > self._max_bytes:
            raise ResponseTooLargeError("V2EX capture exceeds capture_max_bytes")
        return FetchedWebPage(
            target_url,
            content,
            "text/markdown",
            backend="agent-reach:v2ex",
        )


def _first_path_segment(path: str) -> str | None:
    segments = [segment for segment in path.split("/") if segment]
    return segments[0] if segments else None


def _command_output_to_markdown(platform: str, output: bytes) -> bytes:
    text = output.decode("utf-8", errors="replace").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return f"# {platform}\n\n```yaml\n{text}\n```\n".encode()
    return (_json_to_markdown(value, heading=f"# {platform}") + "\n").encode()


def _json_to_markdown(value: object, *, heading: str | None = None) -> str:
    if isinstance(value, dict):
        lines = [heading] if heading else []
        title = value.get("title")
        body = value.get("body") or value.get("content")
        if isinstance(title, str) and heading is None:
            lines.extend([f"# {title}", ""])
        if isinstance(body, str):
            lines.extend([body, ""])
        for key, item in value.items():
            if key in {"title", "body", "content"}:
                continue
            if isinstance(item, (dict, list)):
                lines.extend([f"## {key}", _json_to_markdown(item), ""])
            else:
                lines.append(f"- {key}: {item}")
        return "\n".join(lines).strip()
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value)


def _v2ex_to_markdown(topic_payload: object, replies_payload: object) -> bytes:
    topic = topic_payload[0] if isinstance(topic_payload, list) and topic_payload else {}
    if not isinstance(topic, dict):
        topic = {}
    lines = [f"# {topic.get('title', 'V2EX Topic')}", ""]
    if topic.get("content"):
        lines.extend([str(topic["content"]), ""])
    member = topic.get("member")
    if isinstance(member, dict) and member.get("username"):
        lines.extend([f"作者：{member['username']}", ""])
    if isinstance(replies_payload, list) and replies_payload:
        lines.extend(["## Replies", ""])
        for reply in replies_payload:
            if not isinstance(reply, dict):
                continue
            author = reply.get("member", {}).get("username", "unknown")
            lines.extend([f"### {author}", str(reply.get("content", "")), ""])
    return "\n".join(lines).encode()
