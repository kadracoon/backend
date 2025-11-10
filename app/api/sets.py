from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.db import get_pool
from app.core.tmdb_sync_client import get_movie, get_frames, search_similar


router = APIRouter(prefix="/sets", tags=["sets"])


class Top100In(BaseModel):
    name: str
    tmdb_ids: List[int]  # ровно 100 на вход


@router.post("/top100")
async def create_top100(payload: Top100In):
    if len(payload.tmdb_ids) != 100:
        raise HTTPException(400, "need exactly 100 ids")

    pool = await get_pool()
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            set_id = await conn.fetchval(
                "INSERT INTO sets(name, type, size) VALUES($1,'STATIC',$2) RETURNING id",
                payload.name, len(payload.tmdb_ids)
            )
            # фиксируем порядок
            for i, mid in enumerate(payload.tmdb_ids, start=1):
                await conn.execute(
                    "INSERT INTO set_items(set_id, ord, tmdb_id) VALUES($1,$2,$3)",
                    set_id, i, mid
                )
            # строим questions + set_questions
            qids = []
            for i, mid in enumerate(payload.tmdb_ids, start=1):
                meta = await get_movie(mid)
                frames = await get_frames(mid)
                frames = [f["frame_path"] for f in frames if f.get("frame_path")]
                if not frames:
                    raise HTTPException(400, f"movie {mid} has no frames")

                # выбираем 1 лучший кадр (MVP: первый)
                frame_paths = [frames[0]]

                # собираем пул дистракторов
                year = int(meta["release_date"][:4]) if meta.get("release_date") else None
                genre_ids = meta.get("genre_ids", [])
                candidates = await search_similar(genre_ids, year, _type=meta.get("_type","movie"), limit=120)

                pool_ids = []
                for c in candidates:
                    cid = c["id"]
                    if cid != mid and cid not in pool_ids:
                        pool_ids.append(cid)
                    if len(pool_ids) >= 16:
                        break
                if len(pool_ids) < 6:  # запас на выбор 3-х
                    raise HTTPException(400, f"not enough distractors for {mid}")

                qid = await conn.fetchval(
                    "INSERT INTO questions(type, tmdb_id, frame_paths, distractor_pool) VALUES($1,$2,$3,$4) RETURNING id",
                    "ONE_FRAME_FOUR_TITLES", mid, frame_paths, pool_ids
                )
                qids.append(qid)

                await conn.execute(
                    "INSERT INTO set_questions(set_id, ord, question_id) VALUES($1,$2,$3)",
                    set_id, i, qid
                )

            await tr.commit()
            return {"set_id": set_id, "questions": len(qids)}
        except Exception:
            await tr.rollback()
            raise
