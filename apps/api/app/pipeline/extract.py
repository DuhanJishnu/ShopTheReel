"""extract: Gemini vision extraction over sampled frames + cost logging.

CLI: python -m app.pipeline.extract --help
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.vision import ExtractionResult, VisionClient
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.services import reels as reel_service

log = get_logger()


async def run_extract(
    session: AsyncSession, reel: models.Reel, vision: VisionClient, frame_blobs: list[bytes] | None = None,
    store=None,  # type: ignore[no-untyped-def]
) -> ExtractionResult:
    """Run extraction, persist overall style/occasion + costs. Returns the result for crop_merge."""
    await reel_service.write_stage(session, reel.id, "extract", "running")
    if frame_blobs is None:
        assert store is not None, "store required to load frames"
        res = await session.execute(select(models.Frame).where(models.Frame.reel_id == reel.id).order_by(models.Frame.idx))
        frame_blobs = [await store.download_bytes(f.storage_key) for f in res.scalars().all()]
    result = await vision.extract(frame_blobs[:8])
    reel.overall_style = result.overall_style
    reel.occasion = result.occasion_guess
    usage = vision.last_usage
    session.add(models.ReelCost(
        reel_id=reel.id, model=getattr(vision, "_model", vision.name),
        input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
        est_cost_inr=None,  # pricing varies; tokens are the tracked unit (spec NFR-2)
    ))
    await session.flush()
    await reel_service.write_stage(
        session, reel.id, "extract", "done",
        metrics={"items": len(result.items), "backend": vision.name, **usage},
    )
    # Stash raw extraction on the reel row for crop_merge (avoids a temp table in Phase 2).
    reel.error = None
    await session.flush()
    return result


async def _cli(reel_id: str, fake: bool) -> None:
    from app.clients.vision import FakeVision, get_vision_client
    from app.core.deps import get_store

    vision = FakeVision() if fake else get_vision_client()
    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None:
            raise SystemExit(f"reel {reel_id} not found")
        result = await run_extract(session, reel, vision, store=get_store())
        await session.commit()
        print(f"items={len(result.items)} backend={vision.name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract garments from sampled frames.")
    parser.add_argument("--reel-id", required=True, help="Reel id to extract")
    parser.add_argument("--fake", action="store_true", help="Use FakeVision (no Gemini call)")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id, args.fake))


if __name__ == "__main__":
    main()
