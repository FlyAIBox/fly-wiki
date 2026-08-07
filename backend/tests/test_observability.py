from flywiki.observability.adapters import LangfuseObservability, NoopObservability
from flywiki.observability.interface import ObservabilityEvent


class FakeLangfuse:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def create_event(self, **event) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)


def test_langfuse_adapter_only_forwards_allowlisted_metadata() -> None:
    client = FakeLangfuse()
    observability = LangfuseObservability(client)

    observability.record(
        ObservabilityEvent(
            name="workspace.bootstrap",
            trace_id="0" * 32,
            metadata={
                "workspace_id": "workspace-1",
                "status": "ok",
                "secret": "must-not-leave-process",
                "document_body": "private",
            },
        )
    )

    assert client.events == [
        {
            "name": "workspace.bootstrap",
            "trace_context": {"trace_id": "0" * 32},
            "metadata": {"workspace_id": "workspace-1", "status": "ok"},
        }
    ]


def test_noop_observability_accepts_events() -> None:
    NoopObservability().record(ObservabilityEvent(name="test", trace_id="trace"))

