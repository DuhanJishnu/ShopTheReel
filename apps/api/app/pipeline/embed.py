"""embed: fill per-item text vectors (image vectors come from crop_merge).

CLI: python -m app.pipeline.embed --help
Phase 3 uses hashed text vectors; the Gemini TextEmbedder slots into
TextEmbedder without touching this stage.
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embeddings import HashedTextEmbedder, TextEmbedder
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.services import reels as reel_service

log = get_logger()


async def run_embed(session: AsyncSession, reel: models.Reel, embedder: TextEmbedder | None = None) -> int:
    embedder = embedder or HashedTextEmbedder()
    await reel_service.write_stage(session, reel.id, "embed", "running")
    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id))
    n = 0
    for item in res.scalars().all():
        if item.text_vec is None:
            item.text_vec = embedder.embed_text(item.attribute_text or item.subcategory or item.category)
            n += 1
    await session.flush()
    await reel_service.write_stage(session, reel.id, "embed", "done", metrics={"vectors": n, "dim": embedder.dim})
    return n


async def _cli(reel_id: str) -> None:
    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None:
            raise SystemExit(f"reel {reel_id} not found")
        n = await run_embed(session, reel)
        await session.commit()
        print(f"vectors={n}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fill per-item text embedding vectors.")
    parser.add_argument("--reel-id", required=True, help="Reel id to embed")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id))


if __name__ == "__main__":
    main()
