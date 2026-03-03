from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.sensor_log import SensorLog
from ..models.shipment import Shipment


def _parse_uuid(value: Optional[str], field_name: str) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


def _parse_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None

    normalized = str(value).strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


def _shipment_ids_for_scope(
    db: Session,
    shipment_id: Optional[str],
    shipment_code: Optional[str],
    device_id: Optional[str],
) -> Optional[List[uuid.UUID]]:
    shipment_uuid = _parse_uuid(shipment_id, "shipment_id")
    device_uuid = _parse_uuid(device_id, "device_id")

    has_filters = bool(shipment_uuid or shipment_code or device_uuid)
    if not has_filters:
        return None

    query = db.query(Shipment.id)
    if shipment_uuid:
        query = query.filter(Shipment.id == shipment_uuid)
    if shipment_code:
        query = query.filter(Shipment.shipment_code.ilike(f"%{shipment_code.strip()}%"))
    if device_uuid:
        query = query.filter(Shipment.device_id == device_uuid)

    return [row[0] for row in query.all()]


def calculate_sensor_statistics(
    db: Session,
    *,
    shipment_id: Optional[str] = None,
    shipment_code: Optional[str] = None,
    device_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    temperature_threshold: float = 8.0,
) -> Dict[str, Any]:
    shipment_ids = _shipment_ids_for_scope(
        db,
        shipment_id=shipment_id,
        shipment_code=shipment_code,
        device_id=device_id,
    )

    query = db.query(SensorLog)
    if shipment_ids is not None:
        if not shipment_ids:
            return {
                "filters": {
                    "shipment_id": shipment_id,
                    "shipment_code": shipment_code,
                    "device_id": device_id,
                    "start_time": start_time,
                    "end_time": end_time,
                },
                "total_logs": 0,
                "temperature_sample_count": 0,
                "average_temperature": None,
                "min_temperature": None,
                "max_temperature": None,
                "max_shock": None,
                "first_recorded_at": None,
                "last_recorded_at": None,
                "has_temperature_breach": False,
                "shipment_ids": [],
            }
        query = query.filter(SensorLog.shipment_id.in_(shipment_ids))

    start_dt = _parse_datetime(start_time, "start_time")
    end_dt = _parse_datetime(end_time, "end_time")
    if start_dt is not None:
        query = query.filter(SensorLog.recorded_at >= start_dt)
    if end_dt is not None:
        query = query.filter(SensorLog.recorded_at <= end_dt)

    aggregate = query.with_entities(
        func.count(SensorLog.id),
        func.count(SensorLog.temperature),
        func.avg(SensorLog.temperature),
        func.min(SensorLog.temperature),
        func.max(SensorLog.temperature),
        func.max(SensorLog.shock),
        func.min(SensorLog.recorded_at),
        func.max(SensorLog.recorded_at),
    ).one()

    has_temperature_breach = (
        query.filter(SensorLog.temperature.isnot(None), SensorLog.temperature > temperature_threshold)
        .limit(1)
        .count()
        > 0
    )

    shipment_ids_in_scope = [
        str(row[0])
        for row in query.with_entities(SensorLog.shipment_id).distinct().limit(200).all()
        if row[0] is not None
    ]

    return {
        "filters": {
            "shipment_id": shipment_id,
            "shipment_code": shipment_code,
            "device_id": device_id,
            "start_time": start_time,
            "end_time": end_time,
        },
        "total_logs": int(aggregate[0] or 0),
        "temperature_sample_count": int(aggregate[1] or 0),
        "average_temperature": float(aggregate[2]) if aggregate[2] is not None else None,
        "min_temperature": float(aggregate[3]) if aggregate[3] is not None else None,
        "max_temperature": float(aggregate[4]) if aggregate[4] is not None else None,
        "max_shock": float(aggregate[5]) if aggregate[5] is not None else None,
        "first_recorded_at": aggregate[6].isoformat() if aggregate[6] is not None else None,
        "last_recorded_at": aggregate[7].isoformat() if aggregate[7] is not None else None,
        "has_temperature_breach": has_temperature_breach,
        "shipment_ids": shipment_ids_in_scope,
    }
