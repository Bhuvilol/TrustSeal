from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from ..core.config import settings
from ..schemas.ingest import CustodyIngestRequest, TelemetryIngestRequest


@dataclass(slots=True)
class VerificationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    normalized_ts: datetime | None = None


class IngestVerificationService:
    def verify_telemetry(self, payload: TelemetryIngestRequest) -> VerificationResult:
        try:
            uuid.UUID(payload.event_id)
            uuid.UUID(payload.shipment_id)
            uuid.UUID(payload.device_id)
        except (TypeError, ValueError):
            return VerificationResult(ok=False, error_code="INVALID_UUID", message="Invalid UUID in telemetry payload")

        ts = self._parse_ts(payload.ts)
        if ts is None:
            return VerificationResult(ok=False, error_code="INVALID_TIMESTAMP", message="Invalid telemetry timestamp")

        hash_valid = self._verify_payload_hash_telemetry(payload)
        if not hash_valid:
            return VerificationResult(ok=False, error_code="INVALID_PAYLOAD_HASH", message="Telemetry payload hash mismatch")

        if not payload.signature.strip():
            return VerificationResult(ok=False, error_code="INVALID_SIGNATURE", message="Missing telemetry signature")

        if settings.INGEST_VERIFY_SIGNATURES:
            sig_valid, sig_error = self._verify_telemetry_signature(payload)
            if not sig_valid:
                return VerificationResult(
                    ok=False,
                    error_code=sig_error or "INVALID_SIGNATURE",
                    message="Telemetry signature verification failed",
                )

        return VerificationResult(ok=True, normalized_ts=ts)

    def verify_custody(self, payload: CustodyIngestRequest) -> VerificationResult:
        try:
            uuid.UUID(payload.custody_event_id)
            uuid.UUID(payload.shipment_id)
            uuid.UUID(payload.leg_id)
            uuid.UUID(payload.verifier_device_id)
            uuid.UUID(payload.verifier_user_id)
        except (TypeError, ValueError):
            return VerificationResult(ok=False, error_code="INVALID_UUID", message="Invalid UUID in custody payload")

        ts = self._parse_ts(payload.ts)
        if ts is None:
            return VerificationResult(ok=False, error_code="INVALID_TIMESTAMP", message="Invalid custody timestamp")

        if payload.fingerprint_result != "match":
            return VerificationResult(
                ok=False,
                error_code="FINGERPRINT_NOT_MATCHED",
                message="Custody verification requires fingerprint_result=match",
            )

        if not payload.signature.strip():
            return VerificationResult(ok=False, error_code="INVALID_SIGNATURE", message="Missing custody signature")

        if not payload.approval_message_hash.strip():
            return VerificationResult(
                ok=False,
                error_code="INVALID_APPROVAL_HASH",
                message="Missing custody approval_message_hash",
            )

        approval_hash_valid = self._verify_custody_approval_hash(payload)
        if not approval_hash_valid:
            return VerificationResult(
                ok=False,
                error_code="INVALID_APPROVAL_HASH",
                message="Custody approval_message_hash mismatch",
            )

        if settings.INGEST_VERIFY_SIGNATURES:
            sig_valid, sig_error = self._verify_custody_signature(payload)
            if not sig_valid:
                return VerificationResult(
                    ok=False,
                    error_code=sig_error or "INVALID_SIGNATURE",
                    message="Custody signature verification failed",
                )

        return VerificationResult(ok=True, normalized_ts=ts)

    def _parse_ts(self, value: str) -> datetime | None:
        raw = (value or "").strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None

    def _verify_payload_hash_telemetry(self, payload: TelemetryIngestRequest) -> bool:
        if payload.hash_alg.lower() != "sha256":
            return False
        canonical: dict[str, Any] = {
            "event_id": payload.event_id,
            "shipment_id": payload.shipment_id,
            "device_id": payload.device_id,
            "device_uid": payload.device_uid,
            "ts": payload.ts,
            "seq_no": payload.seq_no,
            "temperature_c": payload.temperature_c,
            "humidity_pct": payload.humidity_pct,
            "shock_g": payload.shock_g,
            "light_lux": payload.light_lux,
            "tilt_deg": payload.tilt_deg,
            "gps": payload.gps.model_dump() if payload.gps else None,
            "battery_pct": payload.battery_pct,
            "network_type": payload.network_type,
            "firmware_version": payload.firmware_version,
            "sig_alg": payload.sig_alg,
            "pubkey_id": payload.pubkey_id,
            "idempotency_key": payload.idempotency_key,
        }
        wire = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        computed = hashlib.sha256(wire).hexdigest()
        if computed == payload.payload_hash.lower():
            return True

        # Legacy Arduino tracker compatibility:
        # earlier firmware hashed the same semantic payload in insertion order
        # rather than backend-sorted canonical order. Accept both to keep
        # deployed tracker firmware interoperable.
        legacy_canonical: dict[str, Any] = {
            "battery_pct": payload.battery_pct,
            "device_id": payload.device_id,
            "device_uid": payload.device_uid,
            "event_id": payload.event_id,
            "firmware_version": payload.firmware_version,
            "gps": payload.gps.model_dump() if payload.gps else None,
            "idempotency_key": payload.idempotency_key,
            "light_lux": payload.light_lux,
            "network_type": payload.network_type,
            "pubkey_id": payload.pubkey_id,
            "seq_no": payload.seq_no,
            "shipment_id": payload.shipment_id,
            "sig_alg": payload.sig_alg,
            "ts": payload.ts,
            "humidity_pct": payload.humidity_pct,
            "temperature_c": payload.temperature_c,
            "shock_g": payload.shock_g,
            "tilt_deg": payload.tilt_deg,
        }
        legacy_wire = json.dumps(legacy_canonical, separators=(",", ":")).encode("utf-8")
        legacy_computed = hashlib.sha256(legacy_wire).hexdigest()
        return legacy_computed == payload.payload_hash.lower()

    def _verify_custody_approval_hash(self, payload: CustodyIngestRequest) -> bool:
        canonical: dict[str, Any] = {
            "custody_event_id": payload.custody_event_id,
            "shipment_id": payload.shipment_id,
            "leg_id": payload.leg_id,
            "verifier_device_id": payload.verifier_device_id,
            "verifier_user_id": payload.verifier_user_id,
            "ts": payload.ts,
            "fingerprint_result": payload.fingerprint_result,
            "fingerprint_score": payload.fingerprint_score,
            "fingerprint_template_id": payload.fingerprint_template_id,
            "digital_signer_address": payload.digital_signer_address,
            "sig_alg": payload.sig_alg,
            "idempotency_key": payload.idempotency_key,
        }
        wire = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        computed = hashlib.sha256(wire).hexdigest()
        return computed == payload.approval_message_hash.lower()

    def _verify_telemetry_signature(self, payload: TelemetryIngestRequest) -> tuple[bool, str | None]:
        pubkey = self._load_public_key_from_device_registry(payload.pubkey_id)
        if pubkey is None:
            return False, "UNKNOWN_PUBKEY"
        return self._verify_signature_over_digest(pubkey, payload.payload_hash, payload.signature)

    def _verify_custody_signature(self, payload: CustodyIngestRequest) -> tuple[bool, str | None]:
        pubkey = self._load_public_key_from_verifier_registry(payload.verifier_device_id)
        if pubkey is None:
            return False, "UNKNOWN_PUBKEY"
        return self._verify_signature_over_digest(pubkey, payload.approval_message_hash, payload.signature)

    def _verify_signature_over_digest(
        self,
        public_key_pem: str,
        digest_hex: str,
        signature_b64: str,
    ) -> tuple[bool, str | None]:
        try:
            signature = base64.b64decode(signature_b64, validate=True)
            digest = bytes.fromhex(digest_hex)
            public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                return False, "UNSUPPORTED_PUBKEY_TYPE"
            public_key.verify(signature, digest, ec.ECDSA(Prehashed(hashes.SHA256())))
            return True, None
        except ValueError:
            return False, "INVALID_SIGNATURE_FORMAT"
        except InvalidSignature:
            return False, "INVALID_SIGNATURE"
        except Exception:
            return False, "SIGNATURE_VERIFICATION_ERROR"

    def _load_public_key_from_device_registry(self, pubkey_id: str) -> str | None:
        raw = settings.INGEST_DEVICE_PUBLIC_KEYS_JSON
        if not raw:
            return None
        try:
            mapping = json.loads(raw)
        except json.JSONDecodeError:
            return None
        value = mapping.get(pubkey_id)
        return value if isinstance(value, str) and value.strip() else None

    def _load_public_key_from_verifier_registry(self, verifier_device_id: str) -> str | None:
        raw = settings.INGEST_VERIFIER_PUBLIC_KEYS_JSON
        if not raw:
            return None
        try:
            mapping = json.loads(raw)
        except json.JSONDecodeError:
            return None
        value = mapping.get(verifier_device_id)
        return value if isinstance(value, str) and value.strip() else None


ingest_verification_service = IngestVerificationService()
