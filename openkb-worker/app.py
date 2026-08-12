from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("OPENKB_ROOT", "/data/openkb")).resolve()
MODEL = os.environ.get("OPENKB_MODEL", "gpt-5-mini")
LANGUAGE = os.environ.get("OPENKB_LANGUAGE", "zh")
COMMAND_TIMEOUT = float(os.environ.get("OPENKB_COMMAND_TIMEOUT_SECONDS", "1800"))
OPENKB_VERSION = os.environ.get("OPENKB_VERSION", "0.4.5")
OPENKB_COMMIT = os.environ.get(
    "OPENKB_COMMIT", "ac118407eacd995618256f121c21a2d275672f47"
)
WORKER_VERSION = f"openkb-{OPENKB_VERSION}@{OPENKB_COMMIT[:12]}"

_WORKSPACE_KEY = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_DOCUMENT_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_LOCKS: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)


class DocumentInput(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=2048)
    markdown: str = Field(min_length=1, max_length=20 * 1024 * 1024)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CompileInput(BaseModel):
    document: DocumentInput


class ReplaceInput(BaseModel):
    documents: list[DocumentInput] = Field(min_length=1)


class PageOutput(BaseModel):
    path: str
    markdown: str
    wikilinks: list[str]


class SnapshotOutput(BaseModel):
    worker_version: str
    pages: list[PageOutput]


app = FastAPI(title="FlyWiki OpenKB Worker", version="0.1.0")


@app.get("/health/live")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "worker_version": WORKER_VERSION,
        "openkb_commit": OPENKB_COMMIT,
    }


@app.post("/v1/workspaces/{workspace_key}/compile", response_model=SnapshotOutput)
async def compile_document(workspace_key: str, payload: CompileInput) -> SnapshotOutput:
    _validate_workspace_key(workspace_key)
    _validate_document(payload.document)
    try:
        return await asyncio.to_thread(_compile_sync, workspace_key, payload.document)
    except DocumentConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except WorkerCommandError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@app.put("/v1/workspaces/{workspace_key}", response_model=SnapshotOutput)
async def replace_workspace(workspace_key: str, payload: ReplaceInput) -> SnapshotOutput:
    _validate_workspace_key(workspace_key)
    for document in payload.documents:
        _validate_document(document)
    if len({document.id for document in payload.documents}) != len(payload.documents):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "document ids must be unique")
    try:
        return await asyncio.to_thread(_replace_sync, workspace_key, payload.documents)
    except WorkerCommandError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@app.get("/v1/workspaces/{workspace_key}", response_model=SnapshotOutput)
async def get_workspace(workspace_key: str) -> SnapshotOutput:
    workspace = _workspace_path(workspace_key)
    if not workspace.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OpenKB Workspace not found")
    return await asyncio.to_thread(_snapshot, workspace)


@app.delete("/v1/workspaces/{workspace_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_key: str) -> Response:
    workspace = _workspace_path(workspace_key)
    with _LOCKS[workspace_key]:
        if not workspace.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "OpenKB Workspace not found")
        shutil.rmtree(workspace)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class WorkerCommandError(RuntimeError):
    pass


class DocumentConflict(RuntimeError):
    pass


def _compile_sync(workspace_key: str, document: DocumentInput) -> SnapshotOutput:
    with _LOCKS[workspace_key]:
        workspace = _workspace_path(workspace_key)
        _ensure_workspace(workspace)
        manifest = _read_manifest(workspace)
        known_hash = manifest.get(document.id)
        if known_hash == document.content_sha256:
            return _snapshot(workspace)
        if known_hash is not None:
            raise DocumentConflict(
                "immutable document id was reused; replace the Workspace to apply a new revision"
            )
        _add_document(workspace, document)
        manifest[document.id] = document.content_sha256
        _write_manifest(workspace, manifest)
        return _snapshot(workspace)


def _replace_sync(workspace_key: str, documents: list[DocumentInput]) -> SnapshotOutput:
    with _LOCKS[workspace_key]:
        active = _workspace_path(workspace_key)
        staging_root = ROOT / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = staging_root / f"{workspace_key}-{uuid.uuid4()}"
        backup = staging_root / f"{workspace_key}-rollback-{uuid.uuid4()}"
        try:
            _ensure_workspace(staging)
            manifest: dict[str, str] = {}
            for document in documents:
                _add_document(staging, document)
                manifest[document.id] = document.content_sha256
            _write_manifest(staging, manifest)

            moved_active = False
            if active.exists():
                os.replace(active, backup)
                moved_active = True
            try:
                os.replace(staging, active)
            except Exception:
                if moved_active and backup.exists():
                    os.replace(backup, active)
                raise
            if backup.exists():
                shutil.rmtree(backup)
            return _snapshot(active)
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def _ensure_workspace(workspace: Path) -> None:
    if (workspace / ".openkb").exists():
        return
    workspace.mkdir(parents=True, exist_ok=True)
    _run_openkb(
        workspace,
        "init",
        "--model",
        MODEL,
        "--language",
        LANGUAGE,
        input_text="\n",
    )


def _add_document(workspace: Path, document: DocumentInput) -> None:
    incoming = workspace / ".flywiki" / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    path = incoming / f"{document.id}.md"
    path.write_text(document.markdown, encoding="utf-8")
    try:
        _run_openkb(workspace, "add", str(path))
    finally:
        path.unlink(missing_ok=True)


def _run_openkb(workspace: Path, *arguments: str, input_text: str | None = None) -> None:
    command = ["openkb", *arguments]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT,
        check=False,
        env=os.environ.copy(),
        input=input_text,
        cwd=workspace,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "OpenKB command failed").strip()
        raise WorkerCommandError(detail[-1000:])


def _snapshot(workspace: Path) -> SnapshotOutput:
    wiki = workspace / "wiki"
    pages: list[PageOutput] = []
    if wiki.exists():
        for path in sorted(wiki.rglob("*.md")):
            markdown = path.read_text(encoding="utf-8")
            pages.append(
                PageOutput(
                    path=path.relative_to(wiki).as_posix(),
                    markdown=markdown,
                    wikilinks=_WIKILINK.findall(markdown),
                )
            )
    return SnapshotOutput(worker_version=WORKER_VERSION, pages=pages)


def _manifest_path(workspace: Path) -> Path:
    return workspace / ".flywiki" / "manifest.json"


def _read_manifest(workspace: Path) -> dict[str, str]:
    path = _manifest_path(workspace)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkerCommandError("invalid FlyWiki compilation manifest")
    return {str(key): str(value) for key, value in payload.items()}


def _write_manifest(workspace: Path, manifest: dict[str, str]) -> None:
    path = _manifest_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="manifest-", suffix=".json", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _workspace_path(workspace_key: str) -> Path:
    _validate_workspace_key(workspace_key)
    path = (ROOT / "workspaces" / workspace_key).resolve()
    expected_parent = (ROOT / "workspaces").resolve()
    if path.parent != expected_parent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid Workspace key")
    return path


def _validate_workspace_key(workspace_key: str) -> None:
    if not _WORKSPACE_KEY.fullmatch(workspace_key):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid Workspace key")


def _validate_document(document: DocumentInput) -> None:
    if not _DOCUMENT_ID.fullmatch(document.id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid document id")
    actual = hashlib.sha256(document.markdown.encode()).hexdigest()
    if actual != document.content_sha256:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "content hash mismatch")
