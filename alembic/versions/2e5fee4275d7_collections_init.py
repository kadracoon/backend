"""collections init

Revision ID: 2e5fee4275d7
Revises: 
Create Date: 2025-11-12 14:41:29.483662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e5fee4275d7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", sa.String(50), nullable=False, server_default="ONE_FRAME_FOUR_TITLES"),
        sa.Column("rule_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "collection_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("compiled_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("rule_overrides_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.UniqueConstraint("collection_id", "version", name="uq_collection_version"),
    )
    op.create_table(
        "collection_items",
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("collection_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("_type", sa.String(10), nullable=False, server_default="movie"),
        sa.PrimaryKeyConstraint("version_id", "ord"),
    )


def downgrade():
    op.drop_table("collection_items")
    op.drop_table("collection_versions")
    op.drop_table("collections")
