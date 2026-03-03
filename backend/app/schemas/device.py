from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from ..models.enums import DeviceStatus

class DeviceBase(BaseModel):
    device_uid: str
    model: str
    firmware_version: str
    battery_capacity_mAh: Optional[int] = None
    status: DeviceStatus = DeviceStatus.ACTIVE

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    battery_capacity_mAh: Optional[int] = None
    status: Optional[DeviceStatus] = None

class Device(DeviceBase):
    id: str
    created_at: datetime

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

    class Config:
        from_attributes = True
