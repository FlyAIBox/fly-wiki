from dataclasses import dataclass

from httpx import ASGITransport, AsyncClient

from flywiki.app import create_app
from flywiki.config import Settings
from flywiki.db.database import Database
from flywiki.health.service import ComponentHealth, HealthService


@dataclass
class FakeProbe:
    name: str
    healthy: bool

    async def check(self) -> ComponentHealth:
        return ComponentHealth(self.name, self.healthy, "test")


async def test_readiness_reports_each_component(database: Database) -> None:
    health = HealthService([FakeProbe("database", True), FakeProbe("langfuse", False)])
    app = create_app(
        Settings(bootstrap_on_start=False), database=database, health_service=health
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "components": {
            "database": {"name": "database", "healthy": True, "detail": "test"},
            "langfuse": {"name": "langfuse", "healthy": False, "detail": "test"},
        },
    }

