from __future__ import annotations
from typing import Any, Dict, Optional
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.collection_models import Collection, CollectionVersion, CollectionItem
from app.services.tmdb_sync_client import search_movies
import math


DEFAULT_RULE: Dict[str, Any] = {
    "filters": {
        "type_": "movie",     # movie|tv
        "year_from": None,
        "year_to": None,
        "genre_ids": [],      # список id
        "country": None,
        "is_animated": None,
    },
    "sort": {
        "by": "vote_count",
        "order": "desc",
    },
    "limit": 100,
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
    """Аккуратно совмещаем базовое правило и overrides (filters/sort/limit)."""
    if not overrides:
        return base

    out = {**base}

    bf = base.get("filters", {}) or {}
    of = overrides.get("filters", {}) or {}
    out["filters"] = {**bf, **of}

    bs = base.get("sort", {}) or {}
    os_ = overrides.get("sort", {}) or {}
    out["sort"] = {**bs, **os_}

    if "limit" in overrides and overrides["limit"]:
        out["limit"] = overrides["limit"]

    return out


async def compute_next_version(session: AsyncSession, collection_id: int) -> int:
    row = await session.execute(
        select(func.max(CollectionVersion.version)).where(
            CollectionVersion.collection_id == collection_id
        )
    )
    v = row.scalar_one_or_none()
    return 1 if v is None else v + 1


async def materialize_collection(
    session: AsyncSession,
    collection: Collection,
    overrides: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> int:
    """
    Создаём новую версию коллекции и наполняем collection_items.
    Возвращаем PK версии (CollectionVersion.id).
    """

    # 1. Базовое правило: из коллекции или дефолт
    base_rule: Dict[str, Any] = collection.rule_json or DEFAULT_RULE
    rule = merge_rules(base_rule, overrides)

    filters: Dict[str, Any] = rule.get("filters") or {}
    sort: Dict[str, Any] = rule.get("sort") or {}
    limit: int = int(rule.get("limit") or 100)

    # --- НОРМАЛИЗАЦИЯ ФИЛЬТРОВ ОТ СВЭГГЕРА ---

    # type_ — оставляем как есть, но по умолчанию movie
    type_ = filters.get("type_") or "movie"

    year_from = filters.get("year_from")
    year_to = filters.get("year_to")

    # genre_ids могут прилететь как:
    # - None
    # - 0
    # - [0]
    # - int
    # - [int, int, ...]
    genre_ids = filters.get("genre_ids")

    if isinstance(genre_ids, int):
        # если 0 — считаем "нет фильтра", иначе заворачиваем в список
        genre_ids = [] if genre_ids == 0 else [genre_ids]
    elif genre_ids in (None, 0, [0]):
        genre_ids = []
    elif isinstance(genre_ids, list):
        # выкидываем нули и неинты
        genre_ids = [g for g in genre_ids if isinstance(g, int) and g != 0]
    else:
        # всё остальное — в помойку
        genre_ids = []

    # country может прилететь как "string" из примера
    country = filters.get("country")
    if isinstance(country, str):
        if country.strip() == "" or country.strip().lower() in {"string", "country"}:
            country = None

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

    # tmdb-sync отдаёт {"items": [...]}
    raw_items = resp.get("items") if isinstance(resp, dict) else resp
    movies = raw_items or []
    size = len(movies)

    # 3. Номер логической версии
    next_version = await compute_next_version(session, collection.id)

    # 4. Создаём запись версии
    version = CollectionVersion(
        collection_id=collection.id,
        version=next_version,
        size=size,
        seed=seed,
        # сохраняем фактически использованное правило,
        # чтобы потом было понятно, по чему собрали
        rule=rule,
        rule_overrides_json=overrides or {},
        status="published",
    )
    session.add(version)
    await session.flush()  # нужен version.id (PK)

    # 5. На всякий случай чистим items для этой версии
    await session.execute(
        delete(CollectionItem).where(CollectionItem.version_id == version.id)
    )

    # 6. Наполняем items, если есть фильмы
    items_to_add: list[CollectionItem] = []
    for idx, m in enumerate(movies, start=1):
        ci = CollectionItem(
            version_id=version.id,  # ВАЖНО: именно PK версии
            ord=idx,
            tmdb_id=m["id"],
            _type=type_,
        )
        items_to_add.append(ci)

    if items_to_add:
        session.add_all(items_to_add)

    # на всякий случай синхронизируем size с фактическим количеством
    version.size = len(items_to_add)

    await session.commit()
    await session.refresh(version)
    return version.id
