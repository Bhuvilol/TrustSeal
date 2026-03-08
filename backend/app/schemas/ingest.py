from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GpsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    speed_kmh: float | None = Field(default=None, ge=0.0, le=500.0)
    heading_deg: float | None = Field(default=None, ge=0.0, le=360.0)


class TelemetryIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    shipment_id: str
    device_id: str
    device_uid: str | None = Field(default=None, min_length=1, max_length=128)
    ts: str
    seq_no: int = Field(ge=0)

    temperature_c: float | None = Field(default=None, ge=-80.0, le=120.0)
    humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    shock_g: float | None = Field(default=None, ge=0.0, le=50.0)
    light_lux: float | None = Field(default=None, ge=0.0, le=200000.0)
    tilt_deg: float | None = Field(default=None, ge=-180.0, le=180.0)
    gps: GpsPayload | None = None

    battery_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    network_type: Literal["cellular", "lte", "2g", "wifi", "ethernet"] | None = None
    firmware_version: str | None = Field(default=None, min_length=1, max_length=64)
    event_kind: Literal["periodic", "alert"] | None = None
    alert_reason: Literal["light", "temperature", "humidity", "shock", "tilt"] | None = None

    hash_alg: Literal["sha256"]
    payload_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    sig_alg: Literal["ecdsa-secp256r1", "ecdsa-secp256k1"]
    signature: str = Field(min_length=1, max_length=2048)
    pubkey_id: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=256)


class CustodyIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custody_event_id: str
    shipment_id: str
    leg_id: str
    verifier_device_id: str
    verifier_user_id: str
    ts: str

    fingerprint_result: Literal["match", "no_match", "error"]
    fingerprint_score: float | None = Field(default=None, ge=0.0, le=100.0)
    fingerprint_template_id: str | None = Field(default=None, min_length=1, max_length=128)

    digital_signer_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    approval_message_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    signature: str = Field(min_length=1, max_length=2048)
    sig_alg: Literal["ecdsa-secp256r1", "ecdsa-secp256k1"]
    idempotency_key: str = Field(min_length=1, max_length=256)
