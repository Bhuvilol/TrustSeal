from __future__ import annotations

import json

from app.services.telemetry_stream_service import TelemetryStreamService


class _FakeRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def xadd(self, stream_name: str, entry: dict) -> str:
        self.calls.append((stream_name, entry))
        return "1-0"


def _service_with_fake_redis() -> tuple[TelemetryStreamService, _FakeRedis]:
    service = TelemetryStreamService()
    fake = _FakeRedis()
    service._redis = fake  # type: ignore[attr-defined]
    return service, fake


def test_publish_telemetry_normalizes_legacy_payload() -> None:
    service, fake = _service_with_fake_redis()
    payload = {
        "shipment_id": "11111111-1111-1111-1111-111111111111",
        "device_id": "22222222-2222-2222-2222-222222222222",
        "recorded_at": "2026-03-06T12:00:00Z",
        "temperature": 5.5,
        "humidity": 70.0,
    }
    stream_id = service.publish_sensor_log(payload)
    assert stream_id == "1-0"
    assert len(fake.calls) == 1
    entry = fake.calls[0][1]
    encoded = json.loads(entry["payload"])
    assert encoded["event_type"] == "telemetry"
    assert encoded["shipment_id"] == payload["shipment_id"]
    assert encoded["device_id"] == payload["device_id"]
    assert encoded["ts"] == payload["recorded_at"]
    assert isinstance(encoded["event_id"], str) and encoded["event_id"]
    assert encoded["idempotency_key"] == encoded["event_id"]
    assert encoded["metrics"]["temperature_c"] == 5.5


def test_publish_bundle_ready_requires_bundle_id() -> None:
    service, fake = _service_with_fake_redis()
    stream_id = service.publish_bundle_ready({"shipment_id": "s1"})
    assert stream_id is None
    assert fake.calls == []


def test_publish_anchor_request_includes_canonical_fields() -> None:
    service, fake = _service_with_fake_redis()
    payload = {
        "shipment_id": "s1",
        "bundle_id": "b1",
        "batch_hash": "hash1",
        "ipfs_cid": "bafy123",
    }
    stream_id = service.publish_anchor_request(payload)
    assert stream_id == "1-0"
    entry = fake.calls[0][1]
    encoded = json.loads(entry["payload"])
    assert encoded["event_type"] == "anchor_request"
    assert encoded["shipment_id"] == "s1"
    assert encoded["bundle_id"] == "b1"
    assert encoded["batch_hash"] == "hash1"
    assert encoded["ipfs_cid"] == "bafy123"
