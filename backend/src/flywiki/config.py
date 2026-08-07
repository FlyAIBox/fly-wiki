from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FLYWIKI_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./flywiki.db"
    redis_url: str = "redis://localhost:6379/0"
    minio_health_url: str = "http://localhost:9090/minio/health/live"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

