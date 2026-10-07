"""Phase 3 migration: products + matches with HNSW indexes, detected_items.text_vec."""

revision = "0004_phase3"
down_revision = "0003_google"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("sku", sa.String(128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("subcategory", sa.String(128), nullable=False),
        sa.Column("gender", sa.String(16), nullable=False),
        sa.Column("colours", sa.JSON(), nullable=True),
        sa.Column("pattern", sa.String(32), nullable=True),
        sa.Column("fit", sa.String(32), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("sizes_available", sa.JSON(), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("buy_url", sa.Text(), nullable=True),
        sa.Column("attribute_text", sa.Text(), nullable=True),
        sa.Column("text_vec", Vector(768), nullable=True),
        sa.Column("image_vec", Vector(512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "sku", name="uq_products_provider_sku"),
    )
    op.execute("CREATE INDEX ix_products_text_vec ON products USING hnsw (text_vec vector_cosine_ops)")
    op.execute("CREATE INDEX ix_products_image_vec ON products USING hnsw (image_vec vector_cosine_ops)")
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_gender", "products", ["gender"])
    op.create_index("ix_products_in_stock", "products", ["in_stock"])
    op.create_table(
        "matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("detected_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
    )
    op.create_index("ix_matches_item_id", "matches", ["item_id"])
    op.add_column("detected_items", sa.Column("text_vec", Vector(768), nullable=True))


def downgrade() -> None:
    op.drop_column("detected_items", "text_vec")
    op.drop_table("matches")
    op.drop_table("products")
