"""Pydantic v2 schemas for reels (Phase 2)."""

from typing import Literal

from pydantic import BaseModel, Field

ReelKind = Literal["video", "images", "link"]


class ReelCreateIn(BaseModel):
    kind: ReelKind
    storage_keys: list[str] = Field(default_factory=list)
    source_url: str | None = None


class ReelOut(BaseModel):
    id: str
    status: str
    kind: str
    cache_hit: bool = False


class ReelStatusOut(BaseModel):
    id: str
    status: str
    kind: str
    cache_hit: bool
    overall_style: list[str] | None = None
    occasion: str | None = None
    stages: list[dict] = Field(default_factory=list)
    error: str | None = None


class DetectedItemOut(BaseModel):
    id: str
    category: str
    subcategory: str
    colours: list[str] = Field(default_factory=list)
    pattern: str | None = None
    fit: str | None = None
    confidence: float
    crop_url: str | None = None
