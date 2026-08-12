from celery import Celery

from flywiki.config import get_settings

settings = get_settings()

celery_app = Celery(
    "flywiki",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="flywiki.health.ping")
def ping() -> str:
    return "pong"


# Import task modules after celery_app is constructed to avoid circular imports.
from flywiki.compilation import tasks as compilation_tasks  # noqa: E402, F401
from flywiki.sources import tasks as source_tasks  # noqa: E402, F401
