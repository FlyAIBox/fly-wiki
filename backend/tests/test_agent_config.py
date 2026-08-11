from pathlib import Path

from langchain_openai import ChatOpenAI

from flywiki.agents.factory import create_agent_model
from flywiki.config import Settings


def test_openai_compatible_environment_configures_agent_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_NAME", "custom-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.delenv("FLYWIKI_AGENT_MODEL", raising=False)
    for variable in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy"):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)
    model = create_agent_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "custom-model"
    assert model.openai_api_base == "https://llm.example.com/v1"
    assert model.openai_api_key is not None
    assert model.openai_api_key.get_secret_value() == "test-key"


def test_flywiki_agent_model_remains_a_compatible_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MODEL_NAME", "new-name")
    monkeypatch.setenv("FLYWIKI_AGENT_MODEL", "openai:legacy-override")

    settings = Settings(_env_file=None)

    assert settings.resolved_agent_model == "openai:legacy-override"


def test_web_content_fetcher_uses_a_project_relative_config_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("FLYWIKI_WEB_CONTENT_FETCHER_SKILL_PATH", raising=False)
    settings = Settings(_env_file=None)

    assert settings.web_content_fetcher_skill_path == Path(
        "skills/web-content-fetcher"
    )
    assert settings.resolved_web_content_fetcher_skill_path == (
        Path(__file__).resolve().parents[2] / "skills" / "web-content-fetcher"
    )
