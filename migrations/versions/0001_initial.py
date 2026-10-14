"""Initial persistence schema.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(32), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("file_size_bytes > 0"),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "sha256", "document_type"),
    )
    op.create_table(
        "verification_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(100), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("workspace_id", "source_key"),
    )
    op.create_table(
        "case_documents",
        sa.Column("case_id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "case_id"],
            ["verification_cases.workspace_id", "verification_cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id"], ["documents.workspace_id", "documents.id"]
        ),
        sa.UniqueConstraint("case_id", "document_type"),
    )
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100)),
        sa.Column("predictions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "version"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("verification_cases.id"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("corrections", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "verification_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("verification_cases.id"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "evidence_refs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "extraction_run_id",
            sa.String(36),
            sa.ForeignKey("extraction_runs.id"),
            nullable=False,
        ),
        sa.Column("field_path", sa.String(200), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON()),
        sa.Column("excerpt", sa.String()),
    )


def downgrade():
    for name in (
        "evidence_refs",
        "verification_findings",
        "review_events",
        "jobs",
        "extraction_runs",
        "case_documents",
        "verification_cases",
        "documents",
        "workspaces",
    ):
        op.drop_table(name)
