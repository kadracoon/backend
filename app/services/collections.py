from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.collection_models import Collection, CollectionVersion, CollectionItem
from app.services.tmdb_sync_client import search_movies
import math


DEFAULT_RULE = {
    "filters": {
        "year_from": None, "year_to": None,
        "genre_ids": [],           # список или один id
        "country": None,
        "is_animated": None,
        "_type": "movie",          # movie|tv
    },
    "sort": {"by": "vote_count", "order": "desc"},
    "limit": 100
}


def merge_rules(base: dict, overrides: dict | None) -> dict:
    if not overrides: return base
    out = {**base}
    bf, of = base.get("filters", {}), (overrides.get("filters", {}) if overrides else {})
    bs, os_ = base.get("sort", {}), (overrides.get("sort", {}) if overrides else {})
    out["filters"] = {**bf, **of}
    out["sort"] = {**bs, **os_}
    if "limit" in overrides: out["limit"] = overrides["limit"]
    return out


async def compute_next_version(session: AsyncSession, collection_id: int) -> int:
    row = await session.execute(
        select(CollectionVersion.version).where(CollectionVersion.collection_id == collection_id).order_by(CollectionVersion.version.desc()).limit(1)
    )
    v = row.scalar_one_or_none()
    return 1 if v is None else (v + 1)


async def materialize_collection(
    session: AsyncSession,
    collection: Collection,
    overrides: dict | None = None,
    seed: int | None = None
) -> int:
    rule = merge_rules(collection.rule_json, overrides)
    filters = rule["filters"]
    sort_by = rule["sort"]["by"]
    order = rule["sort"]["order"]
    total_needed = int(rule.get("limit", 100))

    # Поддержим список жанров (берём первый жанр как главный фильтр; расширение — потом)
    genre_id = None
    if filters.get("genre_ids"):
        if isinstance(filters["genre_ids"], list) and len(filters["genre_ids"]) > 0:
            genre_id = filters["genre_ids"][0]
        elif isinstance(filters["genre_ids"], int):
            genre_id = filters["genre_ids"]

    # Пакетный сбор через /movies/search (там есть limit/skip)
    batch, skip, got_ids = 100, 0, []
    while len(got_ids) < total_needed:
        country_code = filters.get("country") or filters.get("country_code")
        resp = await search_movies(
            genre_id=genre_id,
            country_code=country_code,
            year_from=filters.get("year_from"),
            year_to=filters.get("year_to"),
            is_animated=filters.get("is_animated"),
            sort_by=sort_by, order=order,
            limit=min(batch, total_needed - len(got_ids)),
            skip=skip,
            _type=filters.get("type_") or "movie",
        )
        results = resp.get("results", [])
        if not results: break
        for r in results:
            if r["id"] not in got_ids:
                got_ids.append(r["id"])
        skip += len(results)
        if len(results) < batch:
            break

    # Создаём версию
    version = await compute_next_version(session, collection.id)
    v = CollectionVersion(
        collection_id=collection.id,
        version=version,
        size=len(got_ids),
        seed=seed,
        rule_overrides_json=overrides or {},
        status="published",
    )
    session.add(v)
    await session.flush()

    # Сохраняем элементы
    for i, mid in enumerate(got_ids, start=1):
        session.add(
            CollectionItem(
                version_id=v.id,
                ord=i,
                tmdb_id=mid,
                _type=filters.get("type_") or "movie",
            )
        )

    await session.commit()
    return v.id
