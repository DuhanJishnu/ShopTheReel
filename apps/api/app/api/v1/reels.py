"""Reels router: create (idempotent) / status / items / history / retry / SSE events."""

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_store
from app.core.errors import problem
from app.db import models
from app.db.session import get_session
from app.schemas.reels import ReelCreateIn
from app.services import reels as reel_service
from app.workers import queue

router = APIRouter(prefix="/v1/reels", tags=["reels"])


@router.post("", status_code=202)
async def create_reel(
    body: ReelCreateIn,
    request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    idem = request.headers.get("Idempotency-Key")
    if idem:
        res = await session.execute(
            select(models.IdempotencyKey).where(
                models.IdempotencyKey.key == idem, models.IdempotencyKey.user_id == user.id))
        existing = res.scalars().first()
        if existing is not None:
            reel = await session.get(models.Reel, existing.reel_id)
            if reel is not None:
                return {"id": reel.id, "status": reel.status}
    if body.kind == "link" and not body.storage_keys:
        if not body.source_url:
            return problem(request, 422, "Unprocessable", "link reels need source_url")
        reel = models.Reel(user_id=user.id, kind="link", source_url=body.source_url, status="needs_media")
    else:
        if not body.storage_keys:
            return problem(request, 422, "Unprocessable", "video/images reels need storage_keys")
        reel = models.Reel(
            user_id=user.id, kind=body.kind, storage_key=body.storage_keys[0],
            source_url=body.source_url, status="queued",
        )
    session.add(reel)
    await session.flush()
    if idem:
        session.add(models.IdempotencyKey(key=idem, user_id=user.id, reel_id=reel.id))
    await reel_service.write_stage(session, reel.id, "ingest", "pending")
    await session.commit()
    if reel.status == "queued":
        await queue.enqueue_process(reel.id)
    return {"id": reel.id, "status": reel.status}


async def _owned(session: AsyncSession, user_id: str, reel_id: str) -> models.Reel | None:
    reel = await session.get(models.Reel, reel_id)
    return reel if reel is not None and reel.user_id == user_id else None


@router.get("/{reel_id}")
async def get_reel(
    reel_id: str, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    reel = await _owned(session, user.id, reel_id)
    if reel is None:
        return problem(request, 404, "Not Found", "reel not found")  # type: ignore[return-value]
    res = await session.execute(select(models.ReelStage).where(models.ReelStage.reel_id == reel.id))
    stages = [
        {"stage": s.stage, "status": s.status, "error": s.error, "metrics": s.metrics or {}}
        for s in res.scalars().all()
    ]
    return {
        "id": reel.id, "status": reel.status, "kind": reel.kind, "cache_hit": reel.cache_hit,
        "overall_style": reel.overall_style, "occasion": reel.occasion,
        "stages": stages, "error": reel.error,
    }


@router.get("/{reel_id}/items")
async def get_items(
    reel_id: str, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
    store=Depends(get_store),  # type: ignore[no-untyped-def]
):
    reel = await _owned(session, user.id, reel_id)
    if reel is None:
        return problem(request, 404, "Not Found", "reel not found")
    res = await session.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == reel.id))
    out = []
    for item in res.scalars().all():
        out.append({
            "id": item.id, "category": item.category, "subcategory": item.subcategory,
            "colours": item.colours or [], "pattern": item.pattern, "fit": item.fit,
            "confidence": item.confidence,
            "crop_url": await store.presign_get(item.crop_key) if item.crop_key else None,
        })
    return out


@router.get("")
async def list_reels(
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    q = select(models.Reel).where(models.Reel.user_id == user.id).order_by(models.Reel.created_at.desc())
    if cursor:
        anchor = await session.get(models.Reel, cursor)
        if anchor is not None and anchor.user_id == user.id:
            q = q.where(models.Reel.created_at < anchor.created_at)
    res = await session.execute(q.limit(limit + 1))
    rows = list(res.scalars().all())
    next_cursor = rows[-1].id if len(rows) > limit else None
    return {
        "items": [{"id": r.id, "status": r.status, "kind": r.kind, "created_at": r.created_at.isoformat()} for r in rows[:limit]],
        "next_cursor": next_cursor,
    }


@router.post("/{reel_id}/retry", status_code=202)
async def retry_reel(
    reel_id: str, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    reel = await _owned(session, user.id, reel_id)
    if reel is None:
        return problem(request, 404, "Not Found", "reel not found")  # type: ignore[return-value]
    if reel.status not in ("failed", "partial"):
        return problem(request, 409, "Conflict", f"reel is {reel.status}, nothing to retry")  # type: ignore[return-value]
    await reel_service.set_status(session, reel, "queued", None)
    await session.commit()
    await queue.enqueue_process(reel.id)
    return {"id": reel.id, "status": reel.status}


@router.get("/{reel_id}/events")
async def reel_events(
    reel_id: str, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> StreamingResponse:
    reel = await _owned(session, user.id, reel_id)
    if reel is None:
        async def _nf():  # type: ignore[no-untyped-def]
            yield "event: error\ndata: {\"detail\": \"not found\"}\n\n"
        return StreamingResponse(_nf(), media_type="text/event-stream", status_code=404)

    async def _gen():  # type: ignore[no-untyped-def]
        yield f"data: {json.dumps({'type': 'status', 'status': reel.status})}\n\n"
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            pubsub = client.pubsub()
            await pubsub.subscribe(f"reel:{reel_id}")
            try:
                async for msg in pubsub.listen():
                    if msg["type"] != "message":
                        continue
                    data = msg["data"]
                    payload = data.decode() if isinstance(data, bytes) else str(data)
                    yield f"data: {payload}\n\n"
                    if '"done"' in payload or '"error"' in payload:
                        break
            finally:
                await pubsub.unsubscribe(f"reel:{reel_id}")
                await client.aclose()
        except Exception:
            return
        for _ in range(900):  # fallback heartbeat handled client-side by polling
            await asyncio.sleep(30)
            yield ": ping\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
