from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from ..models.user import User
from ..models.device import Device
from ..models.shipment import Shipment, ShipmentLeg
from ..models.sensor_log import SensorLog
from ..models.telemetry_event import TelemetryEvent
from ..models.custody_transfer import CustodyTransfer
from ..models.telemetry_batch import TelemetryBatch
from ..models.ipfs_object import IpfsObject
from ..models.chain_anchor import ChainAnchor
from ..models.enums import ShipmentStatus, LegStatus, UserRole
from ..schemas.shipment import Shipment as ShipmentSchema, ShipmentCreate, ShipmentUpdate, ShipmentWithDetails
from ..schemas.sensor_log import SensorLog as SensorLogSchema, SensorLogCreate, SensorStats as SensorStatsSchema
from ..database import get_db
import uuid
from collections.abc import Iterable
import enum as _enum
from ..dependencies import get_current_active_user, require_roles
from ..core.config import settings
from ..services.realtime import build_realtime_event, shipment_event_dispatcher
from ..services.sensor_stats_service import calculate_sensor_statistics
from ..services.telemetry_stream_service import telemetry_stream_service

router = APIRouter()


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}")


def _parse_dt(raw: str | None, field_name: str) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}")

@router.get("", response_model=List[ShipmentSchema], include_in_schema=False)
@router.get("/", response_model=List[ShipmentSchema])
def get_shipments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[ShipmentStatus] = Query(None),
    device_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all shipments with optional filtering"""
    query = db.query(Shipment)

    try:
        if status:
            query = query.filter(Shipment.status == status)

        if device_id:
            query = query.filter(Shipment.device_id == device_id)

        shipments = query.offset(skip).limit(limit).all()

        # SQLAlchemy model instances contain UUID objects which may
        # fail Pydantic response validation when the schema expects
        # strings. Convert UUID fields to strings for a safe response.
        serializable = []
        for s in shipments:
            # Use the instance __dict__ to build a plain dict and
            # strip SQLAlchemy internals.
            obj = {k: v for k, v in s.__dict__.items() if not k.startswith('_')}
            # Ensure common UUID fields are stringified
            for uuid_field in ("id", "device_id"):
                if uuid_field in obj and obj[uuid_field] is not None:
                    obj[uuid_field] = str(obj[uuid_field])
            serializable.append(obj)

        return serializable
    except Exception as exc:
        logging.exception('Error fetching shipments')
        # Return a clear 500 with brief detail for debugging in dev
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/", response_model=ShipmentSchema)
def create_shipment(
    shipment: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Create a new shipment"""
    # Check if shipment_code already exists
    existing_shipment = db.query(Shipment).filter(Shipment.shipment_code == shipment.shipment_code).first()
    if existing_shipment:
        raise HTTPException(status_code=400, detail="Shipment code already exists")

    device_uuid = _parse_uuid(shipment.device_id, "device_id")

    device = db.query(Device).filter(Device.id == device_uuid).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    payload = shipment.dict()
    payload["device_id"] = device_uuid
    db_shipment = Shipment(**payload)
    db.add(db_shipment)
    db.commit()
    db.refresh(db_shipment)
    return _to_plain(db_shipment)

@router.get("/{shipment_id}", response_model=ShipmentWithDetails)
def get_shipment(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific shipment with full details"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return _to_plain(shipment)

@router.put("/{shipment_id}", response_model=ShipmentSchema)
def update_shipment(
    shipment_id: uuid.UUID,
    shipment_update: ShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Update a shipment"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    previous_status = shipment.status
    update_data = shipment_update.dict(exclude_unset=True)
    if "device_id" in update_data and update_data["device_id"] is not None:
        update_data["device_id"] = _parse_uuid(update_data["device_id"], "device_id")
    for field, value in update_data.items():
        setattr(shipment, field, value)
    
    db.commit()
    db.refresh(shipment)

    if previous_status != shipment.status:
        shipment_payload = ShipmentSchema.model_validate(_to_plain(shipment)).model_dump(mode="json")
        shipment_event_dispatcher.publish(
            str(shipment_id),
            build_realtime_event(
                event="shipment.status_changed",
                shipment_id=str(shipment_id),
                data={
                    "previous_status": previous_status.value,
                    "current_status": shipment.status.value,
                    "shipment": shipment_payload,
                },
            ),
        )

    return _to_plain(shipment)

@router.post("/{shipment_id}/logs", response_model=List[SensorLogSchema])
def add_sensor_logs(
    shipment_id: uuid.UUID,
    logs: List[SensorLogCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add sensor logs to a shipment"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Create sensor logs
    db_logs = []
    for log_data in logs:
        log_payload = log_data.dict()
        log_payload["shipment_id"] = shipment_id
        db_log = SensorLog(**log_payload)
        db.add(db_log)
        db_logs.append(db_log)
    
    db.commit()
    serialized_logs = []
    for db_log in db_logs:
        db.refresh(db_log)
        log_payload = SensorLogSchema.model_validate(_to_plain(db_log)).model_dump(mode="json")
        telemetry_stream_service.publish_sensor_log(log_payload)
        serialized_logs.append(log_payload)
        shipment_event_dispatcher.publish(
            str(shipment_id),
            build_realtime_event(
                event="sensor_log.created",
                shipment_id=str(shipment_id),
                data={"log": log_payload},
            ),
        )

    return serialized_logs

@router.get("/{shipment_id}/logs", response_model=List[SensorLogSchema])
def get_sensor_logs(
    shipment_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get sensor logs for a specific shipment"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    logs = db.query(SensorLog).filter(SensorLog.shipment_id == shipment_id).offset(skip).limit(limit).all()
    return [_to_plain(l) for l in logs]


@router.get("/{shipment_id}/telemetry")
def get_shipment_telemetry(
    shipment_id: uuid.UUID,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Canonical telemetry timeline from telemetry_events; falls back to sensor_logs."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    from_dt = _parse_dt(from_ts, "from")
    to_dt = _parse_dt(to_ts, "to")

    q = db.query(TelemetryEvent).filter(TelemetryEvent.shipment_id == shipment_id)
    if from_dt is not None:
        q = q.filter(TelemetryEvent.ts >= from_dt)
    if to_dt is not None:
        q = q.filter(TelemetryEvent.ts <= to_dt)

    events = q.order_by(TelemetryEvent.ts.asc()).limit(limit).all()
    if events:
        out = []
        for e in events:
            metrics = e.metrics if isinstance(e.metrics, dict) else {}
            out.append(
                {
                    "event_id": e.event_id,
                    "ts": e.ts.isoformat() if e.ts else None,
                    "seq_no": e.seq_no,
                    "temperature_c": metrics.get("temperature_c"),
                    "humidity_pct": metrics.get("humidity_pct"),
                    "shock_g": metrics.get("shock_g"),
                    "light_lux": metrics.get("light_lux"),
                    "tilt_deg": metrics.get("tilt_deg"),
                    "battery_pct": metrics.get("battery_pct"),
                    "gps": e.gps if isinstance(e.gps, dict) else None,
                    "ingest_status": e.ingest_status,
                    "verification_status": e.verification_status,
                    "bundle_id": str(e.bundle_id) if e.bundle_id else None,
                    "payload_hash": e.payload_hash,
                }
            )
        return out

    legacy_q = db.query(SensorLog).filter(SensorLog.shipment_id == shipment_id)
    if from_dt is not None:
        legacy_q = legacy_q.filter(SensorLog.recorded_at >= from_dt)
    if to_dt is not None:
        legacy_q = legacy_q.filter(SensorLog.recorded_at <= to_dt)
    legacy_logs = legacy_q.order_by(SensorLog.recorded_at.asc()).limit(limit).all()
    return [
        {
            "event_id": str(l.id),
            "ts": l.recorded_at.isoformat() if l.recorded_at else None,
            "seq_no": None,
            "temperature_c": l.temperature,
            "humidity_pct": l.humidity,
            "shock_g": l.shock,
            "light_lux": None,
            "tilt_deg": l.tilt_angle,
            "battery_pct": None,
            "gps": {
                "lat": l.latitude,
                "lng": l.longitude,
                "speed_kmh": l.speed,
                "heading_deg": l.heading,
            },
            "ingest_status": "legacy",
            "verification_status": "legacy",
            "bundle_id": None,
            "payload_hash": l.hash_value,
        }
        for l in legacy_logs
    ]


@router.get("/{shipment_id}/custody")
def get_shipment_custody_timeline(
    shipment_id: uuid.UUID,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    from_dt = _parse_dt(from_ts, "from")
    to_dt = _parse_dt(to_ts, "to")

    q = db.query(CustodyTransfer).filter(CustodyTransfer.shipment_id == shipment_id)
    if from_dt is not None:
        q = q.filter(CustodyTransfer.ts >= from_dt)
    if to_dt is not None:
        q = q.filter(CustodyTransfer.ts <= to_dt)
    transfers = q.order_by(CustodyTransfer.ts.asc()).limit(limit).all()

    return [
        {
            "custody_event_id": t.custody_event_id,
            "shipment_id": str(t.shipment_id),
            "leg_id": str(t.leg_id) if t.leg_id else None,
            "verifier_user_id": str(t.verifier_user_id),
            "verifier_device_id": str(t.verifier_device_id),
            "ts": t.ts.isoformat() if t.ts else None,
            "fingerprint_result": t.fingerprint_result,
            "fingerprint_score": t.fingerprint_score,
            "digital_signer_address": t.digital_signer_address,
            "verification_status": t.verification_status,
            "ingest_status": t.ingest_status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in transfers
    ]


@router.get("/{shipment_id}/overview")
def get_shipment_overview(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    latest_batch = (
        db.query(TelemetryBatch)
        .filter(TelemetryBatch.shipment_id == shipment_id)
        .order_by(TelemetryBatch.created_at.desc())
        .first()
    )
    ipfs_obj = (
        db.query(IpfsObject).filter(IpfsObject.bundle_id == latest_batch.id).first()
        if latest_batch
        else None
    )
    anchor = (
        db.query(ChainAnchor).filter(ChainAnchor.bundle_id == latest_batch.id).first()
        if latest_batch
        else None
    )

    return {
        "shipment": _to_plain(shipment),
        "latest_bundle": (
            {
                "bundle_id": str(latest_batch.id),
                "status": latest_batch.status,
                "record_count": latest_batch.record_count,
                "batch_hash": latest_batch.batch_hash,
                "ipfs_cid": latest_batch.ipfs_cid or (ipfs_obj.ipfs_cid if ipfs_obj else None),
                "tx_hash": latest_batch.tx_hash or (anchor.tx_hash if anchor else None),
                "anchor_status": anchor.anchor_status if anchor else None,
                "anchored_at": latest_batch.anchored_at.isoformat() if latest_batch.anchored_at else None,
                "created_at": latest_batch.created_at.isoformat() if latest_batch.created_at else None,
            }
            if latest_batch
            else None
        ),
    }


@router.get("/{shipment_id}/sensor-stats", response_model=SensorStatsSchema)
def get_shipment_sensor_stats(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    stats = calculate_sensor_statistics(
        db,
        shipment_id=str(shipment_id),
        temperature_threshold=float(getattr(settings, "TEMPERATURE_THRESHOLD_C", 8.0)),
    )
    return {
        "shipment_id": str(shipment_id),
        "total_logs": stats["total_logs"],
        "temperature_sample_count": stats["temperature_sample_count"],
        "average_temperature": stats["average_temperature"],
        "min_temperature": stats["min_temperature"],
        "max_temperature": stats["max_temperature"],
        "max_shock": stats["max_shock"],
        "first_recorded_at": stats["first_recorded_at"],
        "last_recorded_at": stats["last_recorded_at"],
        "has_temperature_breach": stats["has_temperature_breach"],
    }

@router.post("/{shipment_id}/settle")
def settle_shipment(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Settle a shipment (mark as completed)"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    previous_status = shipment.status
    shipment.status = ShipmentStatus.COMPLETED
    
    # Complete all pending legs
    pending_legs = db.query(ShipmentLeg).filter(
        ShipmentLeg.shipment_id == shipment_id,
        ShipmentLeg.status != LegStatus.SETTLED
    ).all()
    
    for leg in pending_legs:
        leg.status = LegStatus.SETTLED
        leg.completed_at = datetime.now(timezone.utc)
    
    db.commit()

    if previous_status != ShipmentStatus.COMPLETED:
        shipment_event_dispatcher.publish(
            str(shipment_id),
            build_realtime_event(
                event="shipment.status_changed",
                shipment_id=str(shipment_id),
                data={
                    "previous_status": previous_status.value,
                    "current_status": ShipmentStatus.COMPLETED.value,
                },
            ),
        )

    shipment_event_dispatcher.publish(
        str(shipment_id),
        build_realtime_event(
            event="shipment.settled",
            shipment_id=str(shipment_id),
            data={
                "status": ShipmentStatus.COMPLETED.value,
                "settled_leg_ids": [str(leg.id) for leg in pending_legs],
                "settled_leg_count": len(pending_legs),
            },
        ),
    )

    return {"message": "Shipment settled successfully"}


def _to_plain(obj):
    """Recursively convert SQLAlchemy model instances, UUIDs and related
    objects into plain Python types suitable for JSON/Pydantic responses.
    """
    if obj is None:
        return None

    # Handle UUIDs
    if isinstance(obj, uuid.UUID):
        return str(obj)

    # Handle mappings/dicts
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}

    # Handle Enum instances by returning their value (e.g., 'created')
    if isinstance(obj, _enum.Enum):
        return obj.value

    # Handle iterables (lists, InstrumentedList, etc.) but not strings
    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        return [_to_plain(i) for i in obj]

    # Handle SQLAlchemy model instances by reading public attributes
    if hasattr(obj, '__dict__'):
        data = {}
        for k, v in obj.__dict__.items():
            if k.startswith('_'):
                continue
            data[k] = _to_plain(v)
        return data

    # Fallback to primitive types
    return obj
