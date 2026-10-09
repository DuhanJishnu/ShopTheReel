"""Profile router: GET/PUT /v1/me/profile, DELETE /v1/me, GET /v1/me/style-dna."""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_profile, get_current_user
from app.db import models
from app.db.session import get_session
from app.db.vectors import as_list
from app.schemas.profile import ProfileIn

router = APIRouter(tags=["me"])


def _to_out(p: models.Profile) -> dict:
    return {
        "user_id": p.user_id,
        "gender": p.gender,
        "sizes": p.sizes,
        "height_cm": p.height_cm,
        "budget_min": p.budget_min,
        "budget_max": p.budget_max,
        "style_tags": p.style_tags or [],
        "disliked_colours": p.disliked_colours or [],
        "preferred_brands": p.preferred_brands or [],
    }


@router.get("/v1/me/profile")
async def get_profile(
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> dict:
    profile = await ensure_profile(session, user.id)
    return _to_out(profile)


@router.put("/v1/me/profile")
async def put_profile(
    body: ProfileIn,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> dict:
    profile = await ensure_profile(session, user.id)
    for field in ("gender", "sizes", "height_cm", "budget_min", "budget_max", "style_tags", "disliked_colours", "preferred_brands"):
        setattr(profile, field, getattr(body, field))
    await session.commit()
    return _to_out(profile)


@router.delete("/v1/me", status_code=204)
async def delete_me(
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> None:
    # Cascade deletes profiles/refresh_tokens/reels via FK; delete user row.
    await session.delete(user)
    await session.commit()
    return None


@router.get("/v1/me/style-dna")
async def style_dna(
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> dict:
    """Aggregate liked/bought feedback into top colours, brands, tags + taste state."""
    res = await session.execute(
        select(models.Feedback, models.Match, models.Product, models.DetectedItem)
        .join(models.Match, models.Feedback.match_id == models.Match.id)
        .join(models.Product, models.Match.product_id == models.Product.id)
        .join(models.DetectedItem, models.Match.item_id == models.DetectedItem.id)
        .where(models.Feedback.user_id == user.id, models.Feedback.signal.in_(["like", "bought"]))
        .order_by(models.Feedback.created_at.desc())
        .limit(50)
    )
    colours: Counter[str] = Counter()
    brands: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    for _, _, product, item in res.all():
        for colour in (product.colours or []) + (item.colours or []):
            colours[colour.lower()] += 1
        brands[(product.brand or "Generic")] += 1
        for tag in (item.style_tags or []):
            tags[tag.lower()] += 1
    profile = await ensure_profile(session, user.id)
    return {
        "top_colours": [c for c, _ in colours.most_common(5)],
        "top_brands": [b for b, _ in brands.most_common(5)],
        "top_tags": [t for t, _ in tags.most_common(5)],
        "taste_trained": as_list(profile.taste_vec) is not None,
    }
