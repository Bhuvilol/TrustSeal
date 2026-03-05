from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import app.routers.ops as ops_module
from app.models.telemetry_batch import TelemetryBatch
from app.routers.ops import reprocess_dead_letter, retry_custody_gate, retry_ipfs_pin


def _db_with_batch(batch):
    q_batch = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    db = MagicMock()
    db.query.side_effect = lambda model: {TelemetryBatch: q_batch}[model]
    return db


def test_retry_ipfs_pin_success(monkeypatch) -> None:
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(id=bundle_id, shipment_id=uuid.uuid4(), status="failed", ipfs_cid=None)
    db = _db_with_batch(batch)

    monkeypatch.setattr(ops_module.batch_worker, "build_bundle_payload_json", lambda *_args, **_kwargs: '[{"x":1}]')
    monkeypatch.setattr(
        ops_module.ipfs_worker,
        "pin_bundle",
        lambda *_args, **_kwargs: SimpleNamespace(ipfs_cid="bafy-retry", pin_status="pinned"),
    )

    result = retry_ipfs_pin(bundle_id=bundle_id, db=db, _admin=SimpleNamespace())
    assert result["accepted"] is True
    assert result["bundle_id"] == str(bundle_id)
    assert result["ipfs_cid"] == "bafy-retry"
    assert result["pin_status"] == "pinned"


def test_retry_custody_gate_raises_on_failure(monkeypatch) -> None:
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(id=bundle_id, shipment_id=uuid.uuid4(), status="ipfs_pinned", error_message="missing")
    db = _db_with_batch(batch)
    monkeypatch.setattr(ops_module.custody_gate_worker, "verify_bundle_custody", lambda *_args, **_kwargs: False)

    with pytest.raises(HTTPException) as exc:
        retry_custody_gate(bundle_id=bundle_id, db=db, _admin=SimpleNamespace())
    assert exc.value.status_code == 409
    assert "Custody gate retry failed" in str(exc.value.detail)


def test_reprocess_dead_letter_requeues_entries(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self):
            self.requeued = []
            self.deleted = []

        def xrange(self, *_args, **_kwargs):
            return [
                (
                    "1-0",
                    {
                        "stream_name": "telemetry_stream",
                        "fields": json.dumps({"event_type": "telemetry", "payload": "{}"}),
                    },
                )
            ]

        def xadd(self, stream_name, fields):
            self.requeued.append((stream_name, fields))
            return "2-0"

        def xdel(self, stream_name, message_id):
            self.deleted.append((stream_name, message_id))
            return 1

        def close(self):
            return None

    fake = FakeRedis()
    monkeypatch.setattr(ops_module.settings, "TELEMETRY_PIPELINE_MODE", "redis")
    monkeypatch.setattr(ops_module, "Redis", SimpleNamespace(from_url=lambda *args, **kwargs: fake))

    result = reprocess_dead_letter(limit=10, delete_requeued=True, db=MagicMock(), _admin=SimpleNamespace())
    assert result["accepted"] is True
    assert result["scanned"] == 1
    assert result["requeued"] == 1
    assert result["failed"] == 0
    assert fake.requeued[0][0] == "telemetry_stream"
    assert len(fake.deleted) == 1

