from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.chain_anchor import ChainAnchor
from ..models.ipfs_object import IpfsObject
from ..models.telemetry_batch import TelemetryBatch
from .batch_finalization_service import BatchFinalizationError, batch_finalization_service
from .state_machine_service import state_machine_service

logger = logging.getLogger(__name__)


class AnchorWorker:
    """Owns custody_verified -> anchor_pending -> anchored/failed transitions."""

    def request_anchor(self, db: Session, *, bundle_id: str) -> ChainAnchor | None:
        try:
            bundle_uuid = uuid.UUID(str(bundle_id))
        except (TypeError, ValueError):
            return None

        batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_uuid).first()
        if batch is None:
            return None
        if batch.status not in {"custody_verified", "anchor_pending", "anchored", "failed"}:
            return None
        if batch.status == "anchored":
            return db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()

        anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()
        if anchor is None:
            anchor = ChainAnchor(
                bundle_id=batch.id,
                shipment_id=batch.shipment_id,
                network=f"polygon-{settings.CHAIN_CHAIN_ID}",
                contract_address=settings.CHAIN_CONTRACT_ADDRESS or "",
                anchor_status="pending",
            )
            db.add(anchor)
        else:
            transition = state_machine_service.ensure_transition(
                machine="anchor",
                from_state=anchor.anchor_status,
                to_state="pending",
            )
            if not transition.ok:
                anchor.error_message = transition.error
                db.commit()
                return None
            anchor.anchor_status = "pending"

        batch_transition = state_machine_service.ensure_transition(
            machine="batch",
            from_state=batch.status,
            to_state="anchor_pending",
        )
        if not batch_transition.ok:
            return None
        batch.status = "anchor_pending"
        db.commit()
        db.refresh(anchor)

        from .telemetry_stream_service import telemetry_stream_service

        telemetry_stream_service.publish_anchor_request(
            {
                "shipment_id": str(batch.shipment_id),
                "bundle_id": str(batch.id),
                "batch_hash": batch.batch_hash,
                "ipfs_cid": batch.ipfs_cid,
            }
        )
        return anchor

    def process_anchor(self, db: Session, *, bundle_id: str) -> ChainAnchor | None:
        try:
            bundle_uuid = uuid.UUID(str(bundle_id))
        except (TypeError, ValueError):
            return None

        batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_uuid).first()
        if batch is None or batch.status not in {"anchor_pending", "custody_verified"}:
            return None
        if batch.status == "custody_verified":
            promoted = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="anchor_pending",
            )
            if not promoted.ok:
                batch.error_message = promoted.error
                db.commit()
                return None
            batch.status = "anchor_pending"
            db.commit()

        ipfs_obj = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
        ipfs_cid = (batch.ipfs_cid or (ipfs_obj.ipfs_cid if ipfs_obj else None) or "").strip()
        if not ipfs_cid:
            batch_transition = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="failed",
            )
            if batch_transition.ok:
                batch.status = "failed"
            batch.error_message = "Cannot anchor without ipfs_cid"
            db.commit()
            return None

        anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()
        if anchor is None:
            anchor = ChainAnchor(
                bundle_id=batch.id,
                shipment_id=batch.shipment_id,
                network=f"polygon-{settings.CHAIN_CHAIN_ID}",
                contract_address=settings.CHAIN_CONTRACT_ADDRESS or "",
                anchor_status="pending",
            )
            db.add(anchor)
            db.flush()

        submit_transition = state_machine_service.ensure_transition(
            machine="anchor",
            from_state=anchor.anchor_status,
            to_state="submitted",
        )
        if not submit_transition.ok:
            anchor.error_message = submit_transition.error
            db.commit()
            return anchor
        anchor.anchor_status = "submitted"
        db.commit()

        try:
            tx_hash = batch_finalization_service._anchor_on_chain(
                shipment_id=str(batch.shipment_id),
                bundle_id=str(batch.id),
                bundle_hash=batch.batch_hash,
                ipfs_cid=ipfs_cid,
            )
        except BatchFinalizationError as exc:
            anchor_fail_transition = state_machine_service.ensure_transition(
                machine="anchor",
                from_state=anchor.anchor_status,
                to_state="failed",
            )
            if anchor_fail_transition.ok:
                anchor.anchor_status = "failed"
            anchor.error_message = str(exc)
            batch_fail_transition = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="failed",
            )
            if batch_fail_transition.ok:
                batch.status = "failed"
            batch.error_message = str(exc)
            db.commit()
            return anchor

        anchor.tx_hash = tx_hash
        confirm_transition = state_machine_service.ensure_transition(
            machine="anchor",
            from_state=anchor.anchor_status,
            to_state="confirmed",
        )
        if not confirm_transition.ok:
            anchor.error_message = confirm_transition.error
            db.commit()
            return anchor
        anchor.anchor_status = "confirmed"
        anchor.anchored_at = datetime.now(timezone.utc)
        batch.tx_hash = tx_hash
        batch_transition = state_machine_service.ensure_transition(
            machine="batch",
            from_state=batch.status,
            to_state="anchored",
        )
        if not batch_transition.ok:
            batch.error_message = batch_transition.error
            db.commit()
            return anchor
        batch.status = "anchored"
        batch.anchored_at = anchor.anchored_at
        batch.error_message = None
        db.commit()
        db.refresh(anchor)
        return anchor


anchor_worker = AnchorWorker()
