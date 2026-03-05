"""add canonical pipeline tables

Revision ID: 20260306_01
Revises: 20260303_02
Create Date: 2026-03-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260306_01"
down_revision: Union[str, Sequence[str], None] = "20260303_02"
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
        "telemetry_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("shipment_id", uuid_type, nullable=False),
        sa.Column("device_id", uuid_type, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("gps", sa.JSON(), nullable=True),
        sa.Column("hash_alg", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("sig_alg", sa.String(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("pubkey_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("verification_status", sa.String(), nullable=False, server_default="valid"),
        sa.Column("ingest_status", sa.String(), nullable=False, server_default="received"),
        sa.Column("bundle_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["bundle_id"], ["telemetry_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_telemetry_events_event_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_telemetry_events_idempotency_key"),
    )
    op.create_index("ix_telemetry_events_shipment_id", "telemetry_events", ["shipment_id"], unique=False)
    op.create_index("ix_telemetry_events_device_id", "telemetry_events", ["device_id"], unique=False)
    op.create_index("ix_telemetry_events_ts", "telemetry_events", ["ts"], unique=False)
    op.create_index("ix_telemetry_events_payload_hash", "telemetry_events", ["payload_hash"], unique=False)
    op.create_index("ix_telemetry_events_pubkey_id", "telemetry_events", ["pubkey_id"], unique=False)
    op.create_index("ix_telemetry_events_verification_status", "telemetry_events", ["verification_status"], unique=False)
    op.create_index("ix_telemetry_events_ingest_status", "telemetry_events", ["ingest_status"], unique=False)
    op.create_index("ix_telemetry_events_bundle_id", "telemetry_events", ["bundle_id"], unique=False)

    op.create_table(
        "ipfs_objects",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("bundle_id", uuid_type, nullable=False),
        sa.Column("shipment_id", uuid_type, nullable=False),
        sa.Column("ipfs_cid", sa.String(), nullable=False),
        sa.Column("pin_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["telemetry_batches.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_id", name="uq_ipfs_objects_bundle_id"),
    )
    op.create_index("ix_ipfs_objects_shipment_id", "ipfs_objects", ["shipment_id"], unique=False)
    op.create_index("ix_ipfs_objects_ipfs_cid", "ipfs_objects", ["ipfs_cid"], unique=False)
    op.create_index("ix_ipfs_objects_pin_status", "ipfs_objects", ["pin_status"], unique=False)
    op.create_index("ix_ipfs_objects_content_hash", "ipfs_objects", ["content_hash"], unique=False)

    op.create_table(
        "chain_anchors",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("bundle_id", uuid_type, nullable=False),
        sa.Column("shipment_id", uuid_type, nullable=False),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("contract_address", sa.String(), nullable=False),
        sa.Column("tx_hash", sa.String(), nullable=True),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("anchor_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["telemetry_batches.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_id", name="uq_chain_anchors_bundle_id"),
        sa.UniqueConstraint("tx_hash", name="uq_chain_anchors_tx_hash"),
    )
    op.create_index("ix_chain_anchors_shipment_id", "chain_anchors", ["shipment_id"], unique=False)
    op.create_index("ix_chain_anchors_anchor_status", "chain_anchors", ["anchor_status"], unique=False)
    op.create_index("ix_chain_anchors_tx_hash", "chain_anchors", ["tx_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chain_anchors_tx_hash", table_name="chain_anchors")
    op.drop_index("ix_chain_anchors_anchor_status", table_name="chain_anchors")
    op.drop_index("ix_chain_anchors_shipment_id", table_name="chain_anchors")
    op.drop_table("chain_anchors")

    op.drop_index("ix_ipfs_objects_content_hash", table_name="ipfs_objects")
    op.drop_index("ix_ipfs_objects_pin_status", table_name="ipfs_objects")
    op.drop_index("ix_ipfs_objects_ipfs_cid", table_name="ipfs_objects")
    op.drop_index("ix_ipfs_objects_shipment_id", table_name="ipfs_objects")
    op.drop_table("ipfs_objects")

    op.drop_index("ix_telemetry_events_bundle_id", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_ingest_status", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_verification_status", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_pubkey_id", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_payload_hash", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_ts", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_device_id", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_shipment_id", table_name="telemetry_events")
    op.drop_table("telemetry_events")

