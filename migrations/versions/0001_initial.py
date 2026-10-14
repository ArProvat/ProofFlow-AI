"""Initial persistence schema.

Revision ID: 0001
Revises:
"""

from alembic import op

import proofflow.models  # noqa: F401
from proofflow.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for table in Base.metadata.sorted_tables:
        op.create_table(table.name, *table.columns, *table.constraints)


def downgrade():
    for table in reversed(Base.metadata.sorted_tables):
        op.drop_table(table.name)
