from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import uuid

from app.core.config import settings
from app.services.idempotency_service import idempotency_service


def test_telemetry_replay_rejects_future_timestamp() -> None:
    db = MagicMock()
    previous_skew = settings.INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS
    try:
        settings.INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS = 10
        ts = datetime.now(timezone.utc) + timedelta(seconds=30)
        reason = idempotency_service.telemetry_replay_reason(
            db,
            device_id=str(uuid.uuid4()),
            seq_no=1,
            ts=ts,
        )
        assert reason == "REPLAY_TIMESTAMP_FUTURE"
    finally:
        settings.INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS = previous_skew


def test_telemetry_replay_rejects_non_monotonic_sequence() -> None:
    db = MagicMock()
    q1 = MagicMock()
    db.query.side_effect = [q1]
    q1.filter.return_value.order_by.return_value.first.return_value = (12,)

    reason = idempotency_service.telemetry_replay_reason(
        db,
        device_id=str(uuid.uuid4()),
        seq_no=10,
        ts=datetime.now(timezone.utc),
    )
    assert reason == "REPLAY_SEQUENCE"


def test_custody_replay_rejects_non_monotonic_timestamp_order() -> None:
    db = MagicMock()
    q1 = MagicMock()
    db.query.side_effect = [q1]
    latest = datetime.now(timezone.utc)
    q1.filter.return_value.order_by.return_value.first.return_value = (latest,)

    reason = idempotency_service.custody_replay_reason(
        db,
        verifier_device_id=str(uuid.uuid4()),
        shipment_id=str(uuid.uuid4()),
        ts=latest - timedelta(seconds=1),
    )
    assert reason == "REPLAY_TIMESTAMP_ORDER"
