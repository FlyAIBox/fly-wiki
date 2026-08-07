import asyncio
from dataclasses import asdict, dataclass
from typing import Protocol

import httpx
from redis.asyncio import Redis
from sqlalchemy import text

from flywiki.db.database import Database


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    healthy: bool
    detail: str = "ok"


class HealthProbe(Protocol):
    name: str

    async def check(self) -> ComponentHealth: ...


class DatabaseProbe:
    name = "database"

    def __init__(self, database: Database) -> None:
        self._database = database

    async def check(self) -> ComponentHealth:
        try:
            async with self._database.sessions() as session:
                await session.execute(text("SELECT 1"))
            return ComponentHealth(self.name, True)
        except Exception as exc:  # noqa: BLE001 - health endpoint must report failures
            return ComponentHealth(self.name, False, type(exc).__name__)


class RedisProbe:
    name = "redis"

    def __init__(self, url: str) -> None:
        self._url = url

    async def check(self) -> ComponentHealth:
        client = Redis.from_url(self._url, socket_connect_timeout=1, socket_timeout=1)
        try:
            await client.ping()
            return ComponentHealth(self.name, True)
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(self.name, False, type(exc).__name__)
        finally:
            await client.aclose()


class HttpProbe:
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self._url = url

    async def check(self) -> ComponentHealth:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(self._url)
                response.raise_for_status()
            return ComponentHealth(self.name, True)
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(self.name, False, type(exc).__name__)


class CeleryProbe:
    name = "worker"

    def __init__(self, celery_app) -> None:  # type: ignore[no-untyped-def]
        self._celery_app = celery_app

    async def check(self) -> ComponentHealth:
        def ping() -> bool:
            responses = self._celery_app.control.inspect(timeout=1).ping()
            return bool(responses)

        try:
            healthy = await asyncio.to_thread(ping)
            return ComponentHealth(self.name, healthy, "ok" if healthy else "no workers")
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(self.name, False, type(exc).__name__)


class HealthService:
    def __init__(self, probes: list[HealthProbe]) -> None:
        self._probes = probes

    async def readiness(self) -> dict:
        results = await asyncio.gather(*(probe.check() for probe in self._probes))
        return {
            "status": "ready" if all(result.healthy for result in results) else "degraded",
            "components": {result.name: asdict(result) for result in results},
        }

