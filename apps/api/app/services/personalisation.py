"""Taste-vector personalisation: EMA toward liked/bought, away from disliked.

LR = {"like": 0.2, "bought": 0.35, "dislike": 0.15, "wrong_item": 0.15}.
wrong_item pushes the taste away like a dislike (the item was a miss).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import models
from app.db.vectors import as_list, ema_step

log = get_logger()
LR = {"like": 0.2, "bought": 0.35, "dislike": 0.15, "wrong_item": 0.15}
AWAY = {"dislike", "wrong_item"}
SIGNALS = {"like", "dislike", "wrong_item", "bought"}


async def record_feedback(session: AsyncSession, user: models.User, match_id: str, signal: str) -> models.Feedback:
    if signal not in SIGNALS:
        raise ValueError(f"signal must be one of {sorted(SIGNALS)}")
    res = await session.execute(
        select(models.Match, models.DetectedItem)
        .join(models.DetectedItem, models.Match.item_id == models.DetectedItem.id)
        .join(models.Reel, models.DetectedItem.reel_id == models.Reel.id)
        .where(models.Match.id == match_id, models.Reel.user_id == user.id)
    )
    row = res.first()
    if row is None:
        raise LookupError("match not found")
    feedback = models.Feedback(user_id=user.id, match_id=match_id, signal=signal)
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def apply_taste_update(session: AsyncSession, feedback_id: str) -> None:
    """ARQ job body: fold one feedback signal into the user's taste vector."""
    feedback = await session.get(models.Feedback, feedback_id)
    if feedback is None:
        return
    match = await session.get(models.Match, feedback.match_id)
    if match is None:
        return
    product = await session.get(models.Product, match.product_id)
    if product is None:
        return
    vec = as_list(product.text_vec)
    if vec is None:
        log.warning("taste update skipped: product has no text vector", product_id=product.id)
        return
    profile = await session.get(models.Profile, feedback.user_id)
    if profile is None:
        profile = models.Profile(user_id=feedback.user_id)
        session.add(profile)
    taste = as_list(profile.taste_vec)
    profile.taste_vec = ema_step(taste, vec, LR[feedback.signal], away=feedback.signal in AWAY)
    profile.taste_updated_at = datetime.now(UTC)
    await session.commit()
    log.info("taste updated", user_id=feedback.user_id, signal=feedback.signal)
