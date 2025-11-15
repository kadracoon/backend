"""add rule to collection_versions

Revision ID: e9c23adad4c8
Revises: fc19c5ebd54b
Create Date: 2025-11-14 22:11:05.608821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9c23adad4c8'
down_revision: Union[str, Sequence[str], None] = 'fc19c5ebd54b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collection_versions",
        sa.Column("rule", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("collection_versions", "rule")

