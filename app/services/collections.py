from __future__ import annotations
from typing import Any, Dict, Optional
from sqlalchemy import delete, select, func
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


def _apply_overrides(rule: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Обновляем rule фильтрами из overrides (если пришли в запросе)."""
    if not overrides:
        return rule

    base_filters = rule.get("filters") or {}
    new_filters = base_filters.copy()
    for k, v in overrides.items():
        if v is not None:
            new_filters[k] = v

    new_rule = rule.copy()
    new_rule["filters"] = new_filters
    return new_rule


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
    overrides: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> int:
    """
    Создаём новую версию коллекции и наполняем collection_items.
    Возвращаем id версии.
    """

    # 1. Базовое правило берём из collection.rule_json
    base_rule: Dict[str, Any] = collection.rule_json or {}
    rule = _apply_overrides(base_rule, overrides)

    filters: Dict[str, Any] = rule.get("filters") or {}
    sort: Dict[str, Any] = rule.get("sort") or {}
    limit: int = int(rule.get("limit") or 100)

    # фильтры
    type_ = filters.get("type_") or "movie"
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    genre_ids = filters.get("genre_ids") or []
    country = filters.get("country")
    is_animated = filters.get("is_animated")

    genre_id = genre_ids[0] if genre_ids else None

    sort_by = sort.get("by") or "vote_count"
    order = sort.get("order") or "desc"

    # 2. Дёргаем tmdb-sync /movies/search
    resp = await search_movies(
        _type=type_,
        genre_id=genre_id,
        country_code=country,
        year_from=year_from,
        year_to=year_to,
        is_animated=is_animated,
        sort_by=sort_by,
        order=order,
        limit=limit,
        skip=0,
    )
    movies = resp.get("items") or resp.get("results") or []
    size = len(movies)

    # 3. Вычисляем номер версии: max(version)+1
    res = await session.execute(
        select(func.max(CollectionVersion.version)).where(
            CollectionVersion.collection_id == collection.id
        )
    )
    current_max = res.scalar() or 0
    next_version = current_max + 1

    # 4. Создаём CollectionVersion
    version = CollectionVersion(
        collection_id=collection.id,
        version=next_version,
        size=size,
        seed=seed,
        rule=rule,                     # финальное правило для этой версии
        rule_overrides_json=overrides, # что применили поверх base_rule
        status="published",
    )
    session.add(version)
    await session.flush()  # нужен id версии

    # 5. На всякий случай чистим items для этой версии (если вдруг перегенерация)
    await session.execute(
        delete(CollectionItem).where(CollectionItem.version_id == version.id)
    )

    # 6. Наполняем items
    items_to_add = []
    for idx, m in enumerate(movies, start=1):
        ci = CollectionItem(
            version_id=version.id,
            ord=idx,
            tmdb_id=m["id"],
            _type=type_,  # ВАЖНО: именно _type, как в модели
        )
        items_to_add.append(ci)

    session.add_all(items_to_add)

    # 7. Коммит и возврат id версии
    await session.commit()
    return version.id


