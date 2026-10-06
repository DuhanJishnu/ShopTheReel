"""ARQ job functions (Phase 2: single extraction job)."""

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.pipeline.orchestrator import run_pipeline

log = get_logger()


async def process_reel(ctx: dict, reel_id: str) -> dict:
    log.info("job start", job="process_reel", reel_id=reel_id)
    async with SessionLocal() as session:
        reel = await run_pipeline(session, reel_id)
        return {"reel_id": reel_id, "status": reel.status, "cache_hit": reel.cache_hit}
