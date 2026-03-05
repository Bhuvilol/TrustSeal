from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_request_id() -> str:
    return str(uuid4())


class ApiSuccess(BaseModel):
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default_factory=new_request_id)
    timestamp: str = Field(default_factory=utc_now_iso)


class ApiError(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default_factory=new_request_id)
    timestamp: str = Field(default_factory=utc_now_iso)

