from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ObservabilityEvent:
    name: str
    trace_id: str
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


class Observability(Protocol):
    def record(self, event: ObservabilityEvent) -> None: ...

