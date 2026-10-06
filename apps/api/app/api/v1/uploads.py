"""Uploads router: POST /v1/uploads/presign."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.clients.storage import ALLOWED_CONTENT_TYPES, new_storage_key, presign_expiry
from app.core.config import settings
from app.core.deps import get_current_user, get_store
from app.core.errors import problem
from app.db import models
from app.schemas.uploads import PresignIn

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


@router.post("/presign", response_model=None)
async def presign(
    body: PresignIn,
    request: Request,
    user: models.User = Depends(get_current_user),
    store=Depends(get_store),  # type: ignore[no-untyped-def]
) -> dict | JSONResponse:
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        return problem(request, 415, "Unsupported Media Type", f"content_type must be one of {sorted(ALLOWED_CONTENT_TYPES)}")
    max_bytes = settings.max_video_mb * 1024 * 1024
    if body.size_bytes > max_bytes:
        return problem(request, 413, "Payload Too Large", f"size_bytes exceeds {settings.max_video_mb} MB cap")
    key = new_storage_key(body.kind, body.content_type)
    url = await store.presign_put(key, body.content_type)
    return {"upload_url": url, "storage_key": key, "expires_at": presign_expiry()}
