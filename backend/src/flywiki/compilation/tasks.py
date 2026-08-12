import asyncio
import uuid

from flywiki.compilation.factory import create_openkb_adapter
from flywiki.compilation.service import KnowledgeCompilation
from flywiki.config import get_settings
from flywiki.db.database import Database
from flywiki.sources.storage import create_minio_object_store
from flywiki.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="flywiki.compilation.run",
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=2,
)
def run_compilation(_task, workspace_id: str, job_id: str) -> str:  # type: ignore[no-untyped-def]
    return asyncio.run(_run_compilation(uuid.UUID(workspace_id), uuid.UUID(job_id)))


async def _run_compilation(workspace_id: uuid.UUID, job_id: uuid.UUID) -> str:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.sessions() as session:
            job = await KnowledgeCompilation(
                session,
                create_minio_object_store(settings),
                create_openkb_adapter(settings),
            ).run(workspace_id, job_id)
            return job.status.value
    finally:
        await database.dispose()
