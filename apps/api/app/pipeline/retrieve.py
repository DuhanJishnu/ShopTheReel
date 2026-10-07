"""retrieve: hybrid ANN retrieval + fusion, persist matches (exact tier).

Score (spec 7.2): 0.5*img_sim + 0.35*text_sim + 0.15*attr_match.
Hard filters in SQL; size/colour/price soft filters in Python.
Phase 3 persists the single `exact` tier (ranked); similar/budget land in Phase 4.

CLI: python -m app.pipeline.retrieve --help
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.provider import CandidateQuery, CatalogProvider
from app.catalog.providers.dataset import DatasetProvider
from app.catalog.providers.mock_partner import MockPartnerProvider, fanout
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.services import reels as reel_service

log = get_logger()
SIZE_SLOT = {
    "top": "top", "outerwear": "top", "dress": "top",
    "bottom": "bottom", "footwear": "shoe", "belt": "bottom",
}
TOP_N = 12


def attr_match(item: models.DetectedItem, product: models.Product) -> float:
    hits, total = 0, 0
    if item.colours:
        total += 1
        pcolours = {c.lower() for c in (product.colours or [])}
        if any(c.lower() in pcolours for c in item.colours):
            hits += 1
    if item.pattern and item.pattern != "unknown":
        total += 1
        hits += item.pattern == (product.pattern or "")
    if item.fit and item.fit != "unknown":
        total += 1
        hits += item.fit == (product.fit or "")
    return hits / total if total else 0.5


def size_for(item: models.DetectedItem, profile: models.Profile | None) -> str | None:
    if profile is None or not profile.sizes:
        return None
    return (profile.sizes or {}).get(SIZE_SLOT.get(item.category, ""))


async def run_retrieve(session: AsyncSession, reel: models.Reel) -> int:
    await reel_service.write_stage(session, reel.id, "retrieve", "running")
    profile = await session.get(models.Profile, reel.user_id)
    gender = (profile.gender if profile and profile.gender else "unisex") or "unisex"
    disliked = [c.lower() for c in (profile.disliked_colours if profile and profile.disliked_colours else [])]
    budget_min = profile.budget_min if profile else None
    budget_max = profile.budget_max if profile else None

    dataset = DatasetProvider(session)
    providers: list[CatalogProvider] = [dataset, MockPartnerProvider(dataset)]

    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id))
    items = res.scalars().all()
    total = 0
    for item in items:
        size = size_for(item, profile)
        lo = (budget_min * 0.5) if budget_min else None
        hi = (budget_max * 1.5) if budget_max else None
        gh = item.gender_hint or gender
        if gh == "unknown":
            gh = gender
        query = CandidateQuery(
            categories={item.category}, gender=gh,
            colours=item.colours or [], pattern=item.pattern, size=size,
            budget_min=lo, budget_max=hi, disliked_colours=disliked,
            text_vec=item.text_vec, image_vec=item.embedding, limit=50,
        )
        cands = await fanout(providers, query)
        scored: list[tuple[float, models.Product]] = []
        for cand in cands:
            product = await session.get(models.Product, cand.product_id)
            if product is None:
                continue
            if size and product.sizes_available and size not in product.sizes_available:
                continue
            if disliked and any(c.lower() in disliked for c in (product.colours or [])):
                continue
            if lo is not None and float(product.price) < lo:
                continue
            if hi is not None and float(product.price) > hi:
                continue
            am = attr_match(item, product)
            cand.attr_match = am
            scored.append((cand.fused, product))
        scored.sort(key=lambda s: s[0], reverse=True)
        for rank, (score, product) in enumerate(scored[:TOP_N]):
            session.add(models.Match(item_id=item.id, product_id=product.id, tier="exact",
                                     score=score, reason=None, rank=rank))
            total += 1
    await session.flush()
    await reel_service.write_stage(session, reel.id, "retrieve", "done",
                                   metrics={"matches": total, "items": len(items)})
    return total


async def _cli(reel_id: str) -> None:
    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None:
            raise SystemExit(f"reel {reel_id} not found")
        n = await run_retrieve(session, reel)
        await session.commit()
        print(f"matches={n}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Retrieve candidate products and persist exact matches.")
    parser.add_argument("--reel-id", required=True, help="Reel id to match")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id))


if __name__ == "__main__":
    main()
