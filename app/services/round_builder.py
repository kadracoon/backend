from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime
import random

from app.services.tmdb_sync_client import get_movie, get_frames, search_movies


def _extract_year(release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return int(release_date[:4])
    except Exception:
        return None


async def pick_frame_paths(
    tmdb_id: int,
    _type: str,
    mode: str,
    rng: random.Random,
) -> List[str]:
    """Выбираем кадры для раунда.

    ONE_FRAME_FOUR_TITLES  -> 1 кадр
    FOUR_FRAMES_ONE_TITLE  -> до 4 кадров
    """
    frames = await get_frames(tmdb_id, _type=_type)
    if not frames:
        return []

    # уже отсортированы на стороне tmdb-sync по качеству, но чуть перетасуем
    rng.shuffle(frames)

    if mode == "FOUR_FRAMES_ONE_TITLE":
        return [f["path"] for f in frames[:4]]
    else:
        return [frames[0]["path"]]


async def choose_distractors(
    correct_doc: Dict[str, Any],
    *,
    need: int,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Подбираем отвлекающие фильмы.

    Стратегия:
    1) тот же первый жанр + то же десятилетие
    2) тот же жанр
    3) то же десятилетие
    4) fallback: просто топ по голосам
    """
    year = _extract_year(correct_doc.get("release_date"))
    decade = (year // 10) * 10 if year else None
    genre_ids = correct_doc.get("genre_ids") or []
    main_genre = genre_ids[0] if genre_ids else None
    tmdb_type = correct_doc.get("_type") or "movie"

    pools: List[Dict[str, Any]] = []
    if main_genre and decade:
        pools.append({"genre_id": main_genre, "year_from": decade, "year_to": decade + 9})
    if main_genre:
        pools.append({"genre_id": main_genre})
    if decade:
        pools.append({"year_from": decade, "year_to": decade + 9})
    pools.append({})  # fallback

    seen_ids = {correct_doc["id"]}
    picked: List[Dict[str, Any]] = []

    for flt in pools:
        resp = await search_movies(
            _type=tmdb_type,
            genre_id=flt.get("genre_id"),
            country_code=None,
            year_from=flt.get("year_from"),
            year_to=flt.get("year_to"),
            is_animated=None,
            sort_by="vote_count",
            order="desc",
            limit=50,
            skip=0,
        )
        items = resp.get("items") or resp.get("results") or []
        # фильтруем уже виденные
        candidates = [m for m in items if m["id"] not in seen_ids]
        rng.shuffle(candidates)
        for m in candidates:
            picked.append(m)
            seen_ids.add(m["id"])
            if len(picked) >= need:
                return picked

    return picked[:need]


def build_options(
    correct: Dict[str, Any],
    distractors: List[Dict[str, Any]],
    rng: random.Random,
) -> Tuple[List[Dict[str, Any]], int]:
    """Собираем список вариантов и возвращаем (options, correct_index)."""
    options: List[Dict[str, Any]] = []

    def to_opt(m: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": m["id"],
            "title": m.get("title") or m.get("name"),
            "title_ru": m.get("title_ru"),
        }

    options.append(to_opt(correct))
    for d in distractors:
        options.append(to_opt(d))

    rng.shuffle(options)
    correct_id = correct["id"]
    correct_index = next(
        i for i, opt in enumerate(options)
        if opt["id"] == correct_id
    )
    return options, correct_index
