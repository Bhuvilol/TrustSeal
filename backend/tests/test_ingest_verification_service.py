from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from app.core.config import settings
from app.schemas.ingest import CustodyIngestRequest, GpsPayload, TelemetryIngestRequest
from app.services.ingest_verification_service import ingest_verification_service


def _build_valid_telemetry() -> TelemetryIngestRequest:
    event_id = str(uuid.uuid4())
    shipment_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    idempotency_key = str(uuid.uuid4())

    canonical = {
        "event_id": event_id,
        "shipment_id": shipment_id,
        "device_id": device_id,
        "device_uid": "dev-001",
        "ts": ts,
        "seq_no": 1,
        "temperature_c": 4.2,
        "humidity_pct": 64.1,
        "shock_g": 0.2,
        "light_lux": 23.0,
        "tilt_deg": 1.2,
        "gps": {"lat": 12.34, "lng": 56.78, "speed_kmh": 18.3, "heading_deg": 90.0},
        "battery_pct": 84.0,
        "network_type": "lte",
        "firmware_version": "1.0.0",
        "sig_alg": "ecdsa-secp256k1",
        "pubkey_id": "pk-1",
        "idempotency_key": idempotency_key,
    }
    payload_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return TelemetryIngestRequest(
        event_id=event_id,
        shipment_id=shipment_id,
        device_id=device_id,
        device_uid="dev-001",
        ts=ts,
        seq_no=1,
        temperature_c=4.2,
        humidity_pct=64.1,
        shock_g=0.2,
        light_lux=23.0,
        tilt_deg=1.2,
        gps=GpsPayload(lat=12.34, lng=56.78, speed_kmh=18.3, heading_deg=90.0),
        battery_pct=84.0,
        network_type="lte",
        firmware_version="1.0.0",
        hash_alg="sha256",
        payload_hash=payload_hash,
        sig_alg="ecdsa-secp256k1",
        signature="sig-abc",
        pubkey_id="pk-1",
        idempotency_key=idempotency_key,
    )


def test_verify_telemetry_accepts_valid_packet() -> None:
    payload = _build_valid_telemetry()
    result = ingest_verification_service.verify_telemetry(payload)
    assert result.ok is True
    assert result.error_code is None
    assert result.normalized_ts is not None


def test_verify_telemetry_rejects_hash_mismatch() -> None:
    payload = _build_valid_telemetry()
    payload.payload_hash = "deadbeef"
    result = ingest_verification_service.verify_telemetry(payload)
    assert result.ok is False
    assert result.error_code == "INVALID_PAYLOAD_HASH"


def test_verify_custody_requires_fingerprint_match() -> None:
    payload = CustodyIngestRequest(
        custody_event_id=str(uuid.uuid4()),
        shipment_id=str(uuid.uuid4()),
        leg_id=str(uuid.uuid4()),
        verifier_device_id=str(uuid.uuid4()),
        verifier_user_id=str(uuid.uuid4()),
        ts=datetime.now(timezone.utc).isoformat(),
        fingerprint_result="no_match",
        fingerprint_score=0.4,
        fingerprint_template_id="tmp-1",
        digital_signer_address="0x0000000000000000000000000000000000000000",
        approval_message_hash="a" * 64,
        signature="sig",
        sig_alg="ecdsa-secp256k1",
        idempotency_key=str(uuid.uuid4()),
    )
    result = ingest_verification_service.verify_custody(payload)
    assert result.ok is False
    assert result.error_code == "FINGERPRINT_NOT_MATCHED"


def test_verify_telemetry_signature_when_enabled() -> None:
    previous_toggle = settings.INGEST_VERIFY_SIGNATURES
    previous_registry = settings.INGEST_DEVICE_PUBLIC_KEYS_JSON
    try:
        key = ec.generate_private_key(ec.SECP256R1())
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        pubkey_id = "test-device-key-1"

        event_id = str(uuid.uuid4())
        shipment_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        idempotency_key = str(uuid.uuid4())

        canonical = {
            "event_id": event_id,
            "shipment_id": shipment_id,
            "device_id": device_id,
            "device_uid": "dev-001",
            "ts": ts,
            "seq_no": 4,
            "temperature_c": 4.2,
            "humidity_pct": 64.1,
            "shock_g": 0.2,
            "light_lux": 23.0,
            "tilt_deg": 1.2,
            "gps": None,
            "battery_pct": 84.0,
            "network_type": "cellular",
            "firmware_version": "1.0.0",
            "sig_alg": "ecdsa-secp256r1",
            "pubkey_id": pubkey_id,
            "idempotency_key": idempotency_key,
        }
        payload_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        signature = key.sign(bytes.fromhex(payload_hash), ec.ECDSA(Prehashed(hashes.SHA256())))
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        payload = TelemetryIngestRequest(
            event_id=event_id,
            shipment_id=shipment_id,
            device_id=device_id,
            device_uid="dev-001",
            ts=ts,
            seq_no=4,
            temperature_c=4.2,
            humidity_pct=64.1,
            shock_g=0.2,
            light_lux=23.0,
            tilt_deg=1.2,
            gps=None,
            battery_pct=84.0,
            network_type="cellular",
            firmware_version="1.0.0",
            hash_alg="sha256",
            payload_hash=payload_hash,
            sig_alg="ecdsa-secp256r1",
            signature=signature_b64,
            pubkey_id=pubkey_id,
            idempotency_key=idempotency_key,
        )

        settings.INGEST_VERIFY_SIGNATURES = True
        settings.INGEST_DEVICE_PUBLIC_KEYS_JSON = json.dumps({pubkey_id: pub_pem})

        result = ingest_verification_service.verify_telemetry(payload)
        assert result.ok is True
    finally:
        settings.INGEST_VERIFY_SIGNATURES = previous_toggle
        settings.INGEST_DEVICE_PUBLIC_KEYS_JSON = previous_registry


def test_verify_custody_signature_and_hash_when_enabled() -> None:
    previous_toggle = settings.INGEST_VERIFY_SIGNATURES
    previous_registry = settings.INGEST_VERIFIER_PUBLIC_KEYS_JSON
    try:
        key = ec.generate_private_key(ec.SECP256R1())
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        verifier_device_id = str(uuid.uuid4())
        custody_event_id = str(uuid.uuid4())
        shipment_id = str(uuid.uuid4())
        leg_id = str(uuid.uuid4())
        verifier_user_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()

        canonical = {
            "custody_event_id": custody_event_id,
            "shipment_id": shipment_id,
            "leg_id": leg_id,
            "verifier_device_id": verifier_device_id,
            "verifier_user_id": verifier_user_id,
            "ts": ts,
            "fingerprint_result": "match",
            "fingerprint_score": 92.1,
            "fingerprint_template_id": "7",
            "digital_signer_address": "0x0000000000000000000000000000000000000000",
            "sig_alg": "ecdsa-secp256r1",
            "idempotency_key": custody_event_id,
        }
        approval_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        signature = key.sign(bytes.fromhex(approval_hash), ec.ECDSA(Prehashed(hashes.SHA256())))
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        payload = CustodyIngestRequest(
            custody_event_id=custody_event_id,
            shipment_id=shipment_id,
            leg_id=leg_id,
            verifier_device_id=verifier_device_id,
            verifier_user_id=verifier_user_id,
            ts=ts,
            fingerprint_result="match",
            fingerprint_score=92.1,
            fingerprint_template_id="7",
            digital_signer_address="0x0000000000000000000000000000000000000000",
            approval_message_hash=approval_hash,
            signature=signature_b64,
            sig_alg="ecdsa-secp256r1",
            idempotency_key=custody_event_id,
        )

        settings.INGEST_VERIFY_SIGNATURES = True
        settings.INGEST_VERIFIER_PUBLIC_KEYS_JSON = json.dumps({verifier_device_id: pub_pem})

        result = ingest_verification_service.verify_custody(payload)
        assert result.ok is True
    finally:
        settings.INGEST_VERIFY_SIGNATURES = previous_toggle
        settings.INGEST_VERIFIER_PUBLIC_KEYS_JSON = previous_registry
