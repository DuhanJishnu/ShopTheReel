"""Phase 4 migration: feedback, looks, look_items, boards, board_looks."""

revision = "0005_phase4"
down_revision = "0004_phase3"
branch_labels = None
depends_on = None

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_table(
        "looks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reel_id", sa.String(36), sa.ForeignKey("reels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("share_slug", sa.String(32), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_looks_user_id", "looks", ["user_id"])
    op.create_table(
        "look_items",
        sa.Column("look_id", sa.String(36), sa.ForeignKey("looks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "boards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_boards_user_id", "boards", ["user_id"])
    op.create_table(
        "board_looks",
        sa.Column("board_id", sa.String(36), sa.ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("look_id", sa.String(36), sa.ForeignKey("looks.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("board_looks")
    op.drop_table("boards")
    op.drop_table("look_items")
    op.drop_table("looks")
    op.drop_table("feedback")
