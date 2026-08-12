from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FLYWIKI_",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./flywiki.db"
    redis_url: str = "redis://localhost:6379/0"
    minio_health_url: str = "http://localhost:9090/minio/health/live"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "flywiki"
    minio_secret_key: str = Field(default="flywiki-minio", repr=False)
    minio_secure: bool = False
    source_bucket: str = "flywiki-sources"
    capture_timeout_seconds: float = 15.0
    capture_max_bytes: int = 10 * 1024 * 1024
    capture_max_attachment_bytes: int = 5 * 1024 * 1024
    capture_max_redirects: int = 5
    agent_model: str | None = None
    model_name: str = Field(default="gpt-5-mini", validation_alias="MODEL_NAME")
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        repr=False,
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias="OPENAI_BASE_URL",
    )
    agent_reach_skill_path: Path = (
        Path(__file__).resolve().parents[3] / "skills" / "agent-reach"
    )
    web_content_fetcher_skill_path: Path = Path("skills/web-content-fetcher")
    langfuse_health_url: str = "http://localhost:3000/api/public/health"
    bootstrap_on_start: bool = True
    default_owner_email: str = "owner@flywiki.local"
    default_workspace_slug: str = "personal"
    default_workspace_name: str = "Personal Workspace"
    default_knowledge_base_slug: str = "inbox"
    default_knowledge_base_name: str = "Inbox"
    healthcheck_worker_enabled: bool = False
    observability_backend: str = "noop"
    langfuse_public_key: str | None = Field(default=None, repr=False)
    langfuse_secret_key: str | None = Field(default=None, repr=False)
    langfuse_host: str = "http://localhost:3000"
    openkb_worker_url: str = "http://localhost:8100"
    openkb_fallback_worker_url: str | None = None
    openkb_timeout_seconds: float = 1800.0

    @property
    def resolved_agent_model(self) -> str:
        project_override = (self.agent_model or "").strip()
        return project_override or self.model_name.strip()

    @property
    def resolved_web_content_fetcher_skill_path(self) -> Path:
        if self.web_content_fetcher_skill_path.is_absolute():
            return self.web_content_fetcher_skill_path
        project_root = Path(__file__).resolve().parents[3]
        return project_root / self.web_content_fetcher_skill_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
