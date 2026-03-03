from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..database import Base


class RAGDocument(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    device_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSONB, nullable=True)
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
