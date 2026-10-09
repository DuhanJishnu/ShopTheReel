"""Phase 1+2 models: users, profiles, refresh_tokens, reels, reel_stages,
frames, detected_items, reel_costs, idempotency_keys.

NOTE: vector columns stay JSON in Phase 2 so unit tests run on SQLite.
Phase 3 alters taste_vec/embedding columns to pgvector with HNSW indexes.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class EmbeddingVector(TypeDecorator):
    """Embedding column: pgvector vector(n) on Postgres, JSON on SQLite.

    Lets unit tests run on SQLite while production/CI use real ANN types.
    ANN queries themselves are Postgres-only (see DatasetProvider).
    """

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return Vector(self.dim)
        return JSON()


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
    text_vec: Mapped[list | None] = mapped_column(EmbeddingVector(768), nullable=True)
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


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(64), default="dataset")
    sku: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    brand: Mapped[str] = mapped_column(String(128), default="Generic")
    category: Mapped[str] = mapped_column(String(32), index=True)
    subcategory: Mapped[str] = mapped_column(String(128), default="")
    gender: Mapped[str] = mapped_column(String(16), default="unisex", index=True)
    colours: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    sizes_available: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    buy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribute_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_vec: Mapped[list | None] = mapped_column(EmbeddingVector(768), nullable=True)
    image_vec: Mapped[list | None] = mapped_column(EmbeddingVector(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("detected_items.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"))
    tier: Mapped[str] = mapped_column(String(16), default="exact")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, default=0)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(String(36), ForeignKey("matches.id", ondelete="CASCADE"))
    signal: Mapped[str] = mapped_column(String(16))  # like | dislike | wrong_item | bought
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Look(Base):
    __tablename__ = "looks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reel_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reels.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(128), default="Untitled look")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    share_slug: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LookItem(Base):
    __tablename__ = "look_items"
    look_id: Mapped[str] = mapped_column(String(36), ForeignKey("looks.id", ondelete="CASCADE"), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(36), ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True)


class Board(Base):
    __tablename__ = "boards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BoardLook(Base):
    __tablename__ = "board_looks"
    board_id: Mapped[str] = mapped_column(String(36), ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    look_id: Mapped[str] = mapped_column(String(36), ForeignKey("looks.id", ondelete="CASCADE"), primary_key=True)
