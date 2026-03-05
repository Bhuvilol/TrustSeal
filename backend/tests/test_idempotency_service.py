from __future__ import annotations

from unittest.mock import MagicMock

from app.services.idempotency_service import idempotency_service


def test_telemetry_exists_by_idempotency_key() -> None:
    db = MagicMock()
    first_query = MagicMock()
    second_query = MagicMock()
    db.query.side_effect = [first_query, second_query]
    first_query.filter.return_value.first.return_value = None
    second_query.filter.return_value.first.return_value = object()

    exists = idempotency_service.telemetry_exists(
        db,
        event_id="event-1",
        idempotency_key="idem-1",
    )
    assert exists is True


def test_custody_exists_false_when_no_matches() -> None:
    db = MagicMock()
    first_query = MagicMock()
    second_query = MagicMock()
    db.query.side_effect = [first_query, second_query]
    first_query.filter.return_value.first.return_value = None
    second_query.filter.return_value.first.return_value = None

    exists = idempotency_service.custody_exists(
        db,
        custody_event_id="custody-1",
        idempotency_key="idem-2",
    )
    assert exists is False
