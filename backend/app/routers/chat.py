from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import require_roles
from ..models.enums import UserRole
from ..models.user import User
from ..schemas.chat import ChatRequest, ChatResponse, IngestRequest, IngestResponse
from ..services.chat_service import (
    ChatConfigurationError,
    ChatProviderError,
    chat_service,
)

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    payload: IngestRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> IngestResponse:
    try:
        result = await chat_service.ingest_document_async(
            tenant_id=payload.tenant_id.strip(),
            device_id=payload.device_id.strip(),
            raw_document=payload.raw_document.strip(),
            metadata=payload.metadata,
        )
        return IngestResponse(
            tenant_id=result.tenant_id,
            device_id=result.device_id,
            chunks_inserted=result.chunks_inserted,
            document_ids=result.document_ids,
        )
    except ChatConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ChatProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/chat", response_model=ChatResponse)
async def admin_chat(
    payload: ChatRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> ChatResponse:
    tenant_id = (payload.tenant_id or f"user:{current_user.id}").strip()
    device_id = (payload.device_id or "*").strip()

    try:
        return await chat_service.answer_question_async(
            payload.message,
            user_id=str(current_user.id),
            tenant_id=tenant_id,
            device_id=device_id,
            session_id=payload.session_id,
            top_k=payload.top_k,
        )
    except ChatConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ChatProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
