from __future__ import annotations

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
