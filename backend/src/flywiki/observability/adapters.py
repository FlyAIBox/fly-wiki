from typing import Protocol

from flywiki.observability.interface import ObservabilityEvent

ALLOWED_METADATA = {
    "workspace_id",
    "knowledge_base_id",
    "task_id",
    "task_type",
    "version",
    "duration_ms",
    "status",
}


class LangfuseClient(Protocol):
    def create_event(
        self,
        *,
        name: str,
        trace_context: dict[str, str],
        metadata: dict,
    ) -> object: ...


class NoopObservability:
    def record(self, event: ObservabilityEvent) -> None:
        del event


class LangfuseObservability:
    """Small Adapter that prevents private payloads from entering Langfuse by default."""

    def __init__(self, client: LangfuseClient) -> None:
        self._client = client

    def record(self, event: ObservabilityEvent) -> None:
        safe_metadata = {
            key: value for key, value in event.metadata.items() if key in ALLOWED_METADATA
        }
        self._client.create_event(
            name=event.name,
            trace_context={"trace_id": event.trace_id},
            metadata=safe_metadata,
        )
