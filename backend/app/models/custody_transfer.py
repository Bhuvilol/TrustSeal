from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class CustodyTransfer(Base):
    __tablename__ = "custody_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    custody_event_id = Column(String, nullable=False, unique=True, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    leg_id = Column(UUID(as_uuid=True), ForeignKey("shipment_legs.id"), nullable=True, index=True)
    verifier_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    verifier_device_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    fingerprint_result = Column(String, nullable=False, index=True)
    fingerprint_score = Column(Float, nullable=True)
    fingerprint_template_id = Column(String, nullable=True)
    digital_signer_address = Column(String, nullable=False, index=True)
    approval_message_hash = Column(String, nullable=False, index=True)
    signature = Column(Text, nullable=False)
    sig_alg = Column(String, nullable=False)
    verification_status = Column(String, nullable=False, default="valid", index=True)
    ingest_status = Column(String, nullable=False, default="received", index=True)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    shipment = relationship("Shipment")
    leg = relationship("ShipmentLeg")
    verifier_user = relationship("User")

