from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.persistence_worker import PersistenceWorker


def test_process_stream_payload_telemetry_ensures_then_marks() -> None:
    worker = PersistenceWorker()
    db = MagicMock()
    calls: list[str] = []

    worker._ensure_telemetry_row = lambda _db, _payload: (calls.append("ensure") or object())  # type: ignore[method-assign]
    worker.mark_telemetry_persisted = lambda _db, event_id: (calls.append(f"mark:{event_id}") or True)  # type: ignore[method-assign]

    payload = {"event_id": "evt-1", "shipment_id": "s1", "device_id": "d1"}
    ok = worker.process_stream_payload(db, event_type="telemetry", payload=payload)
    assert ok is True
    assert calls == ["ensure", "mark:evt-1"]


def test_process_stream_payload_custody_ensures_then_marks() -> None:
    worker = PersistenceWorker()
    db = MagicMock()
    calls: list[str] = []

    worker._ensure_custody_row = lambda _db, _payload: (calls.append("ensure") or object())  # type: ignore[method-assign]
    worker.mark_custody_persisted = lambda _db, custody_event_id: (calls.append(f"mark:{custody_event_id}") or True)  # type: ignore[method-assign]

    payload = {"custody_event_id": "c-1", "shipment_id": "s1"}
    ok = worker.process_stream_payload(db, event_type="custody", payload=payload)
    assert ok is True
    assert calls == ["ensure", "mark:c-1"]


def test_process_stream_payload_rejects_missing_ids() -> None:
    worker = PersistenceWorker()
    db = MagicMock()
    assert worker.process_stream_payload(db, event_type="telemetry", payload={}) is False
    assert worker.process_stream_payload(db, event_type="custody", payload={}) is False


def test_mark_telemetry_persisted_publishes_realtime_event(mocker) -> None:
    worker = PersistenceWorker()
    db = MagicMock()
    row = MagicMock()
    row.event_id = "evt-1"
    row.shipment_id = uuid.uuid4()
    row.device_id = uuid.uuid4()
    row.ts = datetime.now(timezone.utc)
    row.metrics = {
        "temperature_c": 6.4,
        "humidity_pct": 71.0,
        "shock_g": 0.2,
        "tilt_deg": 1.1,
        "battery_pct": 89.0,
    }
    row.gps = {"lat": 22.5, "lng": 88.3, "speed_kmh": 41.2, "heading_deg": 180.0}
    row.ingest_status = "queued"
    db.query.return_value.filter.return_value.first.return_value = row

    publish = mocker.patch("app.services.persistence_worker.shipment_event_dispatcher.publish")

    assert worker.mark_telemetry_persisted(db, event_id="evt-1") is True
    assert row.ingest_status == "persisted"
    assert db.commit.called
    publish.assert_called_once()
    payload = publish.call_args.args[1]
    assert payload["event"] == "telemetry-update"
    assert payload["data"]["event_id"] == "evt-1"
    assert payload["data"]["latitude"] == 22.5
