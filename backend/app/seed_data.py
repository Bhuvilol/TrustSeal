"""
Seed data for TrustSeal IoT application.
This script creates initial dummy data for testing purposes.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from .core.security import get_password_hash
from .database import SessionLocal, engine
from .models import CustodyCheckpoint, Device, SensorLog, Shipment, ShipmentLeg, User
from .models.enums import DeviceStatus, LegStatus, ShipmentStatus, UserRole


def seed_database() -> None:
    """Seed the database with initial dummy data."""
    from .database import Base

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Clear existing data in child -> parent order.
        db.query(CustodyCheckpoint).delete()
        db.query(SensorLog).delete()
        db.query(ShipmentLeg).delete()
        db.query(Shipment).delete()
        db.query(Device).delete()
        db.query(User).delete()
        db.commit()

        print("Creating users...")
        users = [
            User(
                name="Administrator",
                email="admin@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.ADMIN,
                is_verified=True,
            ),
            User(
                name="Factory Manager",
                email="factory@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.FACTORY,
                is_verified=True,
            ),
            User(
                name="Warehouse Manager",
                email="warehouse@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.WAREHOUSE,
                is_verified=True,
            ),
            User(
                name="Customer",
                email="customer@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.CUSTOMER,
                is_verified=True,
            ),
        ]
        db.add_all(users)
        db.commit()
        for user in users:
            db.refresh(user)

        print("Creating device...")
        device = Device(
            device_uid="DEV-2024-001",
            model="TrustSeal-T1000",
            firmware_version="1.2.3",
            battery_capacity_mAh=5000,
            status=DeviceStatus.ACTIVE,
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        print("Creating shipment...")
        shipment = Shipment(
            shipment_code="SHP-2024-001",
            description="Electronics components shipment",
            origin="Factory A, Shenzhen, China",
            destination="Warehouse B, New York, USA",
            status=ShipmentStatus.IN_TRANSIT,
            device_id=device.id,
        )
        db.add(shipment)
        db.commit()
        db.refresh(shipment)

        print("Creating shipment legs...")
        now = datetime.now(timezone.utc)
        legs = [
            ShipmentLeg(
                shipment_id=shipment.id,
                leg_number=1,
                from_location="Factory A, Shenzhen, China",
                to_location="Port of Shanghai, China",
                status=LegStatus.SETTLED,
                started_at=now - timedelta(days=5),
                completed_at=now - timedelta(days=4),
            ),
            ShipmentLeg(
                shipment_id=shipment.id,
                leg_number=2,
                from_location="Port of Shanghai, China",
                to_location="Port of New York, USA",
                status=LegStatus.IN_PROGRESS,
                started_at=now - timedelta(days=3),
            ),
        ]
        db.add_all(legs)
        db.commit()
        for leg in legs:
            db.refresh(leg)

        print("Creating sensor logs...")
        base_time = now - timedelta(hours=48)
        for i in range(20):
            log_time = base_time + timedelta(hours=i * 2.4)
            temperature = round(20 + random.uniform(-5, 15), 2)
            humidity = round(40 + random.uniform(-10, 30), 2)
            shock = round(random.uniform(0, 2), 3)
            light_exposure = random.choice([True, False])
            tilt_angle = round(random.uniform(0, 45), 2)
            hash_value = f"hash_{i}_{uuid.uuid4().hex[:8]}"

            db.add(
                SensorLog(
                    shipment_id=shipment.id,
                    temperature=temperature,
                    humidity=humidity,
                    shock=shock,
                    light_exposure=light_exposure,
                    tilt_angle=tilt_angle,
                    recorded_at=log_time,
                    hash_value=hash_value,
                )
            )
        db.commit()

        print("Creating custody checkpoints...")
        checkpoints = [
            CustodyCheckpoint(
                shipment_id=shipment.id,
                leg_id=legs[0].id,
                verified_by=users[0].id,
                biometric_verified=True,
                timestamp=now - timedelta(days=5),
                blockchain_tx_hash=f"0x{uuid.uuid4().hex[:64]}",
                merkle_root_hash=f"merkle_{uuid.uuid4().hex[:32]}",
            ),
            CustodyCheckpoint(
                shipment_id=shipment.id,
                leg_id=legs[0].id,
                verified_by=users[1].id,
                biometric_verified=True,
                timestamp=now - timedelta(days=4),
                blockchain_tx_hash=f"0x{uuid.uuid4().hex[:64]}",
                merkle_root_hash=f"merkle_{uuid.uuid4().hex[:32]}",
            ),
        ]
        db.add_all(checkpoints)
        db.commit()

        print("\nDatabase seeded successfully!")
        print(f"Created {len(users)} users")
        print("Created 1 device")
        print("Created 1 shipment")
        print(f"Created {len(legs)} shipment legs")
        print("Created 20 sensor logs")
        print(f"Created {len(checkpoints)} custody checkpoints")

        print("\nLogin credentials:")
        print("Factory Manager: factory@trustseal.io / pass123")
        print("Warehouse Manager: warehouse@trustseal.io / pass123")
        print("Customer: customer@trustseal.io / pass123")
        print("Administrator: admin@trustseal.io / pass123")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
