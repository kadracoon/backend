from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    version_id: Mapped[int] = mapped_column(
        ForeignKey("collection_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mode: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="ONE_FRAME_FOUR_TITLES",
    )

    total_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # отношения
    rounds: Mapped[List["GameRound"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="GameRound.ord",
    )


class GameRound(Base):
    __tablename__ = "game_rounds"

    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ord: Mapped[int] = mapped_column(Integer, primary_key=True)

    correct_tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    _type: Mapped[str] = mapped_column(String(10), nullable=False, default="movie")

    # список путей кадров, которые показываем в раунде
    frame_paths: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    # варианты ответа: [{id,title,title_ru}, ...]
    options: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
    )

    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answered_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    game: Mapped["Game"] = relationship(back_populates="rounds")
