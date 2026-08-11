import hashlib
import uuid

from flywiki.agents.interface import AcquiredSource
from flywiki.sources.acquisition import SourceAcquisitionService
from flywiki.sources.service import normalize_web_url


class SourceAcquisitionGateway:
    """Expose source acquisition to agents without exposing persistence internals."""

    def __init__(
        self,
        service: SourceAcquisitionService,
        *,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> None:
        self._service = service
        self._workspace_id = workspace_id
        self._run_id = run_id
        self._acquired_by_url: dict[str, AcquiredSource] = {}

    @property
    def acquired_sources(self) -> tuple[AcquiredSource, ...]:
        return tuple(self._acquired_by_url.values())

    async def acquire_source(self, url: str) -> AcquiredSource:
        canonical_url = normalize_web_url(url)
        existing = self._acquired_by_url.get(canonical_url)
        if existing is not None:
            return existing

        url_digest = hashlib.sha256(canonical_url.encode()).hexdigest()
        result = await self._service.acquire(
            workspace_id=self._workspace_id,
            url=canonical_url,
            idempotency_key=f"agent:{self._run_id}:{url_digest}",
        )
        acquired = AcquiredSource(
            canonical_url=result.canonical_url,
            markdown=result.markdown,
            backend=result.backend,
            source_version_id=result.source_version_id,
        )
        self._acquired_by_url[canonical_url] = acquired
        return acquired
