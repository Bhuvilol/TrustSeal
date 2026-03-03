from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from redis import Redis
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..models.enums import UserRole
from ..schemas.user import User as UserSchema
from ..models.telemetry_batch import TelemetryBatch
from ..services.batch_finalization_service import BatchFinalizationError, batch_finalization_service

router = APIRouter()


@router.get("/whoami", response_model=UserSchema)
def whoami(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Dev helper: return the current authenticated user (whoami).

    Use this to verify that the Authorization header reaches the backend
    and that the token decodes to a valid user.
    """
    return current_user


@router.get("/finalization/{shipment_id}")
def finalization_by_shipment(
    shipment_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return latest telemetry batch finalization state for a shipment."""
    row = (
        db.query(TelemetryBatch)
        .filter(TelemetryBatch.shipment_id == shipment_id)
        .order_by(TelemetryBatch.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No telemetry batch found for shipment")

    return {
        "shipment_id": str(row.shipment_id),
        "epoch": row.epoch,
        "status": row.status,
        "record_count": row.record_count,
        "batch_hash": row.batch_hash,
        "ipfs_cid": row.ipfs_cid,
        "tx_hash": row.tx_hash,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "anchored_at": row.anchored_at.isoformat() if row.anchored_at else None,
    }


@router.get("/finalization")
def finalization_recent(
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return recent telemetry batch finalization rows across shipments."""
    rows = db.query(TelemetryBatch).order_by(TelemetryBatch.created_at.desc()).limit(limit).all()
    return [
        {
            "shipment_id": str(row.shipment_id),
            "epoch": row.epoch,
            "status": row.status,
            "record_count": row.record_count,
            "batch_hash": row.batch_hash,
            "ipfs_cid": row.ipfs_cid,
            "tx_hash": row.tx_hash,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "anchored_at": row.anchored_at.isoformat() if row.anchored_at else None,
        }
        for row in rows
    ]


@router.get("/evidence/{shipment_id}")
def shipment_evidence_timeline(
    shipment_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return full custody-batch evidence timeline for a shipment."""
    rows = (
        db.query(TelemetryBatch)
        .filter(TelemetryBatch.shipment_id == shipment_id)
        .order_by(TelemetryBatch.epoch.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No telemetry evidence found for shipment")

    anchored_count = sum(1 for row in rows if row.status == "anchored")
    return {
        "shipment_id": str(shipment_id),
        "epochs_total": len(rows),
        "epochs_anchored": anchored_count,
        "epochs_pending": len(rows) - anchored_count,
        "epochs": [
            {
                "epoch": row.epoch,
                "status": row.status,
                "record_count": row.record_count,
                "batch_hash": row.batch_hash,
                "ipfs_cid": row.ipfs_cid,
                "tx_hash": row.tx_hash,
                "error_message": row.error_message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "anchored_at": row.anchored_at.isoformat() if row.anchored_at else None,
            }
            for row in rows
        ],
    }


@router.post("/finalization/reanchor/{shipment_id}")
def reanchor_pending_batches(
    shipment_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retry finalization for pending telemetry batches of a shipment."""
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    rows = (
        db.query(TelemetryBatch)
        .filter(
            TelemetryBatch.shipment_id == shipment_id,
            TelemetryBatch.status == "pending_ipfs_anchor",
        )
        .order_by(TelemetryBatch.epoch.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        return {"shipment_id": str(shipment_id), "processed": 0, "anchored": 0, "failed": 0, "results": []}

    results = []
    anchored = 0
    failed = 0

    for row in rows:
        batch_key = f"trustseal:batch:{shipment_id}:{row.epoch}"
        batch_data = redis_client.hgetall(batch_key)
        payload_json = batch_data.get("payload_json")
        if not payload_json:
            row.status = "finalization_failed"
            row.error_message = f"Missing payload_json in Redis key {batch_key}"
            failed += 1
            results.append(
                {
                    "epoch": row.epoch,
                    "status": row.status,
                    "error_message": row.error_message,
                }
            )
            continue

        try:
            finalization = batch_finalization_service.finalize(
                shipment_id=str(shipment_id),
                epoch=row.epoch,
                batch_hash=row.batch_hash,
                payload_json=payload_json,
            )
            row.status = "anchored"
            row.ipfs_cid = finalization.get("ipfs_cid")
            row.tx_hash = finalization.get("tx_hash")
            row.error_message = None
            row.anchored_at = datetime.now(timezone.utc)

            redis_client.hset(
                batch_key,
                mapping={
                    "status": "anchored",
                    "ipfs_cid": row.ipfs_cid or "",
                    "tx_hash": row.tx_hash or "",
                    "anchored_at": row.anchored_at.isoformat() if row.anchored_at else "",
                },
            )
            anchored += 1
            results.append(
                {
                    "epoch": row.epoch,
                    "status": row.status,
                    "ipfs_cid": row.ipfs_cid,
                    "tx_hash": row.tx_hash,
                }
            )
        except BatchFinalizationError as exc:
            row.status = "finalization_failed"
            row.error_message = str(exc)
            failed += 1
            results.append(
                {
                    "epoch": row.epoch,
                    "status": row.status,
                    "error_message": row.error_message,
                }
            )

    db.commit()
    return {
        "shipment_id": str(shipment_id),
        "processed": len(rows),
        "anchored": anchored,
        "failed": failed,
        "results": results,
    }
