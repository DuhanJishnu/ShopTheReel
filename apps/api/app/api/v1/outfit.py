"""Outfit router: assemble persisted matches into a shoppable outfit (Phase 3: exact tier)."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_store
from app.core.errors import problem
from app.db import models
from app.db.session import get_session

router = APIRouter(prefix="/v1/reels", tags=["outfit"])


def _inr(amount: float) -> str:
    whole = int(round(amount))
    s = str(whole)
    head, tail = (s[:-3], s[-3:]) if len(s) > 3 else ("", s)
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + (",".join(groups + [tail]) if groups else tail)


@router.get("/{reel_id}/outfit")
async def get_outfit(
    reel_id: str, request: Request,
    tier: str = Query(default="exact"),
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
    store=Depends(get_store),  # type: ignore[no-untyped-def]
):
    if tier not in ("exact", "similar", "budget"):
        return problem(request, 422, "Unprocessable", "tier must be exact|similar|budget")
    reel = await session.get(models.Reel, reel_id)
    if reel is None or reel.user_id != user.id:
        return problem(request, 404, "Not Found", "reel not found")
    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id))
    items_out, total = [], 0.0
    for item in res.scalars().all():
        mres = await session.execute(
            select(models.Match, models.Product)
            .join(models.Product, models.Match.product_id == models.Product.id)
            .where(models.Match.item_id == item.id, models.Match.tier == tier)
            .order_by(models.Match.rank)
            .limit(1)
        )
        row = mres.first()
        match = None
        if row is not None:
            match_row, product = row
            total += float(product.price)
            raw_img = product.image_url
            image_url = raw_img
            if raw_img and "://" not in raw_img:
                image_url = await store.presign_get(raw_img)  # storage key, not a public URL
            match = {
                "id": match_row.id,
                "product": {
                    "sku": product.sku, "brand": product.brand, "title": product.title,
                    "price": float(product.price), "price_display": _inr(float(product.price)),
                    "image_url": image_url, "buy_url": product.buy_url,
                },
                "score": match_row.score,
                "match_pct": round(match_row.score * 100),
                "reason": match_row.reason,
            }
        items_out.append({
            "item": {"id": item.id, "category": item.category, "subcategory": item.subcategory,
                     "colours": item.colours or [], "confidence": item.confidence,
                     "crop_url": await store.presign_get(item.crop_key) if item.crop_key else None},
            "match": match, "suggested": item.suggested,
        })
    return {"tier": tier, "items": items_out, "total_price": round(total, 2),
            "total_display": _inr(total), "currency": "INR"}
