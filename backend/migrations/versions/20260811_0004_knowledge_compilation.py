"""Create Knowledge Compilation registry and job tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0004"
down_revision: str | None = "20260807_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("note_version_id", sa.Uuid(), nullable=True),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("openkb_document_id", sa.String(length=160), nullable=False),
        sa.Column(
            "compiled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "note_version_id"],
            ["note_versions.workspace_id", "note_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_knowledge_documents_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "knowledge_base_id",
            "source_version_id",
            name="uq_knowledge_documents_kb_source_version",
        ),
    )
    for column in ("workspace_id", "knowledge_base_id", "source_version_id", "note_version_id"):
        op.create_index(f"ix_knowledge_documents_{column}", "knowledge_documents", [column])

    op.create_table(
        "compilation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("note_version_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("worker_version", sa.String(length=160), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("wikilink_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "note_version_id"],
            ["note_versions.workspace_id", "note_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_compilation_jobs_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_compilation_jobs_workspace_id_idempotency_key",
        ),
    )
    for column in ("workspace_id", "knowledge_base_id", "source_version_id", "note_version_id"):
        op.create_index(f"ix_compilation_jobs_{column}", "compilation_jobs", [column])


def downgrade() -> None:
    op.drop_table("compilation_jobs")
    op.drop_table("knowledge_documents")
