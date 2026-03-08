from __future__ import annotations

import logging
import uuid
from typing import Any
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.custody_transfer import CustodyTransfer
from ..models.telemetry_event import TelemetryEvent
from .realtime import build_realtime_event, shipment_event_dispatcher
from .state_machine_service import state_machine_service

logger = logging.getLogger(__name__)


class PersistenceWorker:
    """Owns queued -> persisted transition."""

    def _publish_telemetry_realtime(self, row: TelemetryEvent) -> None:
        metrics = row.metrics if isinstance(row.metrics, dict) else {}
        gps = row.gps if isinstance(row.gps, dict) else {}
        shipment_event_dispatcher.publish(
            str(row.shipment_id),
            build_realtime_event(
                event="telemetry-update",
                shipment_id=str(row.shipment_id),
                data={
                    "event_id": row.event_id,
                    "device_id": str(row.device_id),
                    "timestamp": row.ts.isoformat() if row.ts else None,
                    "seq_no": row.seq_no,
                    "temperature": metrics.get("temperature_c"),
                    "humidity": metrics.get("humidity_pct"),
                    "shock": metrics.get("shock_g"),
                    "light_lux": metrics.get("light_lux"),
                    "tilt_angle": metrics.get("tilt_deg"),
                    "battery_pct": metrics.get("battery_pct"),
                    "network_type": metrics.get("network_type"),
                    "firmware_version": metrics.get("firmware_version"),
                    "latitude": gps.get("lat"),
                    "longitude": gps.get("lng"),
                    "speed": gps.get("speed_kmh"),
                    "heading": gps.get("heading_deg"),
                },
            ),
        )

    def _parse_uuid(self, value: Any) -> uuid.UUID | None:
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return None

    def _parse_ts(self, value: Any) -> datetime:
        raw = str(value or "").strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)

    def _ensure_telemetry_row(self, db: Session, payload: dict[str, Any]) -> TelemetryEvent | None:
        event_id = str(payload.get("event_id") or "").strip()
        if not event_id:
            return None
        existing = db.query(TelemetryEvent).filter(TelemetryEvent.event_id == event_id).first()
        if existing is not None:
            return existing

        shipment_id = self._parse_uuid(payload.get("shipment_id"))
        device_id = self._parse_uuid(payload.get("device_id"))
        if shipment_id is None or device_id is None:
            return None

        seq_no_raw = payload.get("seq_no", 0)
        try:
            seq_no = max(int(seq_no_raw), 0)
        except (TypeError, ValueError):
            seq_no = 0

        metrics = payload.get("metrics")
        if not isinstance(metrics, dict):
            metrics = None
        gps = payload.get("gps")
        if gps is not None and not isinstance(gps, dict):
            gps = None

        idempotency_key = str(payload.get("idempotency_key") or event_id)
        row = TelemetryEvent(
            event_id=event_id,
            shipment_id=shipment_id,
            device_id=device_id,
            ts=self._parse_ts(payload.get("ts")),
            seq_no=seq_no,
            metrics=metrics,
            gps=gps,
            hash_alg=str(payload.get("hash_alg") or "sha256"),
            payload_hash=str(payload.get("payload_hash") or ""),
            sig_alg=str(payload.get("sig_alg") or "unknown"),
            signature=str(payload.get("signature") or "stream-inserted"),
            pubkey_id=str(payload.get("pubkey_id") or "stream-inserted"),
            idempotency_key=idempotency_key,
            verification_status=str(payload.get("verification_status") or "valid"),
            ingest_status="queued",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def _ensure_custody_row(self, db: Session, payload: dict[str, Any]) -> CustodyTransfer | None:
        custody_event_id = str(payload.get("custody_event_id") or "").strip()
        if not custody_event_id:
            return None
        existing = (
            db.query(CustodyTransfer)
            .filter(CustodyTransfer.custody_event_id == custody_event_id)
            .first()
        )
        if existing is not None:
            return existing

        shipment_id = self._parse_uuid(payload.get("shipment_id"))
        verifier_user_id = self._parse_uuid(payload.get("verifier_user_id"))
        verifier_device_id = self._parse_uuid(payload.get("verifier_device_id"))
        leg_id = self._parse_uuid(payload.get("leg_id"))
        if shipment_id is None or verifier_user_id is None or verifier_device_id is None:
            return None

        idempotency_key = str(payload.get("idempotency_key") or custody_event_id)
        row = CustodyTransfer(
            custody_event_id=custody_event_id,
            shipment_id=shipment_id,
            leg_id=leg_id,
            verifier_user_id=verifier_user_id,
            verifier_device_id=verifier_device_id,
            ts=self._parse_ts(payload.get("ts")),
            fingerprint_result=str(payload.get("fingerprint_result") or "error"),
            fingerprint_score=payload.get("fingerprint_score"),
            fingerprint_template_id=payload.get("fingerprint_template_id"),
            digital_signer_address=str(payload.get("digital_signer_address") or "0x0000000000000000000000000000000000000000"),
            approval_message_hash=str(payload.get("approval_message_hash") or ""),
            signature=str(payload.get("signature") or "stream-inserted"),
            sig_alg=str(payload.get("sig_alg") or "unknown"),
            verification_status=str(payload.get("verification_status") or "valid"),
            ingest_status="queued",
            idempotency_key=idempotency_key,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def mark_telemetry_persisted(self, db: Session, *, event_id: str) -> bool:
        row = db.query(TelemetryEvent).filter(TelemetryEvent.event_id == event_id).first()
        if row is None:
            return False
        if row.ingest_status == "persisted":
            return True
        transition = state_machine_service.ensure_transition(
            machine="telemetry_ingest",
            from_state=row.ingest_status,
            to_state="persisted",
        )
        if not transition.ok:
            return False
        row.ingest_status = "persisted"
        db.commit()
        self._publish_telemetry_realtime(row)
        return True

    def mark_custody_persisted(self, db: Session, *, custody_event_id: str) -> bool:
        row = (
            db.query(CustodyTransfer)
            .filter(CustodyTransfer.custody_event_id == custody_event_id)
            .first()
        )
        if row is None:
            return False
        if row.ingest_status == "persisted":
            return True
        transition = state_machine_service.ensure_transition(
            machine="telemetry_ingest",
            from_state=row.ingest_status,
            to_state="persisted",
        )
        if not transition.ok:
            return False
        row.ingest_status = "persisted"
        db.commit()
        return True

    def process_stream_payload(self, db: Session, *, event_type: str, payload: dict[str, Any]) -> bool:
        if event_type == "telemetry":
            event_id = str(payload.get("event_id") or "").strip()
            if not event_id:
                return False
            self._ensure_telemetry_row(db, payload)
            return self.mark_telemetry_persisted(db, event_id=event_id)
        if event_type == "custody":
            custody_event_id = str(payload.get("custody_event_id") or "").strip()
            if not custody_event_id:
                return False
            self._ensure_custody_row(db, payload)
            return self.mark_custody_persisted(db, custody_event_id=custody_event_id)
        return False


persistence_worker = PersistenceWorker()
