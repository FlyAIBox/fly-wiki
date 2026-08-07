"""Create immutable Source Registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0002"
down_revision: str | None = "20260806_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # Align the foundation migration with its ORM contract. Existing rows
        # already receive server defaults, so making these columns NOT NULL is safe.
        for table in ("owners", "workspaces", "knowledge_bases"):
            op.alter_column(
                table,
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
            )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("canonical_uri", sa.String(length=2048), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_sources_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "identity_key",
            name="uq_sources_workspace_id_identity_key",
        ),
    )
    op.create_index("ix_sources_workspace_id", "sources", ["workspace_id"])

    op.create_table(
        "source_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_id"],
            ["sources.workspace_id", "sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_source_versions_workspace_id_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "source_id",
            "content_sha256",
            name="uq_source_versions_workspace_source_content",
        ),
    )
    op.create_index("ix_source_versions_source_id", "source_versions", ["source_id"])
    op.create_index("ix_source_versions_workspace_id", "source_versions", ["workspace_id"])

    op.create_table(
        "source_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("object_key", sa.String(length=2048), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
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
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint(
            "workspace_id",
            "source_version_id",
            "role",
            "name",
            name="uq_source_artifacts_version_role_name",
        ),
    )
    op.create_index(
        "ix_source_artifacts_source_version_id",
        "source_artifacts",
        ["source_version_id"],
    )
    op.create_index("ix_source_artifacts_workspace_id", "source_artifacts", ["workspace_id"])

    op.create_table(
        "source_capture_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
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
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_source_capture_receipts_workspace_id_idempotency_key",
        ),
    )
    op.create_index(
        "ix_source_capture_receipts_source_version_id",
        "source_capture_receipts",
        ["source_version_id"],
    )
    op.create_index(
        "ix_source_capture_receipts_workspace_id",
        "source_capture_receipts",
        ["workspace_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_source_immutable_update()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '% is immutable', TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table in ("source_versions", "source_artifacts"):
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION reject_source_immutable_update()
                """
            )


def downgrade() -> None:
    op.drop_table("source_capture_receipts")
    op.drop_table("source_artifacts")
    op.drop_table("source_versions")
    op.drop_table("sources")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION reject_source_immutable_update()")
        for table in ("owners", "workspaces", "knowledge_bases"):
            op.alter_column(
                table,
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=True,
            )
