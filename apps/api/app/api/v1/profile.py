"""Profile router: GET/PUT /v1/me/profile, DELETE /v1/me."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_profile, get_current_user
from app.db import models
from app.db.session import get_session
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
