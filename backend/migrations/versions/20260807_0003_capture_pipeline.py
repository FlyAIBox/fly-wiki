"""Create Capture Job and Editable Note tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0003"
down_revision: str | None = "20260807_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_capture_jobs_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_capture_jobs_workspace_id_idempotency_key",
        ),
    )
    op.create_index("ix_capture_jobs_knowledge_base_id", "capture_jobs", ["knowledge_base_id"])
    op.create_index("ix_capture_jobs_source_version_id", "capture_jobs", ["source_version_id"])
    op.create_index("ix_capture_jobs_workspace_id", "capture_jobs", ["workspace_id"])

    op.create_table(
        "editable_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_version_id"],
            ["source_versions.workspace_id", "source_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_editable_notes_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "source_version_id",
            name="uq_editable_notes_workspace_id_source_version_id",
        ),
    )
    op.create_index("ix_editable_notes_source_version_id", "editable_notes", ["source_version_id"])
    op.create_index("ix_editable_notes_workspace_id", "editable_notes", ["workspace_id"])

    op.create_table(
        "note_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("note_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "note_id"],
            ["editable_notes.workspace_id", "editable_notes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_note_versions_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "note_id",
            "version_number",
            name="uq_note_versions_workspace_note_version_number",
        ),
    )
    op.create_index("ix_note_versions_note_id", "note_versions", ["note_id"])
    op.create_index("ix_note_versions_workspace_id", "note_versions", ["workspace_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE TRIGGER trg_note_versions_immutable
            BEFORE UPDATE ON note_versions
            FOR EACH ROW EXECUTE FUNCTION reject_source_immutable_update()
            """
        )


def downgrade() -> None:
    op.drop_table("note_versions")
    op.drop_table("editable_notes")
    op.drop_table("capture_jobs")
