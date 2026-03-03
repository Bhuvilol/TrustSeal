"""
Append-only seed for TrustSeal IoT.

Creates (if missing) a demo Device + Shipment + Legs and appends SensorLog rows
with latitude/longitude so the live map has a route to render.

Usage (from backend/):
  python -m app.seed_append_data
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect

from .database import SessionLocal
from .models import Device, SensorLog, Shipment, ShipmentLeg
from .models.enums import DeviceStatus, LegStatus, ShipmentStatus


def _require_sensor_log_geo_columns() -> None:
    """Fail fast with a clear message if the DB schema is not migrated."""
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        cols = {col["name"] for col in inspector.get_columns("sensor_logs")}
        required = {"latitude", "longitude", "speed", "heading"}
        missing = sorted(required - cols)
        if missing:
            raise RuntimeError(
                "sensor_logs is missing columns: "
                + ", ".join(missing)
                + ". Run: python -m alembic upgrade head"
            )
    finally:
        db.close()


def seed_append_data() -> None:
    _require_sensor_log_geo_columns()

    db = SessionLocal()
    try:
        device_uid = "DEV-LIVE-TELEMETRY-001"
        shipment_code = "SHP-LIVE-TELEMETRY-001"
        seed_prefix = f"append_seed_{shipment_code}_"

        device = db.query(Device).filter(Device.device_uid == device_uid).first()
        if not device:
            device = Device(
                device_uid=device_uid,
                model="TrustSeal-T1000",
                firmware_version="2.0.0-demo",
                battery_capacity_mAh=5200,
                status=DeviceStatus.ACTIVE,
            )
            db.add(device)
            db.commit()
            db.refresh(device)

        shipment = db.query(Shipment).filter(Shipment.shipment_code == shipment_code).first()
        if not shipment:
            shipment = Shipment(
                shipment_code=shipment_code,
                description="Live telemetry demo shipment (append seed)",
                origin="Port of Long Beach, CA",
                destination="Ontario Distribution Center, CA",
                status=ShipmentStatus.IN_TRANSIT,
                device_id=device.id,
            )
            db.add(shipment)
            db.commit()
            db.refresh(shipment)

        legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shipment.id).all()
        if not legs:
            now = datetime.now(timezone.utc)
            leg1 = ShipmentLeg(
                shipment_id=shipment.id,
                leg_number=1,
                from_location="Port of Long Beach, CA",
                to_location="Los Angeles Hub, CA",
                status=LegStatus.SETTLED,
                started_at=now - timedelta(hours=4),
                completed_at=now - timedelta(hours=3),
            )
            leg2 = ShipmentLeg(
                shipment_id=shipment.id,
                leg_number=2,
                from_location="Los Angeles Hub, CA",
                to_location="Ontario Distribution Center, CA",
                status=LegStatus.IN_PROGRESS,
                started_at=now - timedelta(hours=3),
            )
            db.add_all([leg1, leg2])
            db.commit()

        existing = (
            db.query(SensorLog)
            .filter(SensorLog.shipment_id == shipment.id)
            .filter(SensorLog.hash_value.like(f"{seed_prefix}%"))
            .count()
        )

        points = 40
        if existing >= points:
            print(f"Append seed already present: shipment={shipment_code} sensor_logs={existing}")
            return

        start_lat, start_lon = 33.7361, -118.2923  # Long Beach
        end_lat, end_lon = 34.0633, -117.6509  # Ontario, CA

        now = datetime.now(timezone.utc) - timedelta(minutes=(points - 1) * 2)
        for i in range(existing, points):
            t = i / max(1, points - 1)
            latitude = start_lat + (end_lat - start_lat) * t
            longitude = start_lon + (end_lon - start_lon) * t

            # Simple demo speed/heading values.
            speed = 45 + 10 * random.random()
            heading = 80 + 10 * random.random()

            log_time = now + timedelta(minutes=i * 2)

            db.add(
                SensorLog(
                    shipment_id=shipment.id,
                    temperature=round(7.0 + random.uniform(-1.5, 1.5), 2),
                    humidity=round(45.0 + random.uniform(-6, 6), 2),
                    shock=round(random.uniform(0, 2), 3),
                    light_exposure=random.choice([True, False]),
                    tilt_angle=round(random.uniform(0, 45), 2),
                    latitude=round(latitude, 6),
                    longitude=round(longitude, 6),
                    speed=round(speed, 2),
                    heading=round(heading, 2),
                    recorded_at=log_time,
                    hash_value=f"{seed_prefix}{i}",
                )
            )

        db.commit()
        print(f"Appended seed: shipment={shipment_code} device={device_uid} new_logs={points - existing}")
        print(f"Open shipment details: /shipments/{shipment.id}")
    except Exception as exc:
        db.rollback()
        raise RuntimeError(f"Append seed failed: {exc}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    seed_append_data()

