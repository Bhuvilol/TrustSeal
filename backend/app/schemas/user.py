from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from ..models.enums import UserRole

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.CUSTOMER

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: str
    created_at: datetime
    is_active: bool
    is_verified: bool

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

    class Config:
        from_attributes = True

class UserInDB(User):
    password_hash: str
