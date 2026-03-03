from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    tenant_id: str | None = Field(default=None, min_length=1, max_length=120)
    device_id: str | None = Field(default=None, min_length=1, max_length=120)
    session_id: str | None = Field(default=None, max_length=120)
    top_k: int | None = Field(default=None, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    session_id: str | None = None


class IngestRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    device_id: str = Field(min_length=1, max_length=120)
    raw_document: str = Field(min_length=1, max_length=200000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    tenant_id: str
    device_id: str
    chunks_inserted: int
    document_ids: List[str] = Field(default_factory=list)
