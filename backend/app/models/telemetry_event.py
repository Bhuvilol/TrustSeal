from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, nullable=False, unique=True, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    seq_no = Column(Integer, nullable=False)
    metrics = Column(JSON, nullable=True)
    gps = Column(JSON, nullable=True)
    hash_alg = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False, index=True)
    sig_alg = Column(String, nullable=False)
    signature = Column(Text, nullable=False)
    pubkey_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    verification_status = Column(String, nullable=False, default="valid", index=True)
    ingest_status = Column(String, nullable=False, default="received", index=True)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey("telemetry_batches.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    shipment = relationship("Shipment")
    device = relationship("Device")
    bundle = relationship("TelemetryBatch")

