from __future__ import annotations

import json
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from redis import Redis
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import get_db
from ..dependencies import require_roles
from ..models.chain_anchor import ChainAnchor
from ..models.custody_transfer import CustodyTransfer
from ..models.enums import UserRole
from ..models.ipfs_object import IpfsObject
from ..models.telemetry_event import TelemetryEvent
from ..models.telemetry_batch import TelemetryBatch
from ..services.archival_service import archival_service
from ..services.anchor_worker import anchor_worker
from ..services.batch_worker import batch_worker
from ..services.custody_gate_worker import custody_gate_worker
from ..services.ipfs_worker import ipfs_worker
from ..services.chain_indexer_service import chain_indexer_service
from ..services.worker_orchestrator import worker_orchestrator

router = APIRouter()


def _shipment_pipeline_snapshot(db: Session, shipment_id: uuid.UUID) -> dict:
    latest_event = (
        db.query(TelemetryEvent)
        .filter(TelemetryEvent.shipment_id == shipment_id)
        .order_by(TelemetryEvent.ts.desc(), TelemetryEvent.created_at.desc())
        .first()
    )
    latest_custody = (
        db.query(CustodyTransfer)
        .filter(CustodyTransfer.shipment_id == shipment_id)
        .order_by(CustodyTransfer.ts.desc(), CustodyTransfer.created_at.desc())
        .first()
    )
    latest_batch = (
        db.query(TelemetryBatch)
        .filter(TelemetryBatch.shipment_id == shipment_id)
        .order_by(TelemetryBatch.created_at.desc())
        .first()
    )

    latest_anchor = None
    latest_ipfs = None
    if latest_batch is not None:
        latest_anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == latest_batch.id).first()
        latest_ipfs = db.query(IpfsObject).filter(IpfsObject.bundle_id == latest_batch.id).first()

    custody_state = "missing"
    if latest_custody is not None:
        if latest_custody.verification_status != "valid":
            custody_state = str(latest_custody.verification_status)
        elif str(latest_custody.fingerprint_result or "").strip().lower() != "match":
            custody_state = "rejected"
        elif latest_custody.ingest_status == "persisted":
            custody_state = "verified"
        else:
            custody_state = str(latest_custody.ingest_status or "received")

    anchor_state = "missing"
    if latest_anchor is not None:
        anchor_state = str(latest_anchor.anchor_status)
        if anchor_state == "confirmed":
            anchor_state = "confirmed"
    elif latest_batch is not None and latest_batch.status == "anchored":
        anchor_state = "confirmed"
    elif latest_batch is not None and latest_batch.status == "anchor_pending":
        anchor_state = "pending"

    updated_at = None
    if latest_anchor and latest_anchor.anchored_at:
        updated_at = latest_anchor.anchored_at.isoformat()
    elif latest_batch and latest_batch.created_at:
        updated_at = latest_batch.created_at.isoformat()
    elif latest_event and latest_event.created_at:
        updated_at = latest_event.created_at.isoformat()

    return {
        "shipment_id": str(shipment_id),
        "ingest": str(latest_event.ingest_status if latest_event else "missing"),
        "batch": str(latest_batch.status if latest_batch else "missing"),
        "custody": custody_state,
        "anchor": anchor_state,
        "latest_bundle_id": str(latest_batch.id) if latest_batch else None,
        "latest_ipfs_cid": (
            latest_batch.ipfs_cid
            if latest_batch and latest_batch.ipfs_cid
            else (latest_ipfs.ipfs_cid if latest_ipfs else None)
        ),
        "latest_tx_hash": (
            latest_batch.tx_hash
            if latest_batch and latest_batch.tx_hash
            else (latest_anchor.tx_hash if latest_anchor else None)
        ),
        "updated_at": updated_at,
        "error_message": (
            latest_batch.error_message
            if latest_batch and latest_batch.error_message
            else (latest_anchor.error_message if latest_anchor else None)
        ),
    }


@router.get("/pipeline-status")
def pipeline_status(
    shipment_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    """Get pipeline status (requires admin auth)."""
    batch_rows = db.query(TelemetryBatch).all()
    by_status = dict(Counter(str(batch.status) for batch in batch_rows if getattr(batch, "status", None)))

    anchors_pending = len(
        db.query(ChainAnchor)
        .filter(ChainAnchor.anchor_status.in_(["pending", "submitted"]))
        .all()
    )
    anchors_failed = len(
        db.query(ChainAnchor)
        .filter(ChainAnchor.anchor_status == "failed")
        .all()
    )
    ipfs_pending = len(
        db.query(IpfsObject)
        .filter(IpfsObject.pin_status.in_(["pending"]))
        .all()
    )

    redis_info = {"available": False}
    if settings.TELEMETRY_PIPELINE_MODE in {"redis", "dual"}:
        try:
            r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            redis_info = {
                "available": True,
                "telemetry_stream_len": r.xlen(settings.REDIS_TELEMETRY_STREAM),
                "custody_stream_len": r.xlen(settings.REDIS_CUSTODY_STREAM),
                "bundle_ready_stream_len": r.xlen(settings.REDIS_BUNDLE_READY_STREAM),
                "anchor_request_stream_len": r.xlen(settings.REDIS_ANCHOR_REQUEST_STREAM),
                "dead_letter_stream_len": r.xlen(settings.REDIS_DEAD_LETTER_STREAM),
            }
            r.close()
        except Exception as exc:
            redis_info = {"available": False, "error": str(exc)}

    response = {
        "pipeline": {
            "batch_status_counts": by_status,
            "anchors_pending": int(anchors_pending),
            "anchors_failed": int(anchors_failed),
            "ipfs_pending": int(ipfs_pending),
        },
        "redis": redis_info,
        "workers": {
            "started": worker_orchestrator.get_status()["started"],
            "healthy": worker_orchestrator.is_healthy(),
        },
    }
    if shipment_id is not None:
        response["shipment"] = _shipment_pipeline_snapshot(db, shipment_id)
    return response


@router.post("/retry/anchor")
def retry_anchor(
    bundle_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Bundle not found")

    anchor = anchor_worker.request_anchor(db, bundle_id=str(bundle_id))
    if anchor is None:
        raise HTTPException(status_code=409, detail=f"Bundle is not eligible for anchor retry (status={batch.status})")

    return {
        "accepted": True,
        "bundle_id": str(bundle_id),
        "shipment_id": str(batch.shipment_id),
        "batch_status": batch.status,
        "anchor_status": anchor.anchor_status,
    }


@router.post("/retry/ipfs")
def retry_ipfs_pin(
    bundle_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Bundle not found")

    payload_json = batch_worker.build_bundle_payload_json(db, bundle_id=str(bundle_id))
    if not payload_json:
        raise HTTPException(status_code=409, detail="Bundle payload missing; cannot retry IPFS")

    pinned = ipfs_worker.pin_bundle(db, bundle_id=str(bundle_id), payload_json=payload_json)
    if pinned is None:
        raise HTTPException(status_code=409, detail=f"IPFS pin retry failed (batch_status={batch.status})")

    return {
        "accepted": True,
        "bundle_id": str(bundle_id),
        "shipment_id": str(batch.shipment_id),
        "batch_status": batch.status,
        "ipfs_cid": batch.ipfs_cid or pinned.ipfs_cid,
        "pin_status": pinned.pin_status,
    }


@router.post("/retry/custody-gate")
def retry_custody_gate(
    bundle_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Bundle not found")

    verified = custody_gate_worker.verify_bundle_custody(db, bundle_id=str(bundle_id))
    if not verified:
        raise HTTPException(
            status_code=409,
            detail=f"Custody gate retry failed (batch_status={batch.status}, error={batch.error_message})",
        )

    anchor = anchor_worker.request_anchor(db, bundle_id=str(bundle_id))
    return {
        "accepted": True,
        "bundle_id": str(bundle_id),
        "shipment_id": str(batch.shipment_id),
        "batch_status": batch.status,
        "custody_verified": True,
        "anchor_status": anchor.anchor_status if anchor else None,
    }


@router.post("/reconcile")
def reconcile_pipeline(
    shipment_id: uuid.UUID | None = Query(default=None),
    execute_repair: bool = Query(default=False),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    query = db.query(TelemetryBatch)
    if shipment_id:
        query = query.filter(TelemetryBatch.shipment_id == shipment_id)
    batches = query.order_by(TelemetryBatch.created_at.desc()).all()

    missing_ipfs = []
    missing_anchor = []
    repaired = []

    for batch in batches:
        ipfs_obj = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
        anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()

        if batch.status in {"ipfs_pinned", "custody_verified", "anchor_pending", "anchored"} and not ipfs_obj:
            missing_ipfs.append(str(batch.id))
        if batch.status in {"anchor_pending", "anchored"} and not anchor:
            missing_anchor.append(str(batch.id))
            if execute_repair and batch.status == "anchor_pending":
                created = anchor_worker.request_anchor(db, bundle_id=str(batch.id))
                if created:
                    repaired.append(str(batch.id))

    return {
        "shipment_scope": str(shipment_id) if shipment_id else "all",
        "scanned_batches": len(batches),
        "missing_ipfs_rows": missing_ipfs,
        "missing_anchor_rows": missing_anchor,
        "repair_executed": execute_repair,
        "repaired_bundle_ids": repaired,
    }


@router.post("/reindex/chain")
def reindex_chain(
    from_block: int | None = Query(default=None, ge=0),
    to_block: int | None = Query(default=None, ge=0),
    block_batch_size: int | None = Query(default=None, ge=1, le=5000),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    result = chain_indexer_service.sync_once(
        db,
        from_block=from_block,
        to_block=to_block,
        block_batch_size=block_batch_size,
    )
    return {"accepted": True, "result": result}


@router.post("/reprocess/dead-letter")
def reprocess_dead_letter(
    limit: int = Query(default=100, ge=1, le=1000),
    delete_requeued: bool = Query(default=False),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    _ = db  # explicit for API consistency; DB not used in this operation.
    if settings.TELEMETRY_PIPELINE_MODE not in {"redis", "dual"}:
        raise HTTPException(status_code=503, detail="Redis stream mode is disabled")

    try:
        r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        entries = r.xrange(settings.REDIS_DEAD_LETTER_STREAM, min="-", max="+", count=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Dead-letter stream unavailable: {exc}")

    scanned = len(entries)
    requeued = 0
    skipped = 0
    failed = 0

    for message_id, fields in entries:
        stream_name = str(fields.get("stream_name") or "").strip()
        raw_fields = fields.get("fields")
        if not stream_name or not raw_fields:
            skipped += 1
            continue
        try:
            original_fields = json.loads(raw_fields)
            if not isinstance(original_fields, dict):
                skipped += 1
                continue
            r.xadd(stream_name, original_fields)
            requeued += 1
            if delete_requeued:
                r.xdel(settings.REDIS_DEAD_LETTER_STREAM, message_id)
        except Exception:
            failed += 1

    r.close()
    return {
        "accepted": True,
        "dead_letter_stream": settings.REDIS_DEAD_LETTER_STREAM,
        "scanned": scanned,
        "requeued": requeued,
        "skipped": skipped,
        "failed": failed,
        "delete_requeued": delete_requeued,
    }


@router.get("/archival-plan")
def archival_plan(
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    cutoffs = archival_service.cutoffs()
    counts = archival_service.candidate_counts(db)
    return {
        "policy": archival_service.policy(),
        "cutoffs": {k: v.isoformat() for k, v in cutoffs.items()},
        "candidate_counts": counts,
        "notes": [
            "cold_archive_candidates are records older than hot_cutoff.",
            "deep_archive_candidates are records older than cold_cutoff.",
            "purge_candidates are records older than purge_cutoff; purge is gated by ARCHIVE_ENABLE_PURGE.",
        ],
    }


@router.get("/workers/status")
def get_workers_status(
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    """Get status of all Redis stream workers (requires admin auth)."""
    status = worker_orchestrator.get_status()
    return {
        "orchestrator": {
            "started": status["started"],
            "healthy": worker_orchestrator.is_healthy(),
            "shutdown_requested": status["shutdown_requested"],
        },
        "workers": status["workers"],
    }


@router.post("/workers/restart/{worker_name}")
def restart_worker(
    worker_name: str,
    _admin=Depends(require_roles(UserRole.ADMIN)),
):
    """
    Restart a specific worker.
    
    Available workers:
    - telemetry_stream_service
    """
    success = worker_orchestrator.restart_worker(worker_name)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to restart worker: {worker_name}. Check logs for details.",
        )
    
    return {
        "success": True,
        "worker_name": worker_name,
        "message": f"Worker {worker_name} restarted successfully",
    }
