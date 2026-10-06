"""Reel business logic + stage/event helpers shared by API and pipeline."""

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db import models

log = get_logger()


async def publish_event(reel_id: str, payload: dict) -> None:
    """Best-effort publish to Redis channel reel:{id} (no-op when Redis is down)."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.publish(f"reel:{reel_id}", json.dumps(payload))
        await client.aclose()
    except Exception as exc:
        log.warning("event publish failed", reel_id=reel_id, error=str(exc))


async def set_status(session: AsyncSession, reel: models.Reel, status: str, error: str | None = None) -> None:
    reel.status = status
    reel.error = error
    await session.flush()
    await publish_event(reel.id, {"type": "status", "status": status, "reel_id": reel.id})


async def write_stage(
    session: AsyncSession, reel_id: str, stage: str, status: str,
    error: str | None = None, metrics: dict | None = None,
) -> None:
    now = datetime.now(UTC)
    res = await session.execute(
        select(models.ReelStage).where(models.ReelStage.reel_id == reel_id, models.ReelStage.stage == stage)
    )
    row = res.scalars().first()
    if row is None:
        row = models.ReelStage(reel_id=reel_id, stage=stage, status=status, started_at=now)
        session.add(row)
    row.status = status
    if status == "running" and row.started_at is None:
        row.started_at = now
    if status in ("done", "failed"):
        row.ended_at = now
    row.error = error
    row.metrics = metrics
    await session.flush()
    await publish_event(reel_id, {"type": "stage", "stage": stage, "status": status, "metrics": metrics or {}})


async def copy_results(session: AsyncSession, src: models.Reel, dst: models.Reel) -> int:
    """Copy a finished reel's items/style onto a duplicate (cache hit)."""
    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == src.id))
    count = 0
    for item in res.scalars().all():
        session.add(
            models.DetectedItem(
                reel_id=dst.id, category=item.category, subcategory=item.subcategory,
                colours=item.colours, pattern=item.pattern, fit=item.fit,
                material_guess=item.material_guess, gender_hint=item.gender_hint,
                style_tags=item.style_tags, bbox=item.bbox, crop_key=item.crop_key,
                confidence=item.confidence, attribute_text=item.attribute_text,
                embedding=item.embedding, suggested=item.suggested,
            )
        )
        count += 1
    dst.overall_style = src.overall_style
    dst.occasion = src.occasion
    dst.cache_hit = True
    dst.status = "done"
    await session.flush()
    return count
