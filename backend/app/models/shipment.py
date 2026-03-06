from sqlalchemy import Column, String, Text, ForeignKey, Integer, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import uuid
from .enums import ShipmentStatus, LegStatus

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_code = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    status = Column(Enum(ShipmentStatus), nullable=False, default=ShipmentStatus.CREATED)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="shipments")
    legs = relationship("ShipmentLeg", back_populates="shipment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Shipment {self.shipment_code}>"

class ShipmentLeg(Base):
    __tablename__ = "shipment_legs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False)
    leg_number = Column(Integer, nullable=False)
    from_location = Column(String, nullable=False)
    to_location = Column(String, nullable=False)
    status = Column(Enum(LegStatus), nullable=False, default=LegStatus.PENDING)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="legs")

    def __repr__(self):
        return f"<ShipmentLeg {self.leg_number} for Shipment {self.shipment_id}>"
