from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class IpfsObject(Base):
    __tablename__ = "ipfs_objects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey("telemetry_batches.id"), nullable=False, unique=True, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    ipfs_cid = Column(String, nullable=False, index=True)
    pin_status = Column(String, nullable=False, default="pending", index=True)
    pinned_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String, nullable=True, index=True)
    size_bytes = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bundle = relationship("TelemetryBatch")
    shipment = relationship("Shipment")

