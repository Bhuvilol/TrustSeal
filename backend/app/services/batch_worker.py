from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.telemetry_batch import TelemetryBatch
from ..models.telemetry_event import TelemetryEvent
from .state_machine_service import state_machine_service

logger = logging.getLogger(__name__)


class BatchWorker:
    """Owns persisted -> bundled and open -> finalized transitions."""

    @staticmethod
    def _normalize_timestamp(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _pending_rows(self, db: Session, *, shipment_uuid: uuid.UUID) -> list[TelemetryEvent]:
        return (
            db.query(TelemetryEvent)
            .filter(
                TelemetryEvent.shipment_id == shipment_uuid,
                TelemetryEvent.ingest_status == "persisted",
                TelemetryEvent.bundle_id.is_(None),
            )
            .order_by(TelemetryEvent.ts.asc())
            .all()
        )

    def maybe_finalize_shipment_batch(
        self,
        db: Session,
        *,
        shipment_id: str,
        trigger: str,
        force: bool = False,
    ) -> TelemetryBatch | None:
        try:
            shipment_uuid = uuid.UUID(shipment_id)
        except (TypeError, ValueError):
            return None

        rows = self._pending_rows(db, shipment_uuid=shipment_uuid)
        if not rows:
            return None

        if force:
            return self.finalize_shipment_batch(db, shipment_id=shipment_id)

        min_records = max(1, settings.BATCH_MIN_RECORDS)
        if len(rows) >= min_records:
            logger.info(
                "Batch finalize trigger=min_records shipment_id=%s pending=%d threshold=%d",
                shipment_id,
                len(rows),
                min_records,
            )
            return self.finalize_shipment_batch(db, shipment_id=shipment_id)

        oldest_ts = self._normalize_timestamp(rows[0].ts)
        if oldest_ts is None:
            return None
        max_window = max(1, settings.BATCH_MAX_WINDOW_SECONDS)
        if oldest_ts <= datetime.now(timezone.utc) - timedelta(seconds=max_window):
            logger.info(
                "Batch finalize trigger=max_window shipment_id=%s pending=%d window_seconds=%d",
                shipment_id,
                len(rows),
                max_window,
            )
            return self.finalize_shipment_batch(db, shipment_id=shipment_id)

        logger.debug(
            "Batch not finalized trigger=%s shipment_id=%s pending=%d min_records=%d",
            trigger,
            shipment_id,
            len(rows),
            min_records,
        )
        return None

    def finalize_shipment_batch(self, db: Session, *, shipment_id: str) -> TelemetryBatch | None:
        try:
            shipment_uuid = uuid.UUID(shipment_id)
        except (TypeError, ValueError):
            return None

        rows = self._pending_rows(db, shipment_uuid=shipment_uuid)
        if not rows:
            return None

        payload = [
            {
                "event_id": r.event_id,
                "ts": r.ts.isoformat() if r.ts else None,
                "seq_no": r.seq_no,
                "metrics": r.metrics,
                "gps": r.gps,
                "payload_hash": r.payload_hash,
                "device_id": str(r.device_id),
            }
            for r in rows
        ]
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        batch_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        latest_epoch = (
            db.query(TelemetryBatch.epoch)
            .filter(TelemetryBatch.shipment_id == shipment_uuid)
            .order_by(TelemetryBatch.epoch.desc())
            .first()
        )
        next_epoch = int((latest_epoch[0] if latest_epoch else 0) or 0) + 1

        batch = TelemetryBatch(
            shipment_id=shipment_uuid,
            epoch=next_epoch,
            record_count=len(rows),
            batch_hash=batch_hash,
            status="open",
        )
        db.add(batch)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            logger.warning(
                "Batch finalize raced on epoch allocation shipment_id=%s epoch=%s; returning latest batch",
                shipment_id,
                next_epoch,
            )
            return (
                db.query(TelemetryBatch)
                .filter(TelemetryBatch.shipment_id == shipment_uuid)
                .order_by(TelemetryBatch.epoch.desc())
                .first()
            )

        for row in rows:
            transition = state_machine_service.ensure_transition(
                machine="telemetry_ingest",
                from_state=row.ingest_status,
                to_state="bundled",
            )
            if not transition.ok:
                db.rollback()
                logger.warning(
                    "Skipping batch finalize due to invalid telemetry transition event_id=%s from=%s",
                    row.event_id,
                    row.ingest_status,
                )
                return None
            row.bundle_id = batch.id
            row.ingest_status = "bundled"

        batch_transition = state_machine_service.ensure_transition(
            machine="batch",
            from_state=batch.status,
            to_state="finalized",
        )
        if not batch_transition.ok:
            db.rollback()
            logger.warning(
                "Skipping batch finalize due to invalid batch transition bundle_id=%s from=%s",
                batch.id,
                batch.status,
            )
            return None
        batch.status = "finalized"

        db.commit()
        db.refresh(batch)

        from .telemetry_stream_service import telemetry_stream_service

        telemetry_stream_service.publish_bundle_ready(
            {
                "shipment_id": str(shipment_uuid),
                "bundle_id": str(batch.id),
                "epoch": next_epoch,
                "record_count": len(rows),
                "batch_hash": batch_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return batch

    def build_bundle_payload_json(self, db: Session, *, bundle_id: str) -> str | None:
        try:
            bundle_uuid = uuid.UUID(str(bundle_id))
        except (TypeError, ValueError):
            return None

        rows = (
            db.query(TelemetryEvent)
            .filter(TelemetryEvent.bundle_id == bundle_uuid)
            .order_by(TelemetryEvent.ts.asc())
            .all()
        )
        if not rows:
            return None

        payload = [
            {
                "event_id": r.event_id,
                "ts": r.ts.isoformat() if r.ts else None,
                "seq_no": r.seq_no,
                "metrics": r.metrics,
                "gps": r.gps,
                "payload_hash": r.payload_hash,
                "device_id": str(r.device_id),
            }
            for r in rows
        ]
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


batch_worker = BatchWorker()
