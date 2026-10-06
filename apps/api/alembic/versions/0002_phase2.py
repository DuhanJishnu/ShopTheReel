"""Phase 2 migration: frames, detected_items, reel_costs, idempotency_keys."""

revision = "0002_phase2"
down_revision = "0001_phase1"
branch_labels = None
depends_on = None

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.create_table(
        "frames",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reel_id", sa.String(36), sa.ForeignKey("reels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sharpness", sa.Float(), nullable=True),
    )
    op.create_index("ix_frames_reel_id", "frames", ["reel_id"])
    op.create_table(
        "detected_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reel_id", sa.String(36), sa.ForeignKey("reels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("subcategory", sa.String(128), nullable=False),
        sa.Column("colours", sa.JSON(), nullable=True),
        sa.Column("pattern", sa.String(32), nullable=True),
        sa.Column("fit", sa.String(32), nullable=True),
        sa.Column("material_guess", sa.String(128), nullable=True),
        sa.Column("gender_hint", sa.String(16), nullable=True),
        sa.Column("style_tags", sa.JSON(), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("crop_key", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("attribute_text", sa.Text(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("suggested", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_detected_items_reel_id", "detected_items", ["reel_id"])
    op.create_table(
        "reel_costs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reel_id", sa.String(36), sa.ForeignKey("reels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("est_cost_inr", sa.Float(), nullable=True),
    )
    op.create_index("ix_reel_costs_reel_id", "reel_costs", ["reel_id"])
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("reel_id", sa.String(36), sa.ForeignKey("reels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("reel_costs")
    op.drop_table("detected_items")
    op.drop_table("frames")
