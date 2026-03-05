from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class TelemetryBatch(Base):
    __tablename__ = "telemetry_batches"
    __table_args__ = (
        UniqueConstraint("shipment_id", "epoch", name="uq_telemetry_batches_shipment_epoch"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    epoch = Column(Integer, nullable=False)
    record_count = Column(Integer, nullable=False, default=0)
    batch_hash = Column(String, nullable=False, index=True)
    ipfs_cid = Column(String, nullable=True, index=True)
    tx_hash = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="finalized", index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    anchored_at = Column(DateTime(timezone=True), nullable=True)

    shipment = relationship("Shipment")
