from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.config import settings
from app.services.batch_worker import BatchWorker


def test_maybe_finalize_on_min_records(monkeypatch) -> None:
    worker = BatchWorker()
    db = MagicMock()

    old_min = settings.BATCH_MIN_RECORDS
    old_window = settings.BATCH_MAX_WINDOW_SECONDS
    try:
        settings.BATCH_MIN_RECORDS = 2
        settings.BATCH_MAX_WINDOW_SECONDS = 9999

        monkeypatch.setattr(
            worker,
            "_pending_rows",
            lambda _db, shipment_uuid: [
                SimpleNamespace(ts=datetime.now(timezone.utc)),
                SimpleNamespace(ts=datetime.now(timezone.utc)),
            ],
        )
        called: list[str] = []
        monkeypatch.setattr(
            worker,
            "finalize_shipment_batch",
            lambda _db, shipment_id: (called.append(shipment_id) or object()),
        )
        result = worker.maybe_finalize_shipment_batch(
            db,
            shipment_id="11111111-1111-1111-1111-111111111111",
            trigger="telemetry",
        )
        assert result is not None
        assert called == ["11111111-1111-1111-1111-111111111111"]
    finally:
        settings.BATCH_MIN_RECORDS = old_min
        settings.BATCH_MAX_WINDOW_SECONDS = old_window


def test_maybe_finalize_on_time_window(monkeypatch) -> None:
    worker = BatchWorker()
    db = MagicMock()

    old_min = settings.BATCH_MIN_RECORDS
    old_window = settings.BATCH_MAX_WINDOW_SECONDS
    try:
        settings.BATCH_MIN_RECORDS = 100
        settings.BATCH_MAX_WINDOW_SECONDS = 60

        old_ts = datetime.now(timezone.utc) - timedelta(seconds=120)
        monkeypatch.setattr(
            worker,
            "_pending_rows",
            lambda _db, shipment_uuid: [SimpleNamespace(ts=old_ts)],
        )
        called: list[str] = []
        monkeypatch.setattr(
            worker,
            "finalize_shipment_batch",
            lambda _db, shipment_id: (called.append(shipment_id) or object()),
        )
        result = worker.maybe_finalize_shipment_batch(
            db,
            shipment_id="22222222-2222-2222-2222-222222222222",
            trigger="telemetry",
        )
        assert result is not None
        assert called == ["22222222-2222-2222-2222-222222222222"]
    finally:
        settings.BATCH_MIN_RECORDS = old_min
        settings.BATCH_MAX_WINDOW_SECONDS = old_window


def test_maybe_finalize_respects_force(monkeypatch) -> None:
    worker = BatchWorker()
    db = MagicMock()
    monkeypatch.setattr(
        worker,
        "_pending_rows",
        lambda _db, shipment_uuid: [SimpleNamespace(ts=datetime.now(timezone.utc))],
    )
    called: list[str] = []
    monkeypatch.setattr(
        worker,
        "finalize_shipment_batch",
        lambda _db, shipment_id: (called.append(shipment_id) or object()),
    )
    result = worker.maybe_finalize_shipment_batch(
        db,
        shipment_id="33333333-3333-3333-3333-333333333333",
        trigger="custody",
        force=True,
    )
    assert result is not None
    assert called == ["33333333-3333-3333-3333-333333333333"]
