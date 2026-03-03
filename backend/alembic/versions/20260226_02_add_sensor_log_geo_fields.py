"""add geo fields to sensor logs

Revision ID: 20260226_02
Revises: 20260216_01
Create Date: 2026-02-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260226_02"
down_revision: Union[str, Sequence[str], None] = "20260216_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("sensor_logs")}

    if "latitude" not in cols:
        op.add_column("sensor_logs", sa.Column("latitude", sa.Float(), nullable=True))
    if "longitude" not in cols:
        op.add_column("sensor_logs", sa.Column("longitude", sa.Float(), nullable=True))
    if "speed" not in cols:
        op.add_column("sensor_logs", sa.Column("speed", sa.Float(), nullable=True))
    if "heading" not in cols:
        op.add_column("sensor_logs", sa.Column("heading", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("sensor_logs")}

    # Drop in reverse order, guarded for safety.
    if "heading" in cols:
        op.drop_column("sensor_logs", "heading")
    if "speed" in cols:
        op.drop_column("sensor_logs", "speed")
    if "longitude" in cols:
        op.drop_column("sensor_logs", "longitude")
    if "latitude" in cols:
        op.drop_column("sensor_logs", "latitude")
