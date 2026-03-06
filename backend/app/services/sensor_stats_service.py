from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.shipment import Shipment
from ..models.telemetry_event import TelemetryEvent


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

    query = db.query(TelemetryEvent)
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
        query = query.filter(TelemetryEvent.shipment_id.in_(shipment_ids))

    start_dt = _parse_datetime(start_time, "start_time")
    end_dt = _parse_datetime(end_time, "end_time")
    if start_dt is not None:
        query = query.filter(TelemetryEvent.ts >= start_dt)
    if end_dt is not None:
        query = query.filter(TelemetryEvent.ts <= end_dt)

    events = query.order_by(TelemetryEvent.ts.asc(), TelemetryEvent.created_at.asc()).all()
    temperature_values: list[float] = []
    shock_values: list[float] = []
    for event in events:
        metrics = event.metrics if isinstance(event.metrics, dict) else {}
        temperature = metrics.get("temperature_c")
        shock = metrics.get("shock_g")
        if isinstance(temperature, (int, float)):
            temperature_values.append(float(temperature))
        if isinstance(shock, (int, float)):
            shock_values.append(float(shock))

    total_logs = len(events)
    avg_temperature = (
        sum(temperature_values) / len(temperature_values)
        if temperature_values
        else None
    )
    min_temperature = min(temperature_values) if temperature_values else None
    max_temperature = max(temperature_values) if temperature_values else None
    max_shock = max(shock_values) if shock_values else None
    first_recorded_at = events[0].ts.isoformat() if events and events[0].ts is not None else None
    last_recorded_at = events[-1].ts.isoformat() if events and events[-1].ts is not None else None
    has_temperature_breach = any(value > temperature_threshold for value in temperature_values)

    shipment_ids_in_scope = [
        str(row[0])
        for row in query.with_entities(TelemetryEvent.shipment_id).distinct().limit(200).all()
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
        "total_logs": total_logs,
        "temperature_sample_count": len(temperature_values),
        "average_temperature": avg_temperature,
        "min_temperature": min_temperature,
        "max_temperature": max_temperature,
        "max_shock": max_shock,
        "first_recorded_at": first_recorded_at,
        "last_recorded_at": last_recorded_at,
        "has_temperature_breach": has_temperature_breach,
        "shipment_ids": shipment_ids_in_scope,
    }
