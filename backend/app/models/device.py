from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import uuid
from .enums import DeviceStatus

class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String, unique=True, index=True, nullable=False)
    model = Column(String, nullable=False)
    firmware_version = Column(String, nullable=False)
    battery_capacity_mAh = Column(Integer, nullable=True)
    status = Column(Enum(DeviceStatus), nullable=False, default=DeviceStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    shipments = relationship("Shipment", back_populates="device")

    def __repr__(self):
        return f"<Device {self.device_uid}>"
