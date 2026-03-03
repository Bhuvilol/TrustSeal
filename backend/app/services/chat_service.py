from __future__ import annotations

import asyncio

from ..schemas.chat import ChatResponse
from .agentic_rag_service import AgenticRAGService, IngestResult


class ChatServiceError(Exception):
    pass


class ChatConfigurationError(ChatServiceError):
    pass


class ChatProviderError(ChatServiceError):
    pass


class ChatService:
    def __init__(self) -> None:
        self._service = AgenticRAGService()

    async def startup(self) -> None:
        try:
            await self._service.startup()
        except Exception as exc:
            raise ChatConfigurationError("Failed to initialize Agentic RAG dependencies.") from exc

    async def shutdown(self) -> None:
        try:
            await self._service.shutdown()
        except Exception as exc:
            raise ChatProviderError("Failed to shutdown Agentic RAG service cleanly.") from exc

    async def health_status(self) -> dict[str, str]:
        return await self._service.health()

    async def answer_question_async(
        self,
        question: str,
        *,
        user_id: str,
        tenant_id: str,
        device_id: str,
        session_id: str | None,
        top_k: int | None = None,
    ) -> ChatResponse:
        try:
            result = await self._service.chat(
                message=question,
                user_id=user_id,
                tenant_id=tenant_id,
                device_id=device_id,
                session_id=session_id,
                top_k=top_k,
            )
            return ChatResponse(
                answer=result.answer,
                sources=result.sources,
                confidence=result.confidence,
                session_id=result.session_id,
            )
        except Exception as exc:
            if self._is_configuration_issue(exc):
                raise ChatConfigurationError("Agentic RAG is not configured correctly.") from exc
            raise ChatProviderError("Agentic RAG chat processing failed.") from exc

    def answer_question(
        self,
        question: str,
        _db: object | None = None,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        tenant_id: str | None = None,
        device_id: str | None = None,
        top_k: int | None = None,
    ) -> ChatResponse:
        async def _run() -> ChatResponse:
            return await self.answer_question_async(
                question,
                user_id=user_id or "anonymous",
                tenant_id=tenant_id or "default",
                device_id=device_id or "*",
                session_id=session_id,
                top_k=top_k,
            )

        return asyncio.run(_run())

    async def ingest_document_async(
        self,
        *,
        tenant_id: str,
        device_id: str,
        raw_document: str,
        metadata: dict[str, object] | None = None,
    ) -> IngestResult:
        try:
            return await self._service.ingest_document(
                tenant_id=tenant_id,
                device_id=device_id,
                raw_document=raw_document,
                metadata=metadata,
            )
        except Exception as exc:
            if self._is_configuration_issue(exc):
                raise ChatConfigurationError("Agentic RAG ingestion is not configured correctly.") from exc
            raise ChatProviderError("Agentic RAG ingestion failed.") from exc

    def _is_configuration_issue(self, exc: Exception) -> bool:
        text = str(exc).lower()
        config_hints = (
            "api key",
            "postgresql",
            "database",
            "connection",
            "pool initialization",
            "not configured",
            "failed to initialize",
        )
        return any(hint in text for hint in config_hints)


chat_service = ChatService()
