import asyncio
import asyncpg
import logging
from app.core.config import PG_DSN


logger = logging.getLogger(__name__)
_pool = None


async def get_pool():
    global _pool
    if _pool is not None:
        return _pool

    last_err = None
    for attempt in range(30):  # до ~30 секунд
        try:
            _pool = await asyncpg.create_pool(dsn=PG_DSN, min_size=1, max_size=10)
            logger.info("Connected to Postgres")
            return _pool
        except Exception as e:
            last_err = e
            logger.warning("Postgres not ready (%s). Retry %d/30...", e, attempt + 1)
            await asyncio.sleep(1)

    logger.error("Failed to connect Postgres after retries: %s", last_err)
    raise last_err
