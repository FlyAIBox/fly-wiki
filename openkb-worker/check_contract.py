"""Compatibility smoke test for the OpenKB CLI contract used by the Worker."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import tempfile
from pathlib import Path


def run(*arguments: str, cwd: Path | None = None) -> str:
    environment = os.environ.copy()
    environment["LLM_API_KEY"] = "contract-test-key"
    completed = subprocess.run(
        ["openkb", *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        input="\n",
        cwd=cwd,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout


def main() -> None:
    help_text = run("--help")
    if "--kb-dir" not in help_text or "add" not in help_text:
        raise RuntimeError("OpenKB CLI no longer exposes the required commands")
    with tempfile.TemporaryDirectory(prefix="flywiki-openkb-contract-") as directory:
        knowledge_base = Path(directory) / "kb"
        knowledge_base.mkdir()
        run(
            "init",
            "--model",
            "gpt-5-mini",
            "--language",
            "zh",
            cwd=knowledge_base,
        )
        required = [
            knowledge_base / ".openkb" / "config.yaml",
            knowledge_base / "raw",
            knowledge_base / "wiki" / "index.md",
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise RuntimeError(f"OpenKB init contract changed; missing: {missing}")
    print(f"OpenKB {importlib.metadata.version('openkb')} contract passed")


if __name__ == "__main__":
    main()
