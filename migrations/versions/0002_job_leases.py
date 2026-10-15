"""Add a lease for crash recovery of extraction jobs.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("lease_until", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("jobs", "lease_until")
