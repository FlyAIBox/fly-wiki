from collections.abc import Callable
from pathlib import Path
from typing import Any

from flywiki.agents.interface import (
    AgentRunRequest,
    AgentRunResult,
    SourceAcquisitionCapability,
)

_SYSTEM_PROMPT = """You are FlyWiki's restricted research agent.

Use the agent-reach skill for internet source handling. The only allowed network
capability is acquire_source. Do not invent source contents and do not claim a
source was read unless acquire_source returned non-empty evidence. You cannot
write FlyWiki data directly; the capability gateway creates immutable Source
Versions before returning evidence to you.
"""

_SKILL_TEXT_SUFFIXES = {".json", ".md", ".toml", ".txt", ".yaml", ".yml"}


class DeepAgentsRuntime:
    """DeepAgents Adapter behind FlyWiki's AgentRuntime Interface."""

    def __init__(
        self,
        *,
        model: str,
        skill_root: Path,
        model_factory: Callable[[], Any] | None = None,
        agent_factory: Callable[..., Any] | None = None,
        file_data_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if agent_factory is None or file_data_factory is None:
            from deepagents import create_deep_agent
            from deepagents.backends.utils import create_file_data

            agent_factory = agent_factory or create_deep_agent
            file_data_factory = file_data_factory or create_file_data

        self._model = model
        self._model_factory = model_factory
        self._skill_root = skill_root.resolve()
        self._agent_factory = agent_factory
        self._file_data_factory = file_data_factory
        self._skill_files = self._load_skill_files()

    async def run(
        self,
        request: AgentRunRequest,
        capability: SourceAcquisitionCapability,
    ) -> AgentRunResult:
        async def acquire_source(url: str) -> str:
            """Acquire one URL through FlyWiki's authorized Agent Reach gateway."""

            acquired = await capability.acquire_source(url)
            return (
                f"Source URL: {acquired.canonical_url}\n"
                f"Capture backend: {acquired.backend}\n\n"
                f"{acquired.markdown}"
            )

        graph = self._agent_factory(
            model=self._model_factory() if self._model_factory else self._model,
            tools=[acquire_source],
            skills=["/skills/"],
            system_prompt=_SYSTEM_PROMPT,
        )
        prompt = request.prompt
        if request.source_urls:
            sources = "\n".join(f"- {url}" for url in request.source_urls)
            prompt = f"{prompt}\n\nExplicitly supplied source URLs:\n{sources}"
        result = await graph.ainvoke(
            {
                "messages": [{"role": "user", "content": prompt}],
                "files": self._skill_files,
            },
            config={"configurable": {"thread_id": str(request.run_id)}},
        )
        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("DeepAgents returned no messages")
        content = getattr(messages[-1], "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("DeepAgents returned no textual answer")
        return AgentRunResult(content.strip(), capability.acquired_sources)

    def _load_skill_files(self) -> dict[str, Any]:
        skill_file = self._skill_root / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"Agent Reach skill not found: {skill_file}")

        files: dict[str, Any] = {}
        for candidate in sorted(self._skill_root.rglob("*")):
            relative_path = candidate.relative_to(self._skill_root)
            if (
                not candidate.is_file()
                or any(part.startswith(".") for part in relative_path.parts)
                or candidate.suffix.lower() not in _SKILL_TEXT_SUFFIXES
            ):
                continue
            resolved = candidate.resolve()
            if not resolved.is_relative_to(self._skill_root):
                raise ValueError(f"Skill asset escapes skill root: {candidate}")
            relative = relative_path.as_posix()
            virtual_path = f"/skills/agent-reach/{relative}"
            files[virtual_path] = self._file_data_factory(
                candidate.read_text(encoding="utf-8")
            )
        return files
