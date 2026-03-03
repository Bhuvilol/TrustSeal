from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from ..models.enums import ShipmentStatus

class ShipmentBase(BaseModel):
    shipment_code: str
    description: Optional[str] = None
    origin: str
    destination: str
    device_id: str

    @field_validator('device_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

class ShipmentCreate(ShipmentBase):
    pass

class ShipmentUpdate(BaseModel):
    description: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    status: Optional[ShipmentStatus] = None
    device_id: Optional[str] = None

    @field_validator('device_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

class Shipment(ShipmentBase):
    id: str
    status: ShipmentStatus
    created_at: datetime

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

    class Config:
        from_attributes = True

class ShipmentWithDetails(Shipment):
    device: Optional["Device"] = None
    legs: Optional[List["ShipmentLeg"]] = []
    sensor_logs: Optional[List["SensorLog"]] = []
    custody_checkpoints: Optional[List["CustodyCheckpoint"]] = []

# Import to avoid circular imports
from .device import Device
from .leg import ShipmentLeg
from .sensor_log import SensorLog
from .custody import CustodyCheckpoint
