from httpx import ASGITransport, AsyncClient

from flywiki.app import create_app
from flywiki.config import Settings
from flywiki.db.database import Database
from flywiki.workspaces.bootstrap import bootstrap_default_context


async def test_workspace_header_is_required_and_must_match(database: Database) -> None:
    settings = Settings(bootstrap_on_start=False)
    async with database.sessions() as session:
        context = await bootstrap_default_context(session, settings)
    app = create_app(settings, database=database)
    path = f"/api/workspaces/{context.workspace.id}/knowledge-bases"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get(path)
        mismatch = await client.get(path, headers={"X-Workspace-ID": str(context.owner.id)})
        correct = await client.get(
            path, headers={"X-Workspace-ID": str(context.workspace.id)}
        )

    assert missing.status_code == 400
    assert mismatch.status_code == 403
    assert correct.status_code == 200
    assert [item["id"] for item in correct.json()] == [str(context.knowledge_base.id)]

