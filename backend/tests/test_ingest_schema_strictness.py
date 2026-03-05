from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.ingest import CustodyIngestRequest, TelemetryIngestRequest


def _valid_telemetry_payload() -> dict:
    event_id = str(uuid.uuid4())
    return {
        "event_id": event_id,
        "shipment_id": str(uuid.uuid4()),
        "device_id": str(uuid.uuid4()),
        "device_uid": "tracker-001",
        "ts": datetime.now(timezone.utc).isoformat(),
        "seq_no": 1,
        "temperature_c": 5.1,
        "humidity_pct": 66.0,
        "shock_g": 0.2,
        "light_lux": 42.0,
        "tilt_deg": 1.3,
        "gps": None,
        "battery_pct": 88.0,
        "network_type": "cellular",
        "firmware_version": "1.0.0",
        "hash_alg": "sha256",
        "payload_hash": "a" * 64,
        "sig_alg": "ecdsa-secp256r1",
        "signature": "signature-blob",
        "pubkey_id": "pk-1",
        "idempotency_key": event_id,
    }


def _valid_custody_payload() -> dict:
    custody_event_id = str(uuid.uuid4())
    return {
        "custody_event_id": custody_event_id,
        "shipment_id": str(uuid.uuid4()),
        "leg_id": str(uuid.uuid4()),
        "verifier_device_id": str(uuid.uuid4()),
        "verifier_user_id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "fingerprint_result": "match",
        "fingerprint_score": 91.2,
        "fingerprint_template_id": "3",
        "digital_signer_address": "0x0000000000000000000000000000000000000000",
        "approval_message_hash": "b" * 64,
        "signature": "signature-blob",
        "sig_alg": "ecdsa-secp256r1",
        "idempotency_key": custody_event_id,
    }


def test_telemetry_schema_rejects_unknown_fields() -> None:
    payload = _valid_telemetry_payload()
    payload["unexpected"] = "not-allowed"
    with pytest.raises(ValidationError):
        TelemetryIngestRequest(**payload)


def test_telemetry_schema_rejects_invalid_hash_shape() -> None:
    payload = _valid_telemetry_payload()
    payload["payload_hash"] = "deadbeef"
    with pytest.raises(ValidationError):
        TelemetryIngestRequest(**payload)


def test_custody_schema_rejects_bad_signer_address() -> None:
    payload = _valid_custody_payload()
    payload["digital_signer_address"] = "0xabc"
    with pytest.raises(ValidationError):
        CustodyIngestRequest(**payload)


def test_custody_schema_rejects_out_of_range_score() -> None:
    payload = _valid_custody_payload()
    payload["fingerprint_score"] = 150.0
    with pytest.raises(ValidationError):
        CustodyIngestRequest(**payload)
