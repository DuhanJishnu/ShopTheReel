"""Orchestrator: ingest -> preprocess -> extract -> crop_merge with stage tracking.

CLI: python -m app.pipeline.orchestrator --help
Idempotent: re-running a done reel reuses cache paths; stages are re-written.
"""

import argparse
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embeddings import HashedImageEmbedder
from app.clients.vision import VisionClient, get_vision_client
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.pipeline import crop_merge as cm
from app.pipeline import extract as ex
from app.pipeline import ingest as ing
from app.pipeline import preprocess as pp
from app.services import reels as reel_service

log = get_logger()


async def run_pipeline(
    session: AsyncSession, reel_id: str, vision: VisionClient | None = None, store=None,  # type: ignore[no-untyped-def]
) -> models.Reel:
    from app.core.deps import get_store

    store = store or get_store()
    vision = vision or get_vision_client()
    embedder = HashedImageEmbedder()
    reel = await session.get(models.Reel, reel_id)
    if reel is None:
        raise ValueError(f"reel {reel_id} not found")
    try:
        if not reel.storage_key:
            await reel_service.set_status(session, reel, "needs_media", "no media attached")
            await session.commit()
            return reel
        await reel_service.set_status(session, reel, "queued")
        raw = await store.download_bytes(reel.storage_key)
        if await ing.run_ingest(session, reel, raw):
            await session.commit()
            await reel_service.publish_event(reel.id, {"type": "done", "cache_hit": True})
            return reel
        await reel_service.set_status(session, reel, "preprocessing")
        if await pp.run_preprocess(session, reel, raw, store):
            await session.commit()
            await reel_service.publish_event(reel.id, {"type": "done", "cache_hit": True})
            return reel
        await reel_service.set_status(session, reel, "extracting")
        from sqlalchemy import select as _select

        res = await session.execute(
            _select(models.Frame).where(models.Frame.reel_id == reel.id).order_by(models.Frame.idx))
        blobs = [await store.download_bytes(f.storage_key) for f in res.scalars().all()]
        result = await ex.run_extract(session, reel, vision, frame_blobs=blobs)
        await reel_service.set_status(session, reel, "embedding")
        await cm.run_crop_merge(session, reel, result, blobs, store, embedder)
        await reel_service.set_status(session, reel, "done")
        await session.commit()
        await reel_service.publish_event(reel.id, {"type": "done", "cache_hit": False})
        return reel
    except Exception as exc:
        log.error("pipeline failed", reel_id=reel_id, error=str(exc))
        await reel_service.set_status(session, reel, "failed", str(exc)[:500])
        await session.commit()
        await reel_service.publish_event(reel_id, {"type": "error", "error": str(exc)[:500]})
        raise


async def _cli(reel_id: str, fake: bool) -> None:
    from app.clients.vision import FakeVision, get_vision_client

    vision = FakeVision() if fake else get_vision_client()
    async with SessionLocal() as session:
        reel = await run_pipeline(session, reel_id, vision=vision)
        print(f"status={reel.status} cache_hit={reel.cache_hit}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the full extraction pipeline for a reel.")
    parser.add_argument("--reel-id", required=True, help="Reel id to process")
    parser.add_argument("--fake", action="store_true", help="Use FakeVision (no Gemini call)")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id, args.fake))


if __name__ == "__main__":
    main()
