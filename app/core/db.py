import asyncio
import asyncpg
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import PG_DSN  # из env: postgresql://user:pass@host:5432/db


logger = logging.getLogger(__name__)


_pool = None
_engine = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _to_async_url(dsn: str) -> str:
    # превращаем postgresql://... -> postgresql+asyncpg://...
    return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)


# ---------- asyncpg-пул (как было) ----------
async def get_pool():
    global _pool
    if _pool is not None:
        return _pool

    last_err = None
    for attempt in range(30):
        try:
            _pool = await asyncpg.create_pool(dsn=PG_DSN, min_size=1, max_size=10)
            logger.info("Connected to Postgres (asyncpg pool)")
            return _pool
        except Exception as e:
            last_err = e
            logger.warning("Postgres not ready (%s). Retry %d/30...", e, attempt + 1)
            await asyncio.sleep(1)

    logger.error("Failed to connect Postgres after retries: %s", last_err)
    raise last_err


# ---------- SQLAlchemy AsyncSession ----------
def init_engine_if_needed():
    """Инициализация движка/фабрики сессий один раз (лениво)."""
    global _engine, _SessionLocal
    if _engine is not None and _SessionLocal is not None:
        return

    async_url = _to_async_url(PG_DSN)
    _engine = create_async_engine(
        async_url,
        pool_pre_ping=True,
        future=True,
    )
    _SessionLocal = async_sessionmaker(
        _engine, expire_on_commit=False, autoflush=False
    )
    logger.info("SQLAlchemy async engine initialized")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: выдаёт AsyncSession и корректно закрывает её."""
    if _SessionLocal is None:
        init_engine_if_needed()
    assert _SessionLocal is not None  # для type-checker
    async with _SessionLocal() as session:
        yield session
