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
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "flywiki"
    minio_secret_key: str = Field(default="flywiki-minio", repr=False)
    minio_secure: bool = False
    source_bucket: str = "flywiki-sources"
    capture_timeout_seconds: float = 15.0
    capture_max_bytes: int = 10 * 1024 * 1024
    capture_max_attachment_bytes: int = 5 * 1024 * 1024
    capture_max_redirects: int = 5
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

