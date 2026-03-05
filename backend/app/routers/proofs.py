from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_active_user
from ..models.chain_anchor import ChainAnchor
from ..models.ipfs_object import IpfsObject
from ..models.telemetry_batch import TelemetryBatch
from ..models.user import User

router = APIRouter()


def _to_iso(dt):
    return dt.isoformat() if dt else None


def _resolve_linkage(batch: TelemetryBatch, ipfs_obj: IpfsObject | None, anchor: ChainAnchor | None) -> dict:
    ipfs_cid = batch.ipfs_cid or (ipfs_obj.ipfs_cid if ipfs_obj else None)
    tx_hash = batch.tx_hash or (anchor.tx_hash if anchor else None)
    return {
        "bundle_id": str(batch.id),
        "shipment_id": str(batch.shipment_id),
        "bundle_hash": batch.batch_hash,
        "ipfs_cid": ipfs_cid,
        "tx_hash": tx_hash,
        "anchor_status": anchor.anchor_status if anchor else None,
        "network": anchor.network if anchor else None,
        "contract_address": anchor.contract_address if anchor else None,
        "anchored_at": _to_iso(batch.anchored_at) or (_to_iso(anchor.anchored_at) if anchor else None),
    }


@router.get("/shipments/{shipment_id}/latest")
def latest_shipment_proof(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    batch = (
        db.query(TelemetryBatch)
        .filter(TelemetryBatch.shipment_id == shipment_id)
        .order_by(TelemetryBatch.created_at.desc())
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="No bundle found for shipment")

    ipfs_obj = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
    anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()
    linkage = _resolve_linkage(batch, ipfs_obj, anchor)

    return {
        "shipment_id": str(shipment_id),
        "bundle_id": linkage["bundle_id"],
        "epoch": batch.epoch,
        "status": batch.status,
        "record_count": batch.record_count,
        "batch_hash": linkage["bundle_hash"],
        "ipfs_cid": linkage["ipfs_cid"],
        "tx_hash": linkage["tx_hash"],
        "anchor_status": linkage["anchor_status"],
        "network": linkage["network"],
        "contract_address": linkage["contract_address"],
        "anchored_at": linkage["anchored_at"],
        "proof_linkage": linkage,
        "ipfs": {
            "cid": linkage["ipfs_cid"],
            "pin_status": ipfs_obj.pin_status if ipfs_obj else None,
            "pinned_at": _to_iso(ipfs_obj.pinned_at) if ipfs_obj else None,
        },
        "chain": {
            "network": anchor.network if anchor else None,
            "contract_address": anchor.contract_address if anchor else None,
            "tx_hash": linkage["tx_hash"],
            "anchor_status": anchor.anchor_status if anchor else None,
            "anchored_at": linkage["anchored_at"],
        },
        "created_at": _to_iso(batch.created_at),
        "error_message": batch.error_message,
    }


@router.get("/bundles/{bundle_id}")
def bundle_proof(
    bundle_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Bundle not found")

    ipfs_obj = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
    anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()
    linkage = _resolve_linkage(batch, ipfs_obj, anchor)

    return {
        "bundle_id": linkage["bundle_id"],
        "shipment_id": linkage["shipment_id"],
        "epoch": batch.epoch,
        "status": batch.status,
        "record_count": batch.record_count,
        "batch_hash": linkage["bundle_hash"],
        "ipfs_cid": linkage["ipfs_cid"],
        "tx_hash": linkage["tx_hash"],
        "anchor_status": linkage["anchor_status"],
        "network": linkage["network"],
        "contract_address": linkage["contract_address"],
        "anchored_at": linkage["anchored_at"],
        "proof_linkage": linkage,
        "ipfs": {
            "cid": linkage["ipfs_cid"],
            "pin_status": ipfs_obj.pin_status if ipfs_obj else None,
            "content_hash": ipfs_obj.content_hash if ipfs_obj else None,
            "size_bytes": ipfs_obj.size_bytes if ipfs_obj else None,
            "pinned_at": _to_iso(ipfs_obj.pinned_at) if ipfs_obj else None,
        },
        "chain": {
            "network": anchor.network if anchor else None,
            "contract_address": anchor.contract_address if anchor else None,
            "tx_hash": linkage["tx_hash"],
            "block_number": anchor.block_number if anchor else None,
            "anchor_status": anchor.anchor_status if anchor else None,
            "anchored_at": linkage["anchored_at"],
            "error_message": anchor.error_message if anchor else None,
        },
        "created_at": _to_iso(batch.created_at),
        "error_message": batch.error_message,
    }


@router.get("/bundles/{bundle_id}/ipfs-link")
def bundle_ipfs_link(
    bundle_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Bundle not found")

    ipfs_obj = db.query(IpfsObject).filter(IpfsObject.bundle_id == batch.id).first()
    cid = (batch.ipfs_cid or (ipfs_obj.ipfs_cid if ipfs_obj else None) or "").strip()
    if not cid:
        raise HTTPException(status_code=404, detail="No IPFS CID found for bundle")

    return {
        "bundle_id": str(batch.id),
        "shipment_id": str(batch.shipment_id),
        "ipfs_cid": cid,
        "tx_hash": batch.tx_hash,
        "gateway_url": f"https://ipfs.io/ipfs/{cid}",
    }
