from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
PYTHON = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

TRACKER_DEVICE_ID = "0cb901e3-6cf7-4be2-83f4-3a232a283e33"
VERIFIER_DEVICE_ID = "4fedec9d-eca7-428f-9803-d6728d874c54"
SHIPMENT_ID = "d8cb6561-7186-43b1-b4b3-f0925875c450"
LEG_ID = "b29e85bb-2bcc-4107-b614-d239932a0265"
VERIFIER_USER_ID = "a7110eff-cc43-4a64-a962-9d63ec8d46ee"


def wait_for_health(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=3)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Backend did not become healthy in time")


def seed_data(env: dict[str, str]) -> None:
    script = """
import uuid
from app.database import SessionLocal
from app.models import Device, Shipment, ShipmentLeg, User
from app.models.enums import DeviceStatus, ShipmentStatus, LegStatus, UserRole
from app.core.security import get_password_hash

db = SessionLocal()
try:
    tracker_id = uuid.UUID("0cb901e3-6cf7-4be2-83f4-3a232a283e33")
    verifier_device_id = uuid.UUID("4fedec9d-eca7-428f-9803-d6728d874c54")
    shipment_id = uuid.UUID("d8cb6561-7186-43b1-b4b3-f0925875c450")
    leg_id = uuid.UUID("b29e85bb-2bcc-4107-b614-d239932a0265")
    verifier_user_id = uuid.UUID("a7110eff-cc43-4a64-a962-9d63ec8d46ee")

    def ensure_user(email, name, password, role, user_id=None):
        user = db.query(User).filter(User.email == email).first()
        if user:
            return user
        user = User(
            id=user_id,
            email=email,
            name=name,
            password_hash=get_password_hash(password),
            role=role,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        return user

    ensure_user("factory.user001@gmail.com", "Factory User", "Pass@12345", UserRole.FACTORY)
    ensure_user("admin.user001@gmail.com", "Admin User", "Pass@12345", UserRole.ADMIN)
    ensure_user("verifier.user001@gmail.com", "Verifier User", "Pass@12345", UserRole.WAREHOUSE, verifier_user_id)

    if not db.query(Device).filter(Device.id == tracker_id).first():
        db.add(Device(
            id=tracker_id,
            device_uid="ESP32-TRACKER-001",
            model="ESP32 Tracker",
            firmware_version="0.1.0",
            battery_capacity_mAh=5000,
            status=DeviceStatus.ACTIVE,
        ))

    if not db.query(Device).filter(Device.id == verifier_device_id).first():
        db.add(Device(
            id=verifier_device_id,
            device_uid="ESP32-VERIFIER-001",
            model="ESP32 Verifier",
            firmware_version="0.1.0",
            battery_capacity_mAh=2000,
            status=DeviceStatus.ACTIVE,
        ))

    if not db.query(Shipment).filter(Shipment.id == shipment_id).first():
        db.add(Shipment(
            id=shipment_id,
            shipment_code="SHP-SMOKE-001",
            description="Local smoke flow shipment",
            origin="Factory",
            destination="Warehouse",
            status=ShipmentStatus.CREATED,
            device_id=tracker_id,
        ))

    if not db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first():
        db.add(ShipmentLeg(
            id=leg_id,
            shipment_id=shipment_id,
            leg_number=1,
            from_location="Factory",
            to_location="Warehouse",
            status=LegStatus.PENDING,
        ))

    db.commit()
    print("seed-ok")
finally:
    db.close()
"""
    subprocess.run([str(PYTHON), "-c", script], cwd=BACKEND_DIR, env=env, check=True)


def login(base_url: str, email: str, password: str) -> str:
    response = requests.post(
        f"{base_url}/api/v1/auth/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": email, "password": password},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def run_smoke(
    base_url: str,
    factory_token: str,
    admin_token: str,
    tracker_token: str,
    verifier_token: str,
) -> None:
    args = [
        sys.executable,
        str(ROOT / "iot" / "harness" / "smoke_flow.py"),
        "--base-url",
        base_url,
        "--read-base-url",
        "http://127.0.0.1:8001",
        "--shipment-id",
        SHIPMENT_ID,
        "--device-id",
        TRACKER_DEVICE_ID,
        "--device-uid",
        "ESP32-TRACKER-001",
        "--leg-id",
        LEG_ID,
        "--verifier-device-id",
        VERIFIER_DEVICE_ID,
        "--verifier-user-id",
        VERIFIER_USER_ID,
        "--device-token",
        tracker_token,
        "--verifier-token",
        verifier_token,
        "--user-token",
        factory_token,
        "--admin-token",
        admin_token,
        "--settle-seconds",
        "3",
        "--settle-timeout-seconds",
        "20",
        "--settle-poll-seconds",
        "1",
    ]
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    backend_base_url = "http://127.0.0.1:8001"
    bridge_base_url = "http://127.0.0.1:8081"
    smoke_db = BACKEND_DIR / "smoke_e2e.db"
    stream_suffix = uuid.uuid4().hex[:8]
    tracker_token = os.environ.get("SMOKE_TRACKER_TOKEN", "").strip()
    verifier_token = os.environ.get("SMOKE_VERIFIER_TOKEN", "").strip()
    if not tracker_token or not verifier_token:
        raise RuntimeError("SMOKE_TRACKER_TOKEN and SMOKE_VERIFIER_TOKEN must be set")
    if smoke_db.exists():
        smoke_db.unlink()

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": "sqlite:///./smoke_e2e.db",
            "APP_PROCESS_ROLE": "all",
            "TELEMETRY_PIPELINE_MODE": "dual",
            "REDIS_URL": "redis://default:EqttKrqy89YnMeixecd2QimWJ420D0Ur@redis-17517.c264.ap-south-1-1.ec2.cloud.redislabs.com:17517",
            "REDIS_TELEMETRY_STREAM": f"smoke_telemetry_stream_{stream_suffix}",
            "REDIS_CUSTODY_STREAM": f"smoke_custody_stream_{stream_suffix}",
            "REDIS_BUNDLE_READY_STREAM": f"smoke_bundle_ready_stream_{stream_suffix}",
            "REDIS_ANCHOR_REQUEST_STREAM": f"smoke_anchor_request_stream_{stream_suffix}",
            "REDIS_DEAD_LETTER_STREAM": f"smoke_dead_letter_stream_{stream_suffix}",
            "REDIS_TELEMETRY_CONSUMER_GROUP": f"smoke_batch_workers_{stream_suffix}",
            "REDIS_TELEMETRY_CONSUMER_NAME": f"smoke_worker_{stream_suffix}",
            "SECRET_KEY": "local-smoke-secret",
            "WS_REQUIRE_AUTH": "false",
            "INGEST_VERIFY_SIGNATURES": "false",
            "INGEST_DEVICE_AUTH_ENABLED": "true",
            "INGEST_VERIFIER_AUTH_ENABLED": "true",
            "INGEST_DEVICE_TOKENS_JSON": json.dumps({TRACKER_DEVICE_ID: tracker_token}),
            "INGEST_VERIFIER_TOKENS_JSON": json.dumps({VERIFIER_DEVICE_ID: verifier_token}),
            "BATCH_MIN_RECORDS": "3",
            "BATCH_MAX_WINDOW_SECONDS": "1",
            "BATCH_FORCE_ON_CUSTODY": "true",
            "IPFS_PIN_ENABLED": "false",
            "CHAIN_ANCHOR_ENABLED": "false",
            "CHAIN_INDEXER_ENABLED": "false",
            "AGENTIC_EAGER_STARTUP": "false",
            "OPENROUTER_API_KEY": "",
            "OPENAI_API_KEY": "",
            "OPENAI_BASE_URL": "",
        }
    )

    server = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd=BACKEND_DIR,
        env=env,
    )
    bridge_env = os.environ.copy()
    bridge_env.update(
        {
            "BRIDGE_BACKEND_BASE_URL": backend_base_url,
            "BRIDGE_HOST": "127.0.0.1",
            "BRIDGE_PORT": "8081",
            "BRIDGE_TIMEOUT_SECONDS": "20",
        }
    )
    bridge = subprocess.Popen(
        [str(PYTHON), str(ROOT / "iot" / "http_bridge" / "device_ingest_bridge.py")],
        cwd=ROOT,
        env=bridge_env,
    )

    try:
        wait_for_health(backend_base_url)
        wait_for_health(bridge_base_url)
        seed_data(env)
        factory_token = login(backend_base_url, "factory.user001@gmail.com", "Pass@12345")
        admin_token = login(backend_base_url, "admin.user001@gmail.com", "Pass@12345")
        run_smoke(bridge_base_url, factory_token, admin_token, tracker_token, verifier_token)
    finally:
        bridge.terminate()
        try:
            bridge.wait(timeout=10)
        except subprocess.TimeoutExpired:
            bridge.kill()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
