# app/services/games.py
from __future__ import annotations

from typing import Optional, List
import random
import time
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_models import CollectionVersion, CollectionItem
from app.models.game import Game, GameRound
from app.services.tmdb_sync_client import get_movie
from app.services.round_builder import pick_frame_paths, choose_distractors, build_options


class AnswerError(Exception):
    """Для понятных ошибок ответа (не найдено, уже отвечено и т.д.)."""
    pass


async def create_game_from_collection(
    session: AsyncSession,
    *,
    version_id: int,
    mode: str = "ONE_FRAME_FOUR_TITLES",
    total_rounds: Optional[int] = None,
    seed: Optional[int] = None,
) -> Game:
    # проверяем, что версия существует
    ver = await session.scalar(
        select(CollectionVersion).where(CollectionVersion.id == version_id)
    )
    if not ver:
        raise ValueError(f"CollectionVersion {version_id} not found")

    items = (
        await session.execute(
            select(CollectionItem)
            .where(CollectionItem.version_id == version_id)
            .order_by(CollectionItem.ord)
        )
    ).scalars().all()

    if not items:
        raise ValueError("Collection has no items")

    max_rounds = len(items)
    n_rounds = total_rounds or min(100, max_rounds)

    # seed: либо явный, либо из времени
    if seed is None:
        seed = int(time.time())
    rng = random.Random(seed)

    # пока просто берём первые n_rounds, позже можно перемешать
    selected = list(items[:n_rounds])

    game = Game(
        version_id=version_id,
        mode=mode,
        total_rounds=n_rounds,
        seed=seed,
        score=0,
        created_at=datetime.utcnow(),
        finished_at=None,
    )
    session.add(game)
    await session.flush()  # чтобы появился game.id

    ord_counter = 1
    for item in selected:
        tmdb_id = item.tmdb_id
        tmdb_type = item._type or "movie"

        correct_doc = await get_movie(tmdb_id, _type=tmdb_type)
        if not correct_doc:
            continue

        frame_paths = await pick_frame_paths(tmdb_id, tmdb_type, mode, rng)
        if not frame_paths:
            # на всякий случай, если вдруг фильм без кадров
            continue

        distractors = await choose_distractors(correct_doc, need=3, rng=rng)
        if len(distractors) < 3:
            # если не смогли набрать вариантов — пропускаем (MVP)
            continue

        options, correct_index = build_options(correct_doc, distractors, rng)

        gr = GameRound(
            game_id=game.id,
            ord=ord_counter,
            correct_tmdb_id=tmdb_id,
            _type=tmdb_type,
            frame_paths=frame_paths,
            options=options,
            correct_index=correct_index,
            answered_index=None,
            is_correct=None,
            answered_at=None,
        )
        session.add(gr)
        ord_counter += 1

    # реальное количество раундов, которое удалось собрать
    game.total_rounds = ord_counter - 1
    await session.commit()
    await session.refresh(game)
    return game


async def answer_round(
    session: AsyncSession,
    *,
    game_id: int,
    ord: int,
    answer_index: int,
) -> tuple[Game, GameRound, bool]:
    """
    Обрабатывает ответ на раунд.
    Возвращает (game, round, finished_now).

    finished_now == True, если после этого ответа игра стала завершённой.
    """
    game = await session.get(Game, game_id)
    if not game:
        raise AnswerError("Game not found")

    gr = await session.scalar(
        select(GameRound).where(
            GameRound.game_id == game_id,
            GameRound.ord == ord,
        )
    )
    if not gr:
        raise AnswerError("Round not found")

    # если уже отвечено — просто возвращаем текущее состояние (без модификаций)
    if gr.answered_index is not None:
        return game, gr, (game.finished_at is not None)

    # валидация индекса
    if answer_index < 0 or answer_index >= len(gr.options):
        raise AnswerError("Invalid answer index")

    # проставляем ответ
    gr.answered_index = answer_index
    gr.is_correct = (answer_index == gr.correct_index)
    gr.answered_at = datetime.utcnow()

    # простое правило: +1 очко за правильный ответ
    if gr.is_correct:
        game.score += 1

    # проверяем, остались ли ещё неотвеченные раунды
    res = await session.execute(
        select(func.count())
        .select_from(GameRound)
        .where(
            GameRound.game_id == game_id,
            GameRound.answered_index.is_(None),
        )
    )
    remaining = res.scalar_one()

    finished_now = False
    if remaining == 0 and game.finished_at is None:
        game.finished_at = datetime.utcnow()
        finished_now = True

    await session.commit()
    await session.refresh(game)
    await session.refresh(gr)

    return game, gr, finished_now
