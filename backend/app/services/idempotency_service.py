from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.custody_transfer import CustodyTransfer
from ..models.telemetry_event import TelemetryEvent


class IdempotencyService:
    @staticmethod
    def _normalize_db_timestamp(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def telemetry_exists(self, db: Session, *, event_id: str, idempotency_key: str) -> bool:
        by_event_id = db.query(TelemetryEvent.id).filter(TelemetryEvent.event_id == event_id).first()
        if by_event_id:
            return True
        by_key = db.query(TelemetryEvent.id).filter(TelemetryEvent.idempotency_key == idempotency_key).first()
        return bool(by_key)

    def custody_exists(self, db: Session, *, custody_event_id: str, idempotency_key: str) -> bool:
        by_event_id = (
            db.query(CustodyTransfer.id)
            .filter(CustodyTransfer.custody_event_id == custody_event_id)
            .first()
        )
        if by_event_id:
            return True
        by_key = (
            db.query(CustodyTransfer.id)
            .filter(CustodyTransfer.idempotency_key == idempotency_key)
            .first()
        )
        return bool(by_key)

    def telemetry_replay_reason(
        self,
        db: Session,
        *,
        device_id: str,
        seq_no: int,
        ts: datetime,
    ) -> str | None:
        now = datetime.now(timezone.utc)
        if ts > now + timedelta(seconds=settings.INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS):
            return "REPLAY_TIMESTAMP_FUTURE"
        if ts < now - timedelta(seconds=settings.INGEST_REPLAY_MAX_EVENT_AGE_SECONDS):
            return "REPLAY_TIMESTAMP_STALE"

        try:
            device_uuid = uuid.UUID(device_id)
        except ValueError:
            return "INVALID_UUID"

        latest_for_seq = (
            db.query(TelemetryEvent.seq_no)
            .filter(TelemetryEvent.device_id == device_uuid)
            .order_by(desc(TelemetryEvent.seq_no))
            .first()
        )
        if latest_for_seq and seq_no <= int(latest_for_seq[0]):
            return "REPLAY_SEQUENCE"

        latest_for_ts = (
            db.query(TelemetryEvent.ts)
            .filter(TelemetryEvent.device_id == device_uuid)
            .order_by(desc(TelemetryEvent.ts))
            .first()
        )
        latest_ts = self._normalize_db_timestamp(latest_for_ts[0] if latest_for_ts else None)
        if latest_ts and ts <= latest_ts:
            return "REPLAY_TIMESTAMP_ORDER"
        return None

    def custody_replay_reason(
        self,
        db: Session,
        *,
        verifier_device_id: str,
        shipment_id: str,
        ts: datetime,
    ) -> str | None:
        now = datetime.now(timezone.utc)
        if ts > now + timedelta(seconds=settings.INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS):
            return "REPLAY_TIMESTAMP_FUTURE"
        if ts < now - timedelta(seconds=settings.INGEST_REPLAY_MAX_EVENT_AGE_SECONDS):
            return "REPLAY_TIMESTAMP_STALE"

        try:
            verifier_device_uuid = uuid.UUID(verifier_device_id)
            shipment_uuid = uuid.UUID(shipment_id)
        except ValueError:
            return "INVALID_UUID"

        latest = (
            db.query(CustodyTransfer.ts)
            .filter(
                CustodyTransfer.verifier_device_id == verifier_device_uuid,
                CustodyTransfer.shipment_id == shipment_uuid,
            )
            .order_by(desc(CustodyTransfer.ts))
            .first()
        )
        latest_ts = self._normalize_db_timestamp(latest[0] if latest else None)
        if latest_ts and ts <= latest_ts:
            return "REPLAY_TIMESTAMP_ORDER"
        return None


idempotency_service = IdempotencyService()
