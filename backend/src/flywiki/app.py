import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from flywiki.agents.factory import create_agent_runtime
from flywiki.agents.interface import AgentRuntime
from flywiki.agents.routes import router as agent_router
from flywiki.config import Settings, get_settings
from flywiki.db.database import Database
from flywiki.health.routes import router as health_router
from flywiki.health.service import CeleryProbe, DatabaseProbe, HealthService, HttpProbe, RedisProbe
from flywiki.observability.factory import create_observability
from flywiki.sources.acquisition import create_capture_fetcher
from flywiki.sources.fetcher import WebFetcher
from flywiki.sources.routes import router as source_router
from flywiki.sources.storage import ObjectStore, create_minio_object_store
from flywiki.tasks.celery_app import celery_app
from flywiki.workspaces.bootstrap import bootstrap_default_context
from flywiki.workspaces.routes import router as workspace_router


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    health_service: HealthService | None = None,
    object_store: ObjectStore | None = None,
    capture_dispatcher: Callable[[uuid.UUID, uuid.UUID], object] | None = None,
    agent_runtime: AgentRuntime | None = None,
    source_fetcher_factory: Callable[[Settings], WebFetcher] | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    app_database = database or Database(app_settings.database_url)

    probes = [
        DatabaseProbe(app_database),
        RedisProbe(app_settings.redis_url),
        HttpProbe("object_storage", app_settings.minio_health_url),
    ]
    # Langfuse is optional for core readiness (ADR-0006): when the observability
    # backend is noop / profile is off, do not fail /health/ready on ConnectError.
    if app_settings.observability_backend == "langfuse":
        probes.append(HttpProbe("langfuse", app_settings.langfuse_health_url))
    if app_settings.healthcheck_worker_enabled:
        probes.append(CeleryProbe(celery_app))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if app_settings.bootstrap_on_start:
            async with app_database.sessions() as session:
                await bootstrap_default_context(session, app_settings)
        yield
        await app_database.dispose()

    app = FastAPI(title="FlyWiki", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.database = app_database
    app.state.health_service = health_service or HealthService(probes)
    app.state.observability = create_observability(app_settings)
    app.state.object_store = object_store or create_minio_object_store(app_settings)
    app.state.capture_dispatcher = capture_dispatcher or dispatch_capture_job
    app.state.agent_runtime = agent_runtime or create_agent_runtime(app_settings)
    app.state.source_fetcher_factory = source_fetcher_factory or create_capture_fetcher
    app.include_router(health_router)
    app.include_router(workspace_router)
    app.include_router(source_router)
    app.include_router(agent_router)
    return app


def dispatch_capture_job(workspace_id: uuid.UUID, job_id: uuid.UUID) -> object:
    return celery_app.send_task(
        "flywiki.sources.capture",
        args=[str(workspace_id), str(job_id)],
        task_id=str(job_id),
    )
