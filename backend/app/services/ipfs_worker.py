from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.ipfs_object import IpfsObject
from ..models.telemetry_batch import TelemetryBatch
from .state_machine_service import state_machine_service

logger = logging.getLogger(__name__)


class IpfsWorker:
    """Owns finalized -> ipfs_pinned transition."""

    def _payload_content_hash(self, payload_json: str) -> str:
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    def pin_bundle(self, db: Session, *, bundle_id: str, payload_json: str) -> IpfsObject | None:
        try:
            bundle_uuid = uuid.UUID(str(bundle_id))
        except (TypeError, ValueError):
            return None

        batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_uuid).first()
        if batch is None:
            return None
        if batch.status not in {"finalized", "ipfs_pinned", "failed"}:
            return None

        existing = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
        if existing and existing.pin_status == "pinned":
            return existing

        content_hash = self._payload_content_hash(payload_json)
        size_bytes = len(payload_json.encode("utf-8"))

        if not settings.IPFS_PIN_ENABLED:
            transition = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="ipfs_pinned",
            )
            if not transition.ok:
                batch.error_message = transition.error
                db.commit()
                return None
            batch.status = "ipfs_pinned"
            batch.ipfs_cid = "ipfs-disabled"
            if existing is None:
                existing = IpfsObject(
                    bundle_id=batch.id,
                    shipment_id=batch.shipment_id,
                    ipfs_cid="ipfs-disabled",
                    pin_status="skipped",
                    content_hash=content_hash,
                    size_bytes=size_bytes,
                )
                db.add(existing)
            else:
                existing.ipfs_cid = "ipfs-disabled"
                existing.pin_status = "skipped"
                existing.content_hash = content_hash
                existing.size_bytes = size_bytes
            db.commit()
            return existing

        if not settings.IPFS_PIN_JWT:
            fail_transition = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="failed",
            )
            if fail_transition.ok:
                batch.status = "failed"
            batch.error_message = "IPFS pinning enabled but IPFS_PIN_JWT missing"
            db.commit()
            return None

        request_payload = {
            "pinataMetadata": {"name": f"trustseal-bundle-{bundle_id}", "keyvalues": {"bundle_id": str(bundle_id)}},
            "pinataContent": json.loads(payload_json),
        }
        headers = {
            "Authorization": f"Bearer {settings.IPFS_PIN_JWT}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(settings.IPFS_PIN_ENDPOINT, headers=headers, json=request_payload)
                response.raise_for_status()
                body = response.json()
            cid = str(body.get("IpfsHash") or "").strip()
            if not cid:
                raise ValueError("IPFS response missing IpfsHash")
        except Exception as exc:
            logger.exception("IPFS pin failed for bundle_id=%s", bundle_id)
            fail_transition = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="failed",
            )
            if fail_transition.ok:
                batch.status = "failed"
            batch.error_message = str(exc)
            db.commit()
            return None

        if existing is None:
            existing = IpfsObject(
                bundle_id=batch.id,
                shipment_id=batch.shipment_id,
                ipfs_cid=cid,
                pin_status="pinned",
                pinned_at=datetime.now(timezone.utc),
                content_hash=content_hash,
                size_bytes=size_bytes,
            )
            db.add(existing)
        else:
            existing.ipfs_cid = cid
            existing.pin_status = "pinned"
            existing.pinned_at = datetime.now(timezone.utc)
            existing.content_hash = content_hash
            existing.size_bytes = size_bytes

        transition = state_machine_service.ensure_transition(
            machine="batch",
            from_state=batch.status,
            to_state="ipfs_pinned",
        )
        if not transition.ok:
            batch.error_message = transition.error
            db.commit()
            return None

        batch.ipfs_cid = cid
        batch.status = "ipfs_pinned"
        batch.error_message = None
        db.commit()
        db.refresh(existing)
        return existing


ipfs_worker = IpfsWorker()
