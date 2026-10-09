"""ARQ job functions (Phase 2: extraction job; Phase 4: taste updates)."""

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.pipeline.orchestrator import run_pipeline
from app.services.personalisation import apply_taste_update

log = get_logger()


async def process_reel(ctx: dict, reel_id: str) -> dict:
    log.info("job start", job="process_reel", reel_id=reel_id)
    async with SessionLocal() as session:
        reel = await run_pipeline(session, reel_id)
        return {"reel_id": reel_id, "status": reel.status, "cache_hit": reel.cache_hit}


async def update_taste(ctx: dict, feedback_id: str) -> dict:
    log.info("job start", job="update_taste", feedback_id=feedback_id)
    async with SessionLocal() as session:
        await apply_taste_update(session, feedback_id)
        return {"feedback_id": feedback_id}
