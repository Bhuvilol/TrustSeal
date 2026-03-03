from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

from .user import User as UserSchema

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Optional[str] = None
    user_id: Optional[str] = None

class TokenData(BaseModel):
    email: Optional[str] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None


class RegisterResponse(BaseModel):
    user: UserSchema
    access_token: str
    token_type: str = "bearer"
    verification_token: str
    verification_token_expires_at: datetime


class VerifyTokenRequest(BaseModel):
    email: EmailStr
    verification_token: str


class VerifyTokenResponse(BaseModel):
    message: str
    verified: bool
