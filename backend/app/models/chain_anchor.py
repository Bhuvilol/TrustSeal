from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class ChainAnchor(Base):
    __tablename__ = "chain_anchors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey("telemetry_batches.id"), nullable=False, unique=True, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    network = Column(String, nullable=False)
    contract_address = Column(String, nullable=False)
    tx_hash = Column(String, nullable=True, unique=True, index=True)
    block_number = Column(BigInteger, nullable=True)
    anchor_status = Column(String, nullable=False, default="pending", index=True)
    anchored_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bundle = relationship("TelemetryBatch")
    shipment = relationship("Shipment")

