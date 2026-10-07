"""Phase 2.x migration: Google sign-in (nullable password, google_sub)."""

revision = "0003_google"
down_revision = "0002_phase2"
branch_labels = None
depends_on = None

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)
    op.add_column("users", sa.Column("google_sub", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.create_index("ix_users_google_sub", "users", ["google_sub"])


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "google_sub")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
