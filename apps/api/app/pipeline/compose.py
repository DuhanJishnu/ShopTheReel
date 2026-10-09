"""compose: three tiers per item + outfit totals + complete-the-look.

- exact: top reranked score (persisted by retrieve, adjusted by rerank).
- similar: best candidate with a different brand and score >= 0.6.
- budget: cheapest candidate with score >= 0.75 * exact score.
- complete-the-look: missing bottom/footwear slots get suggested items
  (dress counts as top+bottom) matched on the outfit palette.
Idempotent: similar/budget rows are rebuilt per run.

CLI: python -m app.pipeline.compose --help
"""

import argparse
import asyncio
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.provider import CatalogProvider
from app.catalog.providers.dataset import DatasetProvider
from app.catalog.providers.mock_partner import MockPartnerProvider
from app.clients.embeddings import HashedTextEmbedder
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.db.vectors import as_list
from app.pipeline.retrieve import match_item
from app.services import reels as reel_service

log = get_logger()
BOTTOM_SLOTS = {"bottom", "dress"}


def palette(items: list[models.DetectedItem], k: int = 2) -> list[str]:
    counts: Counter[str] = Counter()
    for item in items:
        for colour in item.colours or []:
            counts[colour.lower()] += 1
    return [c for c, _ in counts.most_common(k)] or ["neutral"]


async def tier_rows(session: AsyncSession, item: models.DetectedItem) -> dict[str, models.Match | None]:
    """Pick similar/budget from exact matches; persist tier rows. Returns picks."""
    await session.execute(
        delete(models.Match).where(models.Match.item_id == item.id, models.Match.tier.in_(["similar", "budget"])))
    res = await session.execute(
        select(models.Match, models.Product)
        .join(models.Product, models.Match.product_id == models.Product.id)
        .where(models.Match.item_id == item.id, models.Match.tier == "exact")
        .order_by(models.Match.rank)
    )
    rows = res.all()
    if not rows:
        return {"exact": None, "similar": None, "budget": None}
    exact_match, exact_product = rows[0][0], rows[0][1]
    exact_brand = (exact_product.brand or "").lower()
    similar = next((m for m, p in rows[1:]
                    if (p.brand or "").lower() != exact_brand and m.score >= 0.6), None)
    eligible = [(m, p) for m, p in rows[1:] if m.score >= 0.75 * exact_match.score]
    # Budget falls back to the exact pick so tier totals never invert.
    budget = min(eligible + [(exact_match, exact_product)], key=lambda mp: float(mp[1].price))[0]
    picks: dict[str, models.Match | None] = {"exact": exact_match, "similar": None, "budget": None}
    for tier, pick in (("similar", similar), ("budget", budget)):
        if pick is None:
            continue
        prod = next(p for m, p in rows if m.id == pick.id)
        session.add(models.Match(item_id=item.id, product_id=prod.id, tier=tier,
                                 score=pick.score, reason=pick.reason, rank=0))
        picks[tier] = pick
    await session.flush()
    return picks


async def complete_look(session: AsyncSession, reel: models.Reel, items: list[models.DetectedItem]) -> int:
    """Add suggested bottom/footwear items (with matches) when slots are missing."""
    await session.execute(delete(models.DetectedItem).where(
        models.DetectedItem.reel_id == reel.id, models.DetectedItem.suggested.is_(True)))
    present = {i.category for i in items if not i.suggested}
    need = []
    if not (present & BOTTOM_SLOTS):
        need.append("bottom")
    if "footwear" not in present:
        need.append("footwear")
    if not need:
        return 0
    profile = await session.get(models.Profile, reel.user_id)
    gender = (profile.gender if profile and profile.gender else "unisex") or "unisex"
    colours = palette(items)
    style = " ".join((reel.overall_style or [])[:3])
    text_emb = HashedTextEmbedder()
    img_vecs = [as_list(i.embedding) for i in items]
    img_vecs = [v for v in img_vecs if v and len(v) == 512]
    mean_img = [sum(col) / len(img_vecs) for col in zip(*img_vecs)] if img_vecs else None
    dataset = DatasetProvider(session)
    providers: list[CatalogProvider] = [dataset, MockPartnerProvider(dataset)]
    added = 0
    for slot in need:
        item = models.DetectedItem(
            reel_id=reel.id, category=slot, subcategory=f"suggested {slot}",
            colours=colours, pattern="unknown", fit="unknown", confidence=0.0,
            attribute_text=f"{' '.join(colours)} {slot} {style}".strip(),
            text_vec=text_emb.embed_text(f"{' '.join(colours)} {slot} {style}"),
            embedding=mean_img, suggested=True,
        )
        session.add(item)
        await session.flush()
        if mean_img is not None:
            scored = await match_item(session, item, profile, providers, gender)
            for rank, (score, product) in enumerate(scored[:3]):
                session.add(models.Match(item_id=item.id, product_id=product.id, tier="exact",
                                         score=score, reason="Suggested to complete the look", rank=rank))
        added += 1
    await session.flush()
    return added


async def run_compose(session: AsyncSession, reel: models.Reel) -> dict:
    await reel_service.write_stage(session, reel.id, "compose", "running")
    res = await session.execute(
        select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id,
                                          models.DetectedItem.suggested.is_(False)))
    items = list(res.scalars().all())
    suggested = await complete_look(session, reel, items)
    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id))
    totals: dict[str, float] = {}
    for item in res.scalars().all():
        picks = await tier_rows(session, item)
        for tier, pick in picks.items():
            if pick is None:
                continue
            prod = await session.get(models.Product, pick.product_id)
            if prod is not None:
                totals[tier] = totals.get(tier, 0.0) + float(prod.price)
    await session.flush()
    await reel_service.write_stage(session, reel.id, "compose", "done",
                                   metrics={"totals": totals, "suggested_slots": suggested})
    return {"totals": totals, "suggested_slots": suggested}


async def _cli(reel_id: str) -> None:
    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None:
            raise SystemExit(f"reel {reel_id} not found")
        out = await run_compose(session, reel)
        await session.commit()
        print(f"totals={out['totals']} suggested={out['suggested_slots']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compose three-tier outfits and complete the look.")
    parser.add_argument("--reel-id", required=True, help="Reel id to compose")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id))


if __name__ == "__main__":
    main()
