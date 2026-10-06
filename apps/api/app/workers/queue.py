"""ARQ queue helpers. RedisSettings fields verified against installed arq 0.28."""

from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

_pool: ArqRedis | None = None


def redis_settings(url: str = "") -> RedisSettings:
    parsed = urlparse(url or settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue_process(reel_id: str) -> None:
    pool = await get_pool()
    await pool.enqueue_job("process_reel", reel_id)
