"""add custody_transfers table

Revision ID: 20260306_02
Revises: 20260306_01
Create Date: 2026-03-06 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260306_02"
down_revision: Union[str, Sequence[str], None] = "20260306_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type(bind) -> sa.types.TypeEngine:
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = _uuid_type(bind)

    op.create_table(
        "custody_transfers",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("custody_event_id", sa.String(), nullable=False),
        sa.Column("shipment_id", uuid_type, nullable=False),
        sa.Column("leg_id", uuid_type, nullable=True),
        sa.Column("verifier_user_id", uuid_type, nullable=False),
        sa.Column("verifier_device_id", uuid_type, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint_result", sa.String(), nullable=False),
        sa.Column("fingerprint_score", sa.Float(), nullable=True),
        sa.Column("fingerprint_template_id", sa.String(), nullable=True),
        sa.Column("digital_signer_address", sa.String(), nullable=False),
        sa.Column("approval_message_hash", sa.String(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("sig_alg", sa.String(), nullable=False),
        sa.Column("verification_status", sa.String(), nullable=False, server_default="valid"),
        sa.Column("ingest_status", sa.String(), nullable=False, server_default="received"),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["leg_id"], ["shipment_legs.id"]),
        sa.ForeignKeyConstraint(["verifier_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("custody_event_id", name="uq_custody_transfers_custody_event_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_custody_transfers_idempotency_key"),
    )
    op.create_index("ix_custody_transfers_shipment_id", "custody_transfers", ["shipment_id"], unique=False)
    op.create_index("ix_custody_transfers_leg_id", "custody_transfers", ["leg_id"], unique=False)
    op.create_index("ix_custody_transfers_verifier_user_id", "custody_transfers", ["verifier_user_id"], unique=False)
    op.create_index("ix_custody_transfers_verifier_device_id", "custody_transfers", ["verifier_device_id"], unique=False)
    op.create_index("ix_custody_transfers_ts", "custody_transfers", ["ts"], unique=False)
    op.create_index("ix_custody_transfers_fingerprint_result", "custody_transfers", ["fingerprint_result"], unique=False)
    op.create_index("ix_custody_transfers_digital_signer_address", "custody_transfers", ["digital_signer_address"], unique=False)
    op.create_index("ix_custody_transfers_approval_message_hash", "custody_transfers", ["approval_message_hash"], unique=False)
    op.create_index("ix_custody_transfers_verification_status", "custody_transfers", ["verification_status"], unique=False)
    op.create_index("ix_custody_transfers_ingest_status", "custody_transfers", ["ingest_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_custody_transfers_ingest_status", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_verification_status", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_approval_message_hash", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_digital_signer_address", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_fingerprint_result", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_ts", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_verifier_device_id", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_verifier_user_id", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_leg_id", table_name="custody_transfers")
    op.drop_index("ix_custody_transfers_shipment_id", table_name="custody_transfers")
    op.drop_table("custody_transfers")

