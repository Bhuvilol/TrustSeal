"""align telemetry batch default status

Revision ID: 20260306_03
Revises: 20260306_02
Create Date: 2026-03-06 18:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260306_03"
down_revision: Union[str, Sequence[str], None] = "20260306_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "telemetry_batches",
        "status",
        existing_type=sa.String(),
        server_default="finalized",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "telemetry_batches",
        "status",
        existing_type=sa.String(),
        server_default="pending_ipfs_anchor",
        existing_nullable=False,
    )

