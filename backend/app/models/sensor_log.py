from sqlalchemy import Column, Float, Boolean, ForeignKey, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import uuid

class SensorLog(Base):
    __tablename__ = "sensor_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    shock = Column(Float, nullable=True)
    light_exposure = Column(Boolean, default=False)
    tilt_angle = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    hash_value = Column(String, nullable=False)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="sensor_logs")

    def __repr__(self):
        return f"<SensorLog for Shipment {self.shipment_id} at {self.recorded_at}>"
