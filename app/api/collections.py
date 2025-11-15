from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, AliasChoices, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slugify import slugify


from app.core.db import get_session
from app.models.collection_models import Collection, CollectionVersion, CollectionItem
from app.services.collections import materialize_collection, DEFAULT_RULE


router = APIRouter(prefix="/collections", tags=["collections"])


class FiltersIn(BaseModel):
    # принимаем и "_type", и "type", а наружу сериализуем как "_type"
    type_: str = Field(
        default="movie",
        pattern="^(movie|tv)$",
        validation_alias=AliasChoices("_type", "type"),
        serialization_alias="_type",
    )
    year_from: int | None = None
    year_to: int | None = None
    genre_ids: list[int] | int | None = None
    country: str | None = None
    is_animated: bool | None = None

    model_config = ConfigDict(populate_by_name=True)


class RuleIn(BaseModel):
    filters: FiltersIn = Field(default_factory=FiltersIn)
    sort: dict = Field(default={"by":"vote_count","order":"desc"})  # by: vote_count|popularity|release_date
    limit: int = Field(default=100, ge=1, le=5000)


class CollectionCreateIn(BaseModel):
    name: str = Field(..., max_length=200)
    slug: str | None = None
    description: str | None = None
    type: str = Field(default="ONE_FRAME_FOUR_TITLES")
    rule: RuleIn = Field(default_factory=RuleIn)


@router.post("")
async def create_collection(payload: CollectionCreateIn, session: AsyncSession = Depends(get_session)):
    # slug
    slug = payload.slug or slugify(payload.name)
    exists = (await session.execute(select(Collection).where(Collection.slug == slug))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "slug already exists")

    c = Collection(
        name=payload.name,
        slug=slug,
        description=payload.description,
        type=payload.type,
        rule_json=payload.rule.model_dump(),
    )
    session.add(c)
    await session.commit()
    return {"id": c.id, "slug": c.slug}


class CompileIn(BaseModel):
    overrides: dict | None = None
    seed: int | None = None


@router.post("/{collection_id}/compile")
async def compile_collection(collection_id: int, body: CompileIn, session: AsyncSession = Depends(get_session)):
    c = (await session.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "collection not found")
    vid = await materialize_collection(session, c, overrides=body.overrides, seed=body.seed)
    return {"collection_id": c.id, "version_id": vid}


@router.get("/{collection_id}")
async def get_collection(collection_id: int, session: AsyncSession = Depends(get_session)):
    c = (await session.execute(select(Collection).where(Collection.id == collection_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "collection not found")
    return {
        "id": c.id, "name": c.name, "slug": c.slug, "type": c.type,
        "rule": c.rule_json, "created_at": c.created_at, "updated_at": c.updated_at
    }


@router.get("/{collection_id}/versions")
async def list_versions(collection_id: int, session: AsyncSession = Depends(get_session)):
    rows = await session.execute(
        select(CollectionVersion)
        .where(CollectionVersion.collection_id == collection_id)
        .order_by(CollectionVersion.version)
    )
    versions = rows.scalars().all()
    return [{"id": v.id, "version": v.version, "size": v.size, "status": v.status} for v in versions]


@router.get("/{collection_id}/versions/latest")
async def get_latest_version(collection_id: int, session: AsyncSession = Depends(get_session)):
    row = await session.execute(
        select(CollectionVersion)
        .where(CollectionVersion.collection_id == collection_id)
        .where(CollectionVersion.status == "published")
        .order_by(CollectionVersion.version.desc())
        .limit(1)
    )
    v = row.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "No versions for this collection")
    return {"id": v.id, "version": v.version, "size": v.size}


@router.get("/{collection_id}/versions/{version}")
async def get_version(collection_id: int, version: int, session: AsyncSession = Depends(get_session)):
    v = await session.scalar(
        select(CollectionVersion).where(
            CollectionVersion.version == version,
            CollectionVersion.collection_id == collection_id
        )
    )
    if not v:
        raise HTTPException(404, "Version not found for this collection")
    return {"id": v.id, "version": v.version, "size": v.size}


@router.get("/{collection_id}/versions/{version}/items")
async def get_version_items(
    collection_id: int,
    version: int,
    session: AsyncSession = Depends(get_session),
):
    # 1. валидируем, что такая версия у коллекции есть
    v = await session.scalar(
        select(CollectionVersion).where(
            CollectionVersion.collection_id == collection_id,
            CollectionVersion.version == version,
        )
    )
    if not v:
        raise HTTPException(404, "Version not found for this collection")

    # 2. берём items по PK версии (v.id), а не по номеру версии
    rows = await session.execute(
        select(CollectionItem)
        .where(CollectionItem.version_id == v.id)
        .order_by(CollectionItem.ord)
    )
    items = rows.scalars().all()

    return {
        "collection_id": collection_id,
        "version": version,
        "version_id": v.id,  # на всякий случай отдаём и PK
        "size": v.size,
        "items": [
            {"ord": i.ord, "tmdb_id": i.tmdb_id, "_type": i._type}
            for i in items
        ],
    }
