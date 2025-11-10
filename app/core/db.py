import asyncpg
from app.core.config import PG_DSN


_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=PG_DSN, min_size=1, max_size=10)
    return _pool
