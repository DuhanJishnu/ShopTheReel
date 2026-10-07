"""Phase 1+2 models: users, profiles, refresh_tokens, reels, reel_stages,
frames, detected_items, reel_costs, idempotency_keys.

NOTE: vector columns stay JSON in Phase 2 so unit tests run on SQLite.
Phase 3 alters taste_vec/embedding columns to pgvector with HNSW indexes.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # None for Google-only accounts
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sizes: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(nullable=True)
    budget_min: Mapped[float | None] = mapped_column(nullable=True)
    budget_max: Mapped[float | None] = mapped_column(nullable=True)
    style_tags: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    disliked_colours: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    preferred_brands: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    taste_vec: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    taste_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Reel(Base):
    __tablename__ = "reels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="video")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="needs_media")
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_s: Mapped[float | None] = mapped_column(nullable=True)
    overall_style: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    occasion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ReelStage(Base):
    __tablename__ = "reel_stages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reel_id: Mapped[str] = mapped_column(String(36), ForeignKey("reels.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)


class Frame(Base):
    __tablename__ = "frames"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reel_id: Mapped[str] = mapped_column(String(36), ForeignKey("reels.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column()
    storage_key: Mapped[str] = mapped_column(Text)
    sharpness: Mapped[float | None] = mapped_column(nullable=True)


class DetectedItem(Base):
    __tablename__ = "detected_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reel_id: Mapped[str] = mapped_column(String(36), ForeignKey("reels.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    subcategory: Mapped[str] = mapped_column(String(128), default="")
    colours: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    material_guess: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gender_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    style_tags: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    crop_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    attribute_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )  # Phase 2: hashed 512-d JSON; Phase 3: pgvector image_vec
    suggested: Mapped[bool] = mapped_column(Boolean, default=False)


class ReelCost(Base):
    __tablename__ = "reel_costs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reel_id: Mapped[str] = mapped_column(String(36), ForeignKey("reels.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(128))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    est_cost_inr: Mapped[float | None] = mapped_column(nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reel_id: Mapped[str] = mapped_column(String(36), ForeignKey("reels.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
