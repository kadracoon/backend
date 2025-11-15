"""games schema

Revision ID: fc19c5ebd54b
Revises: 2e5fee4275d7
Create Date: 2025-11-14 15:55:06.878780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc19c5ebd54b'
down_revision: Union[str, Sequence[str], None] = '2e5fee4275d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Таблица игр
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("collection_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(40),
            nullable=False,
            server_default="ONE_FRAME_FOUR_TITLES",
            comment="игровой режим",
        ),
        sa.Column("total_rounds", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

    # Таблица раундов
    op.create_table(
        "game_rounds",
        sa.Column(
            "game_id",
            sa.Integer(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ord", sa.Integer(), primary_key=True),
        sa.Column("correct_tmdb_id", sa.Integer(), nullable=False),
        sa.Column(
            "_type",
            sa.String(10),
            nullable=False,
            server_default="movie",
        ),
        sa.Column(
            "frame_paths",
            sa.JSON(),
            nullable=False,
            comment="список путей кадров, которые показываем в раунде",
        ),
        sa.Column(
            "options",
            sa.JSON(),
            nullable=False,
            comment="варианты ответов: список объектов {id,title,title_ru}",
        ),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("answered_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
    )

    # Индексы для быстрого поиска
    op.create_index(
        "ix_games_version_id",
        "games",
        ["version_id"],
    )
    op.create_index(
        "ix_games_finished_at",
        "games",
        ["finished_at"],
    )
    op.create_index(
        "ix_game_rounds_correct_tmdb_id",
        "game_rounds",
        ["correct_tmdb_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_game_rounds_correct_tmdb_id", table_name="game_rounds")
    op.drop_index("ix_games_finished_at", table_name="games")
    op.drop_index("ix_games_version_id", table_name="games")
    op.drop_table("game_rounds")
    op.drop_table("games")
