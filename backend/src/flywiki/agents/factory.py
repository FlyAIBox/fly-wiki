from langchain_openai import ChatOpenAI

from flywiki.agents.interface import AgentRuntime
from flywiki.agents.runtime import DeepAgentsRuntime
from flywiki.config import Settings


def create_agent_model(settings: Settings) -> str | ChatOpenAI:
    model = settings.resolved_agent_model
    if ":" in model:
        provider, model_name = model.split(":", 1)
        if provider != "openai":
            return model
    else:
        model_name = model

    api_key = (
        settings.openai_api_key.get_secret_value()
        if settings.openai_api_key is not None
        else None
    )
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
    )


def create_agent_runtime(settings: Settings) -> AgentRuntime:
    return DeepAgentsRuntime(
        model=settings.resolved_agent_model,
        skill_root=settings.agent_reach_skill_path,
        model_factory=lambda: create_agent_model(settings),
    )
