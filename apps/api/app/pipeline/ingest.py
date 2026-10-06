"""ingest: hash raw bytes, exact-match cache check. CLI: python -m app.pipeline.ingest --help."""

import argparse
import asyncio
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.services import reels as reel_service

log = get_logger()

ALLOWED_KINDS = {"video", "images"}


async def run_ingest(session: AsyncSession, reel: models.Reel, raw: bytes) -> bool:
    """Hash bytes and check the exact-match cache. Returns True on cache hit."""
    max_bytes = 100 * 1024 * 1024
    if len(raw) > max_bytes:
        raise ValueError(f"media exceeds 100 MB cap ({len(raw)} bytes)")
    digest = hashlib.sha256(raw).hexdigest()
    reel.sha256 = digest
    await reel_service.write_stage(session, reel.id, "ingest", "running")
    res = await session.execute(
        select(models.Reel).where(
            models.Reel.sha256 == digest, models.Reel.status == "done", models.Reel.id != reel.id
        )
    )
    src = res.scalars().first()
    if src is not None:
        n = await reel_service.copy_results(session, src, reel)
        await reel_service.write_stage(session, reel.id, "ingest", "done", metrics={"cache_hit": True, "copied_items": n})
        log.info("ingest cache hit", reel_id=reel.id, src=src.id, items=n)
        return True
    await reel_service.write_stage(session, reel.id, "ingest", "done", metrics={"cache_hit": False, "sha256": digest[:12]})
    return False


async def _cli(reel_id: str) -> None:
    from app.core.deps import get_store

    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None or not reel.storage_key:
            raise SystemExit(f"reel {reel_id} not found or has no storage_key")
        raw = await get_store().download_bytes(reel.storage_key)
        hit = await run_ingest(session, reel, raw)
        await session.commit()
        print(f"cache_hit={hit} sha256={reel.sha256}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Hash media bytes and check the dedupe cache.")
    parser.add_argument("--reel-id", required=True, help="Reel id whose storage_key is hashed")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id))


if __name__ == "__main__":
    main()
