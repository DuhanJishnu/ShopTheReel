"""rerank: personalisation adjustment + rule-based reasons + LLM stub.

Adjusted score (spec 7.2):
  base + 0.15*cos(taste_vec, product_text_vec)
       + 0.05*brand_pref - 0.10*price_over_budget_ratio
Ranks are rewritten per item by adjusted score. Reasons are rule-based and
honest (top contributing factor). LLM_RERANK=true keeps rule order and logs a
warning: the real LLM pass lands with the Phase 5 eval harness (decision).

CLI: python -m app.pipeline.rerank --help
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.db.vectors import as_list, cosine
from app.services import reels as reel_service

log = get_logger()


def brand_pref(product: models.Product, profile: models.Profile | None) -> float:
    if profile is None or not profile.preferred_brands:
        return 0.0
    wanted = {b.lower() for b in profile.preferred_brands}
    return 1.0 if (product.brand or "").lower() in wanted else 0.0


def over_budget_ratio(product: models.Product, profile: models.Profile | None) -> float:
    if profile is None or not profile.budget_max:
        return 0.0
    return max(0.0, (float(product.price) - profile.budget_max) / profile.budget_max)


def reason_for(item: models.DetectedItem, product: models.Product, taste_cos: float,
               brand: float, over: float) -> str:
    if taste_cos > 0.3:
        return "Matches your liked styles"
    if item.colours and any((c or "").lower() in {(p or "").lower() for p in (product.colours or [])}
                            for c in item.colours):
        return f"Same {item.colours[0]} tone as the reel".replace("  ", " ")
    if item.pattern and item.pattern != "unknown" and item.pattern == (product.pattern or ""):
        return f"Same {item.pattern} pattern, similar cut"
    if brand > 0:
        return f"From {product.brand}, one of your brands"
    if over == 0:
        return "Within your budget"
    return "Closest visual match"


async def llm_rerank_stub(item_id: str, ordered_ids: list[str]) -> list[str]:
    """LLM rerank behind LLM_RERANK. Phase 4: flag acknowledged, order kept."""
    if settings.llm_rerank:
        log.warning("LLM_RERANK=true but the LLM pass lands in Phase 5; keeping rule order", item_id=item_id)
    return ordered_ids


async def run_rerank(session: AsyncSession, reel: models.Reel) -> int:
    await reel_service.write_stage(session, reel.id, "rerank", "running")
    profile = await session.get(models.Profile, reel.user_id)
    taste = as_list(profile.taste_vec) if profile else None
    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id))
    n = 0
    for item in res.scalars().all():
        mres = await session.execute(
            select(models.Match, models.Product)
            .join(models.Product, models.Match.product_id == models.Product.id)
            .where(models.Match.item_id == item.id, models.Match.tier == "exact")
        )
        scored: list[tuple[float, models.Match, models.Product]] = []
        for match, product in mres.all():
            tcos = cosine(taste, as_list(product.text_vec) or []) if taste else 0.0
            bp = brand_pref(product, profile)
            over = over_budget_ratio(product, profile)
            adj = match.score + 0.15 * tcos + 0.05 * bp - 0.10 * over
            match.score = round(adj, 4)
            match.reason = reason_for(item, product, tcos, bp, over)
            scored.append((adj, match, product))
        scored.sort(key=lambda s: s[0], reverse=True)
        ordered = await llm_rerank_stub(item.id, [m.id for _, m, _ in scored])
        order = {mid: rank for rank, mid in enumerate(ordered)}
        for _, match, _ in scored:
            match.rank = order[match.id]
            n += 1
    await session.flush()
    await reel_service.write_stage(session, reel.id, "rerank", "done", metrics={"reranked": n})
    return n


async def _cli(reel_id: str) -> None:
    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None:
            raise SystemExit(f"reel {reel_id} not found")
        n = await run_rerank(session, reel)
        await session.commit()
        print(f"reranked={n}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rerank exact matches with personalisation.")
    parser.add_argument("--reel-id", required=True, help="Reel id to rerank")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id))


if __name__ == "__main__":
    main()
