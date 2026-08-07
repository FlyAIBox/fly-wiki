from flywiki.config import Settings
from flywiki.observability.adapters import LangfuseObservability, NoopObservability
from flywiki.observability.interface import Observability


def create_observability(settings: Settings) -> Observability:
    if settings.observability_backend != "langfuse":
        return NoopObservability()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise ValueError("Langfuse observability requires public and secret keys")

    from langfuse import Langfuse

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return LangfuseObservability(client)

