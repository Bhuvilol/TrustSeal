from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.custody_transfer import CustodyTransfer
from ..models.ipfs_object import IpfsObject
from ..models.telemetry_batch import TelemetryBatch
from .state_machine_service import state_machine_service

logger = logging.getLogger(__name__)


class CustodyGateWorker:
    """Owns ipfs_pinned -> custody_verified transition."""

    def verify_bundle_custody(self, db: Session, *, bundle_id: str) -> bool:
        try:
            bundle_uuid = uuid.UUID(str(bundle_id))
        except (TypeError, ValueError):
            return False

        batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_uuid).first()
        if batch is None:
            return False

        if batch.status == "custody_verified":
            return True
        if batch.status != "ipfs_pinned":
            return False

        ipfs_obj = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
        if ipfs_obj is None or ipfs_obj.pin_status not in {"pinned", "skipped"}:
            batch.error_message = "Custody gate blocked: IPFS object missing or not pinned"
            db.commit()
            return False

        created_at = batch.created_at or datetime.now(timezone.utc)
        max_age = max(1, settings.CUSTODY_GATE_MAX_AGE_SECONDS)
        custody_cutoff = created_at - timedelta(seconds=max_age)

        custody = (
            db.query(CustodyTransfer)
            .filter(
                CustodyTransfer.shipment_id == batch.shipment_id,
                CustodyTransfer.verification_status == "valid",
                CustodyTransfer.fingerprint_result == "match",
                CustodyTransfer.ingest_status == "persisted",
                CustodyTransfer.ts >= custody_cutoff,
            )
            .order_by(CustodyTransfer.ts.desc())
            .first()
        )
        if custody is None:
            batch.error_message = (
                "Custody gate blocked: missing recent persisted fingerprint match event "
                f"(window={max_age}s)"
            )
            db.commit()
            return False

        transition = state_machine_service.ensure_transition(
            machine="batch",
            from_state=batch.status,
            to_state="custody_verified",
        )
        if not transition.ok:
            batch.error_message = transition.error
            db.commit()
            return False

        batch.status = "custody_verified"
        batch.error_message = None
        db.commit()
        return True


custody_gate_worker = CustodyGateWorker()
