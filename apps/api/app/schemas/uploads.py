"""Pydantic v2 schemas for uploads."""

from typing import Literal

from pydantic import BaseModel, Field


class PresignIn(BaseModel):
    content_type: str
    size_bytes: int = Field(ge=1)
    kind: Literal["video", "image"] = "video"


class PresignOut(BaseModel):
    upload_url: str
    storage_key: str
    expires_at: str
