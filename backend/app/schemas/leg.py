from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from ..models.enums import LegStatus

class ShipmentLegBase(BaseModel):
    shipment_id: str
    leg_number: int
    from_location: str
    to_location: str

    @field_validator('shipment_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

class ShipmentLegCreate(ShipmentLegBase):
    pass

class ShipmentLegUpdate(BaseModel):
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    status: Optional[LegStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ShipmentLeg(ShipmentLegBase):
    id: str
    status: LegStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

    class Config:
        from_attributes = True
