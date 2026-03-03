from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from ..database import Base
import uuid
from .enums import UserRole

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean(), default=True)
    is_verified = Column(Boolean(), default=False, nullable=False)
    verification_token_hash = Column(String, nullable=True, index=True)
    verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"
