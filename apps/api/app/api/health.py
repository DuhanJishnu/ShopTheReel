"""Health routers: /healthz (liveness) and /readyz (readiness)."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.deps import get_store
from app.db.session import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    checks: dict[str, bool] = {"db": False, "redis": False, "storage": False}
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        checks["redis"] = True
    except Exception:
        pass
    try:
        checks["storage"] = await get_store().health()
    except Exception:
        pass
    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"status": "not-ready", "checks": checks})  # type: ignore[return-value]
