"""add user verification fields

Revision ID: 20260216_01
Revises:
Create Date: 2026-02-16 14:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260216_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_users_verification_token_hash"),
        "users",
        ["verification_token_hash"],
        unique=False,
    )
    # Keep pre-existing accounts functional without forcing backfill tokens.
    op.execute("UPDATE users SET is_verified = TRUE WHERE verification_token_hash IS NULL")
    op.alter_column("users", "is_verified", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_verification_token_hash"), table_name="users")
    op.drop_column("users", "verification_token_expires_at")
    op.drop_column("users", "verification_token_hash")
    op.drop_column("users", "is_verified")
