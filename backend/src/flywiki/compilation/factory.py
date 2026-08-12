from flywiki.compilation.adapters import HttpOpenKBAdapter
from flywiki.compilation.interface import OpenKBAdapter
from flywiki.config import Settings


def create_openkb_adapter(settings: Settings) -> OpenKBAdapter:
    return HttpOpenKBAdapter(
        settings.openkb_worker_url,
        fallback_url=settings.openkb_fallback_worker_url,
        timeout_seconds=settings.openkb_timeout_seconds,
    )
