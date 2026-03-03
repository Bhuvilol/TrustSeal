"""create telemetry_batches table

Revision ID: 20260303_02
Revises: 20260303_01
Create Date: 2026-03-03 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260303_02"
down_revision: Union[str, Sequence[str], None] = "20260303_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    uuid_type = postgresql.UUID(as_uuid=True) if is_postgres else sa.String(length=36)

    op.create_table(
        "telemetry_batches",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("shipment_id", uuid_type, nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_hash", sa.String(), nullable=False),
        sa.Column("ipfs_cid", sa.String(), nullable=True),
        sa.Column("tx_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_ipfs_anchor"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_id", "epoch", name="uq_telemetry_batches_shipment_epoch"),
    )
    op.create_index("ix_telemetry_batches_shipment_id", "telemetry_batches", ["shipment_id"], unique=False)
    op.create_index("ix_telemetry_batches_batch_hash", "telemetry_batches", ["batch_hash"], unique=False)
    op.create_index("ix_telemetry_batches_ipfs_cid", "telemetry_batches", ["ipfs_cid"], unique=False)
    op.create_index("ix_telemetry_batches_tx_hash", "telemetry_batches", ["tx_hash"], unique=False)
    op.create_index("ix_telemetry_batches_status", "telemetry_batches", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_telemetry_batches_status", table_name="telemetry_batches")
    op.drop_index("ix_telemetry_batches_tx_hash", table_name="telemetry_batches")
    op.drop_index("ix_telemetry_batches_ipfs_cid", table_name="telemetry_batches")
    op.drop_index("ix_telemetry_batches_batch_hash", table_name="telemetry_batches")
    op.drop_index("ix_telemetry_batches_shipment_id", table_name="telemetry_batches")
    op.drop_table("telemetry_batches")

