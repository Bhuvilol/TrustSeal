from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import uuid

class CustodyCheckpoint(Base):
    __tablename__ = "custody_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False)
    leg_id = Column(UUID(as_uuid=True), ForeignKey("shipment_legs.id"), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    biometric_verified = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    blockchain_tx_hash = Column(String, nullable=True)
    merkle_root_hash = Column(String, nullable=True)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="custody_checkpoints")
    leg = relationship("ShipmentLeg", back_populates="custody_checkpoints")
    verifier = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<CustodyCheckpoint for Shipment {self.shipment_id} at {self.timestamp}>"
