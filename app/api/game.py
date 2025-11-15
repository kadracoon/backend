from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_session
from app.models.game import Game, GameRound
from app.services.games import create_game_from_collection


router = APIRouter(prefix="/games", tags=["games"])


class GameCreate(BaseModel):
    version_id: int
    mode: Literal["ONE_FRAME_FOUR_TITLES", "FOUR_FRAMES_ONE_TITLE"] = "ONE_FRAME_FOUR_TITLES"
    total_rounds: Optional[int] = None
    seed: Optional[int] = None


class GameCreated(BaseModel):
    id: int
    version_id: int
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


@router.post("", response_model=GameCreated, status_code=status.HTTP_201_CREATED)
async def create_game(
    body: GameCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        game = await create_game_from_collection(
            session,
            version_id=body.version_id,
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
        version_id=game.version_id,
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

    gr = await session.get(GameRound, {"game_id": game_id, "ord": ord})
    # если composite PK не работает так, как ожидаем, можно сделать явно:
    # gr = await session.scalar(
    #     select(GameRound).where(GameRound.game_id == game_id, GameRound.ord == ord)
    # )
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
