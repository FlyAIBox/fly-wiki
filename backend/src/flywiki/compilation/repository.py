import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.compilation.models import CompilationJob, KnowledgeDocument
from flywiki.workspaces.models import KnowledgeBase


class CompilationResourceNotFound(LookupError):
    """Raised without disclosing cross-Workspace resources."""


class CompilationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_job(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> CompilationJob:
        job = await self._session.scalar(
            select(CompilationJob).where(
                CompilationJob.workspace_id == workspace_id,
                CompilationJob.id == job_id,
            )
        )
        if job is None:
            raise CompilationResourceNotFound("Compilation Job not found")
        return job

    async def find_job(
        self, workspace_id: uuid.UUID, idempotency_key: str
    ) -> CompilationJob | None:
        return await self._session.scalar(
            select(CompilationJob).where(
                CompilationJob.workspace_id == workspace_id,
                CompilationJob.idempotency_key == idempotency_key,
            )
        )

    async def get_document(
        self,
        workspace_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
        source_version_id: uuid.UUID,
    ) -> KnowledgeDocument | None:
        return await self._session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.knowledge_base_id == knowledge_base_id,
                KnowledgeDocument.source_version_id == source_version_id,
            )
        )

    async def list_documents(
        self, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> list[KnowledgeDocument]:
        documents = await self._session.scalars(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.knowledge_base_id == knowledge_base_id,
            )
            .order_by(KnowledgeDocument.compiled_at, KnowledgeDocument.id)
        )
        return list(documents)

    async def lock_knowledge_base(
        self, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID
    ) -> None:
        knowledge_base = await self._session.scalar(
            select(KnowledgeBase)
            .where(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.id == knowledge_base_id,
            )
            .with_for_update()
        )
        if knowledge_base is None:
            raise CompilationResourceNotFound("Knowledge Base not found")
