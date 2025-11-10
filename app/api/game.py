import random, time, hashlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.db import get_pool


router = APIRouter(prefix="/game", tags=["game"])


class StartSessionIn(BaseModel):
    set_id: int


@router.post("/sessions")
async def start_session(payload: StartSessionIn):
    pool = await get_pool()
    async with pool.acquire() as conn:
        size = await conn.fetchval("SELECT size FROM sets WHERE id=$1", payload.set_id)
        if not size:
            raise HTTPException(404, "set not found or empty")
        sid = await conn.fetchval(
            "INSERT INTO sessions(set_id, total_questions) VALUES($1,$2) RETURNING id",
            payload.set_id, size
        )
        return {"session_id": sid, "total": size}


@router.get("/sessions/{session_id}/next")
async def next_round(session_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
        SELECT s.set_id, s.total_questions, COUNT(r.*) AS answered
        FROM sessions s
        LEFT JOIN rounds r ON r.session_id = s.id AND r.answered_tmdb_id IS NOT NULL
        WHERE s.id=$1
        GROUP BY s.id
        """, session_id)
        if not row:
            raise HTTPException(404, "session not found")

        answered = row["answered"]
        total = row["total_questions"]
        if answered >= total:
            return {"done": True}

        # какой вопрос по порядку
        idx = answered + 1
        qrow = await conn.fetchrow("""
        SELECT q.id as qid, q.tmdb_id, q.frame_paths, q.distractor_pool
        FROM set_questions sq
        JOIN questions q ON q.id = sq.question_id
        WHERE sq.set_id=$1 AND sq.ord=$2
        """, row["set_id"], idx)
        if not qrow:
            raise HTTPException(404, "question not found")

        # генерим стабильные 3 дистрактора: seed по session+question
        seed = int(hashlib.sha256(f"{session_id}:{qrow['qid']}".encode()).hexdigest(), 16)
        rnd = random.Random(seed)
        pool_ids = list(qrow["distractor_pool"])
        rnd.shuffle(pool_ids)
        options = [qrow["tmdb_id"]] + pool_ids[:3]
        rnd.shuffle(options)

        # создаём round, если ещё не был создан
        ex = await conn.fetchrow("SELECT id FROM rounds WHERE session_id=$1 AND idx=$2", session_id, idx)
        if not ex:
            await conn.execute("""
            INSERT INTO rounds(session_id, question_id, idx, options_tmdb_ids, answer_tmdb_id)
            VALUES($1,$2,$3,$4,$5)
            """, session_id, qrow["qid"], idx, options, qrow["tmdb_id"])

        # собираем URLы картинок (собирает фронт, мы отдаём пути)
        return {
            "done": False,
            "round_index": idx,
            "question": {
                "type": "ONE_FRAME_FOUR_TITLES",
                "frame_paths": qrow["frame_paths"],  # это "/abc.jpg" и т.п.
                "options_tmdb_ids": options,
            }
        }


class AnswerIn(BaseModel):
    tmdb_id: int


@router.post("/rounds/{session_id}/{round_index}/answer")
async def answer(session_id: int, round_index: int, payload: AnswerIn):
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow("""
        SELECT id, answer_tmdb_id, answered_tmdb_id FROM rounds
        WHERE session_id=$1 AND idx=$2
        """, session_id, round_index)
        if not r:
            raise HTTPException(404, "round not found")
        if r["answered_tmdb_id"] is not None:
            # идемпотентность
            is_correct = (r["answered_tmdb_id"] == r["answer_tmdb_id"])
            return {"is_correct": is_correct, "correct": r["answer_tmdb_id"]}

        is_correct = (payload.tmdb_id == r["answer_tmdb_id"])
        await conn.execute("""
        UPDATE rounds SET answered_tmdb_id=$1, is_correct=$2, answered_at=now()
        WHERE id=$3
        """, payload.tmdb_id, is_correct, r["id"])
        return {"is_correct": is_correct, "correct": r["answer_tmdb_id"]}
