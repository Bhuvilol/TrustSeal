from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Literal

from ..core.config import settings
from ..database import SessionLocal
from ..models.enums import ShipmentStatus
from ..models.shipment import Shipment
from ..rag import (
    INSUFFICIENT_CONTEXT_RESPONSE,
    AgenticRAGAgent,
    AgenticRetriever,
    AsyncDocumentRepository,
    ShortTermConversationMemory,
    should_persist_long_term,
)
from .sensor_stats_service import calculate_sensor_statistics

Confidence = Literal["high", "medium", "low"]


@dataclass(slots=True)
class ChatResult:
    answer: str
    sources: list[str]
    confidence: Confidence
    session_id: str


@dataclass(slots=True)
class IngestResult:
    tenant_id: str
    device_id: str
    chunks_inserted: int
    document_ids: list[str]


class AgenticRAGService:
    def __init__(self) -> None:
        self._repository = AsyncDocumentRepository()
        self._retriever = AgenticRetriever(self._repository)
        self._agent = AgenticRAGAgent(self._retriever)
        self._memory = ShortTermConversationMemory(
            window_size=settings.AGENTIC_SHORT_MEMORY_WINDOW,
            ttl_minutes=settings.AGENTIC_SHORT_MEMORY_TTL_MINUTES,
        )
        self._started = False
        self._startup_lock = asyncio.Lock()

    async def startup(self) -> None:
        if self._started:
            return

        async with self._startup_lock:
            if self._started:
                return
            if not settings.DATABASE_URL.lower().startswith("postgresql"):
                # Service can still respond with graceful fallback, but vector features require PostgreSQL.
                self._started = True
                return
            await self._repository.open()
            try:
                await self._retriever.initialize()
            except Exception:
                # Keep API startup resilient; chat/ingest will surface provider/config errors when called.
                pass
            self._started = True

    async def shutdown(self) -> None:
        if not self._started:
            return
        if settings.DATABASE_URL.lower().startswith("postgresql"):
            await self._repository.close()
        self._started = False

    async def health(self) -> dict[str, str]:
        if not settings.DATABASE_URL.lower().startswith("postgresql"):
            return {"status": "degraded", "rag": "requires_postgresql"}
        if not self._started:
            return {"status": "degraded", "rag": "not_started"}
        ok = await self._repository.healthcheck()
        return {"status": "ok" if ok else "degraded", "rag": "ready" if ok else "db_unreachable"}

    async def ingest_document(
        self,
        *,
        tenant_id: str,
        device_id: str,
        raw_document: str,
        metadata: dict[str, object] | None = None,
    ) -> IngestResult:
        await self.startup()
        document_ids = await self._retriever.ingest_document(
            tenant_id=tenant_id,
            device_id=device_id,
            raw_document=raw_document,
            metadata=metadata or {},
        )
        return IngestResult(
            tenant_id=tenant_id,
            device_id=device_id,
            chunks_inserted=len(document_ids),
            document_ids=document_ids,
        )

    async def chat(
        self,
        *,
        message: str,
        tenant_id: str,
        device_id: str,
        user_id: str,
        session_id: str | None,
        top_k: int | None = None,
    ) -> ChatResult:
        await self.startup()

        clean_message = message.strip()
        if not clean_message:
            sid = self._resolve_session_id(session_id)
            return ChatResult(
                answer=INSUFFICIENT_CONTEXT_RESPONSE,
                sources=[],
                confidence="low",
                session_id=sid,
            )

        sid = self._resolve_session_id(session_id)
        scope_key = self._scope_key(
            tenant_id=tenant_id,
            device_id=device_id,
            user_id=user_id,
            session_id=sid,
        )
        history_turns = await self._memory.get_recent_turns(scope_key)
        agent_result = await self._agent.answer(
            message=clean_message,
            tenant_id=tenant_id,
            device_id=device_id,
            history_turns=history_turns,
            top_k=max(1, top_k or settings.AGENTIC_TOP_K),
        )

        answer_text = agent_result.answer
        answer_sources = agent_result.citations
        answer_confidence = agent_result.confidence

        if answer_text.strip() == INSUFFICIENT_CONTEXT_RESPONSE:
            fallback = await asyncio.to_thread(
                self._operational_fallback_sync,
                clean_message,
                device_id,
            )
            if fallback is not None:
                answer_text, answer_sources, answer_confidence = fallback

        await self._memory.append_turn(scope_key, clean_message, answer_text)
        if should_persist_long_term(clean_message, answer_text):
            memory_text = (
                f"User asked: {clean_message}\n"
                f"Assistant answered: {answer_text}\n"
                f"Citations: {', '.join(answer_sources) if answer_sources else 'none'}"
            )
            await self._retriever.ingest_document(
                tenant_id=tenant_id,
                device_id=device_id,
                raw_document=memory_text,
                metadata={
                    "doc_type": "memory",
                    "source": "conversation",
                    "session_id": sid,
                },
            )

        return ChatResult(
            answer=answer_text,
            sources=answer_sources,
            confidence=answer_confidence,
            session_id=sid,
        )

    def _resolve_session_id(self, session_id: str | None) -> str:
        value = (session_id or "").strip()
        if value:
            return value[:120]
        return f"session-{uuid.uuid4().hex[:16]}"

    def _scope_key(
        self,
        *,
        tenant_id: str,
        device_id: str,
        user_id: str,
        session_id: str,
    ) -> str:
        return f"{tenant_id}:{device_id}:{user_id}:{session_id}"

    def _operational_fallback_sync(
        self,
        message: str,
        device_id: str,
    ) -> tuple[str, list[str], Confidence] | None:
        q = message.lower()
        scoped_device_id = self._normalize_uuid_or_none(device_id)
        db = SessionLocal()
        try:
            if "in transit" in q or "currently in transit" in q:
                shipment_query = db.query(Shipment).filter(Shipment.status == ShipmentStatus.IN_TRANSIT)
                if scoped_device_id:
                    shipment_query = shipment_query.filter(Shipment.device_id == uuid.UUID(scoped_device_id))
                shipments = shipment_query.order_by(Shipment.created_at.desc()).limit(20).all()
                if shipments:
                    codes = ", ".join(s.shipment_code for s in shipments[:8])
                    extra = f" and {len(shipments) - 8} more" if len(shipments) > 8 else ""
                    answer = (
                        f"Situation: {len(shipments)} shipment(s) are currently in transit. "
                        f"Data Signals: Active shipment codes include {codes}{extra}. "
                        "Decision Recommendation: Maintain priority telemetry watch on active routes. "
                        "Immediate Next Action: Review temperature and shock exceptions for these in-transit shipments."
                    )
                    return (answer, [str(s.id) for s in shipments], "high")
                return None

            if "compromised" in q:
                compromised = (
                    db.query(Shipment)
                    .filter(Shipment.status == ShipmentStatus.COMPROMISED)
                    .order_by(Shipment.created_at.desc())
                    .limit(20)
                    .all()
                )
                if compromised:
                    codes = ", ".join(s.shipment_code for s in compromised[:8])
                    answer = (
                        f"Situation: {len(compromised)} shipment(s) are marked compromised. "
                        f"Data Signals: Compromised shipments include {codes}. "
                        "Decision Recommendation: Escalate custody and quality review for compromised lots. "
                        "Immediate Next Action: Open incident actions and verify latest telemetry anomalies."
                    )
                    return (answer, [str(s.id) for s in compromised], "high")
                return None

            asks_temperature = any(
                token in q
                for token in (
                    "temperature",
                    "avg temp",
                    "average temp",
                    "average temperature",
                    "min temperature",
                    "max temperature",
                    "degrees",
                )
            )
            asks_shock = "shock" in q
            if asks_temperature or asks_shock:
                stats = calculate_sensor_statistics(
                    db,
                    device_id=scoped_device_id,
                    temperature_threshold=settings.TEMPERATURE_THRESHOLD_C,
                )
                temp_samples = int(stats.get("temperature_sample_count", 0) or 0)
                max_shock = stats.get("max_shock")
                if asks_temperature and temp_samples <= 0:
                    return None
                if asks_shock and max_shock is None:
                    return None

                avg_temp = stats.get("average_temperature")
                min_temp = stats.get("min_temperature")
                max_temp = stats.get("max_temperature")
                shipment_ids = [str(sid) for sid in stats.get("shipment_ids", [])]

                if asks_temperature:
                    answer = (
                        "Situation: Temperature telemetry is available for operational analysis. "
                        f"Data Signals: Samples={temp_samples}, "
                        f"Average={self._fmt(avg_temp)} C, "
                        f"Min={self._fmt(min_temp)} C, "
                        f"Max={self._fmt(max_temp)} C. "
                        "Decision Recommendation: Track variance and trigger review on threshold breaches. "
                        "Immediate Next Action: Investigate shipments with readings above safe range."
                    )
                else:
                    answer = (
                        "Situation: Shock telemetry review completed. "
                        f"Data Signals: Maximum observed shock={self._fmt(max_shock)}. "
                        "Decision Recommendation: Validate handling conditions on routes with higher impact readings. "
                        "Immediate Next Action: Audit latest shock events and correlate with leg transitions."
                    )

                confidence: Confidence = "high" if (temp_samples > 0 or max_shock is not None) else "low"
                return (answer, shipment_ids, confidence)

            return None
        finally:
            db.close()

    def _normalize_uuid_or_none(self, value: str | None) -> str | None:
        raw = (value or "").strip()
        if not raw or raw == "*":
            return None
        try:
            return str(uuid.UUID(raw))
        except (TypeError, ValueError):
            return None

    def _fmt(self, value: float | int | None) -> str:
        if value is None:
            return "N/A"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "N/A"
