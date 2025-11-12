from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="ONE_FRAME_FOUR_TITLES")  # запас на другой геймплей
    rule_json: Mapped[dict] = mapped_column(JSON)  # фильтры/сортировки/лимиты по умолчанию
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    versions: Mapped[list["CollectionVersion"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionVersion(Base):
    __tablename__ = "collection_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)  # 1,2,3,...
    size: Mapped[int] = mapped_column(Integer)
    compiled_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)  # для случайностей/перемешиваний
    rule_overrides_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # доп. изменения к базовому правилу
    status: Mapped[str] = mapped_column(String(20), default="published")  # draft|published|archived

    collection: Mapped["Collection"] = relationship(back_populates="versions")
    items: Mapped[list["CollectionItem"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("collection_id", "version", name="uq_collection_version"),)


class CollectionItem(Base):
    __tablename__ = "collection_items"
    version_id: Mapped[int] = mapped_column(ForeignKey("collection_versions.id", ondelete="CASCADE"), primary_key=True)
    ord: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, index=True)
    _type: Mapped[str] = mapped_column(String(10), default="movie")  # movie|tv

    version: Mapped["CollectionVersion"] = relationship(back_populates="items")
