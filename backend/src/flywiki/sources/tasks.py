import asyncio
import uuid

from flywiki.config import get_settings
from flywiki.db.database import Database
from flywiki.sources.extractor import WebPageExtractor
from flywiki.sources.fetcher import SafeWebFetcher
from flywiki.sources.pipeline import CapturePipeline
from flywiki.sources.storage import create_minio_object_store
from flywiki.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="flywiki.sources.capture",
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def capture_web_page(_task, workspace_id: str, capture_job_id: str) -> str:  # type: ignore[no-untyped-def]
    return asyncio.run(
        _capture_web_page(
            uuid.UUID(workspace_id),
            uuid.UUID(capture_job_id),
        )
    )


async def _capture_web_page(workspace_id: uuid.UUID, capture_job_id: uuid.UUID) -> str:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.sessions() as session:
            job = await CapturePipeline(
                session,
                create_minio_object_store(settings),
                SafeWebFetcher(
                    timeout_seconds=settings.capture_timeout_seconds,
                    max_bytes=settings.capture_max_bytes,
                    max_attachment_bytes=settings.capture_max_attachment_bytes,
                    max_redirects=settings.capture_max_redirects,
                ),
                WebPageExtractor(),
            ).run(workspace_id, capture_job_id)
            return job.status.value
    finally:
        await database.dispose()
