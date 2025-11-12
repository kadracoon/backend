import os, httpx


TMDB_SYNC_URL = os.getenv("TMDB_SYNC_URL", "http://tmdb-sync:8000")


def _clean(d: dict) -> dict:
    # убираем None, пустые строки, пустые списки/словари
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


async def tmdb_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{TMDB_SYNC_URL}{path}", params=_clean(params or {}))
        r.raise_for_status()
        return r.json()


async def search_movies(
    *,
    genre_id: int | None = None,
    country_code: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    is_animated: bool | None = None,
    sort_by: str = "vote_count",   # мы хотим уметь сортировать и по голосам
    order: str = "desc",
    limit: int = 100,
    skip: int = 0,
    _type: str = "movie",
):
    return await tmdb_get(
        "/movies/search",
        {
            "genre_id": genre_id,
            "country_code": country_code,  # ВАЖНО: не "country"
            "year_from": year_from,
            "year_to": year_to,
            "is_animated": is_animated,
            "_type": _type,
            "sort_by": sort_by,
            "order": order,
            "limit": limit,
            "skip": skip,                  # хотим постраничность
        },
    )
