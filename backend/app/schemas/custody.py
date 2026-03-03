from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class CustodyCheckpointBase(BaseModel):
    shipment_id: str
    leg_id: Optional[str] = None
    verified_by: Optional[str] = None
    biometric_verified: Optional[bool] = False
    blockchain_tx_hash: Optional[str] = None
    merkle_root_hash: Optional[str] = None

    @field_validator('shipment_id', mode='before')
    @classmethod
    def convert_shipment_uuid_to_str(cls, v):
        return str(v) if v else None

    @field_validator('leg_id', mode='before')
    @classmethod
    def convert_leg_uuid_to_str(cls, v):
        return str(v) if v else None

    @field_validator('verified_by', mode='before')
    @classmethod
    def convert_user_uuid_to_str(cls, v):
        return str(v) if v else None

class CustodyCheckpointCreate(CustodyCheckpointBase):
    pass

class CustodyCheckpointUpdate(BaseModel):
    leg_id: Optional[str] = None
    verified_by: Optional[str] = None
    biometric_verified: Optional[bool] = None
    blockchain_tx_hash: Optional[str] = None
    merkle_root_hash: Optional[str] = None

    @field_validator('leg_id', mode='before')
    @classmethod
    def convert_leg_uuid_to_str(cls, v):
        return str(v) if v else None

    @field_validator('verified_by', mode='before')
    @classmethod
    def convert_user_uuid_to_str(cls, v):
        return str(v) if v else None

class CustodyCheckpoint(CustodyCheckpointBase):
    id: str
    timestamp: datetime

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

    class Config:
        from_attributes = True
