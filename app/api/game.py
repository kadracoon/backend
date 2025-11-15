from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.collection_models import Collection, CollectionVersion
from app.core.db import get_session
from app.models.game import Game, GameRound
from app.services.games import create_game_from_collection, answer_round, AnswerError
# from .schemas import GameCreate, GameCreated, GameState, RoundOut  # как у тебя разнесено


router = APIRouter(prefix="/games", tags=["games"])


class GameCreate(BaseModel):
    collection_id: int
    version: Optional[int] = None      # если None — берем последнюю версию
    mode: Literal["ONE_FRAME_FOUR_TITLES", "FOUR_FRAMES_ONE_TITLE"] = "ONE_FRAME_FOUR_TITLES"
    total_rounds: Optional[int] = None
    seed: Optional[int] = None


class GameCreated(BaseModel):
    id: int
    collection_id: int
    version: int        # номер версии внутри коллекции (1,2,3...)
    mode: str
    total_rounds: int
    seed: int

    class Config:
        from_attributes = True


class GameState(BaseModel):
    id: int
    version_id: int
    mode: str
    total_rounds: int
    answered: int
    correct: int
    score: int
    finished: bool


class RoundOut(BaseModel):
    game_id: int
    ord: int
    mode: str
    total_rounds: int
    frame_paths: list[str]
    options: list[dict]
    answered_index: int | None


class AnswerIn(BaseModel):
    answer_index: int


class AnswerOut(BaseModel):
    game_id: int
    ord: int
    is_correct: bool
    correct_index: int
    score: int
    finished: bool


@router.post("", response_model=GameCreated, status_code=status.HTTP_201_CREATED)
async def create_game(
    body: GameCreate,
    session: AsyncSession = Depends(get_session),
):
    # 1. проверяем, что коллекция существует
    collection = await session.get(Collection, body.collection_id)
    if not collection:
        raise HTTPException(404, "Collection not found")

    # 2. выбираем версию
    if body.version is not None:
        ver = await session.scalar(
            select(CollectionVersion).where(
                CollectionVersion.collection_id == body.collection_id,
                CollectionVersion.version == body.version,
            )
        )
        if not ver:
            raise HTTPException(404, "Collection version not found")
    else:
        # последняя версия по номеру
        ver = await session.scalar(
            select(CollectionVersion)
            .where(CollectionVersion.collection_id == body.collection_id)
            .order_by(CollectionVersion.version.desc())
            .limit(1)
        )
        if not ver:
            raise HTTPException(400, "Collection has no compiled versions yet")

    # 3. создаём игру из выбранной версии
    try:
        game = await create_game_from_collection(
            session,
            version_id=ver.id,
            mode=body.mode,
            total_rounds=body.total_rounds,
            seed=body.seed,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if game.total_rounds == 0:
        raise HTTPException(400, "No rounds could be generated for this collection")

    return GameCreated(
        id=game.id,
        collection_id=body.collection_id,
        version=ver.version,      # человеческий номер, а не PK
        mode=game.mode,
        total_rounds=game.total_rounds,
        seed=game.seed or 0,
    )


@router.get("/{game_id}/state", response_model=GameState)
async def get_game_state(
    game_id: int,
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")

    rounds = (
        await session.execute(
            select(GameRound).where(GameRound.game_id == game_id)
        )
    ).scalars().all()

    answered = sum(1 for r in rounds if r.answered_index is not None)
    correct = sum(1 for r in rounds if r.is_correct)
    finished = game.finished_at is not None

    return GameState(
        id=game.id,
        version_id=game.version_id,
        mode=game.mode,
        total_rounds=game.total_rounds,
        answered=answered,
        correct=correct,
        score=game.score,
        finished=finished,
    )


@router.get("/{game_id}/round/{ord}", response_model=RoundOut)
async def get_round(
    game_id: int,
    ord: int,
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")

    gr = await session.scalar(
        select(GameRound).where(
            GameRound.game_id == game_id,
            GameRound.ord == ord,
        )
    )

    if not gr:
        raise HTTPException(404, "Round not found")

    return RoundOut(
        game_id=game_id,
        ord=ord,
        mode=game.mode,
        total_rounds=game.total_rounds,
        frame_paths=gr.frame_paths,
        options=gr.options,
        answered_index=gr.answered_index,
    )


@router.post("/{game_id}/round/{ord}/answer", response_model=AnswerOut)
async def answer_round_endpoint(
    game_id: int,
    ord: int,
    body: AnswerIn,
    session: AsyncSession = Depends(get_session),
):
    try:
        game, gr, finished_now = await answer_round(
            session,
            game_id=game_id,
            ord=ord,
            answer_index=body.answer_index,
        )
    except AnswerError as e:
        # мапим бизнес-ошибки в HTTP
        msg = str(e)
        if "Game not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "Round not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "Invalid answer index" in msg:
            raise HTTPException(status_code=400, detail=msg)
        # всё остальное тоже как 400
        raise HTTPException(status_code=400, detail=msg)

    return AnswerOut(
        game_id=game.id,
        ord=ord,
        is_correct=bool(gr.is_correct),
        correct_index=gr.correct_index,
        score=game.score,
        finished=(game.finished_at is not None),
    )
