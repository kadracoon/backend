import httpx
from app.core.config import TMDB_SYNC_URL


async def get_movie(tmdb_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{TMDB_SYNC_URL}/movies/{tmdb_id}")
        r.raise_for_status()
        return r.json()


async def get_frames(tmdb_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{TMDB_SYNC_URL}/movies/{tmdb_id}/frames")
        r.raise_for_status()
        return r.json()["frames"]


async def search_similar(genre_ids, year, _type="movie", limit=80):
    params = {"_type": _type, "limit": limit, "sort_by": "popularity", "order": "desc"}
    if genre_ids:
        params["genre_id"] = genre_ids[0]  # MVP: по главному жанру
    if year:
        params["year_from"] = max(int(year) - 1, 1900)
        params["year_to"]   = int(year) + 1
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{TMDB_SYNC_URL}/movies/search", params=params)
        r.raise_for_status()
        return r.json()["items"]
