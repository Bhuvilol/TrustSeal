from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import app.routers.ops as ops_module
from app.models.chain_anchor import ChainAnchor
from app.models.custody_transfer import CustodyTransfer
from app.models.ipfs_object import IpfsObject
from app.models.telemetry_event import TelemetryEvent
from app.models.telemetry_batch import TelemetryBatch
from app.routers.ops import pipeline_status, reprocess_dead_letter, retry_custody_gate, retry_ipfs_pin


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


def test_pipeline_status_includes_shipment_snapshot(monkeypatch) -> None:
    shipment_id = uuid.uuid4()
    bundle_id = uuid.uuid4()

    latest_event = SimpleNamespace(
        ingest_status="persisted",
        ts=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    latest_custody = SimpleNamespace(
        verification_status="valid",
        fingerprint_result="match",
        ingest_status="persisted",
        ts=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    latest_batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        status="anchor_pending",
        ipfs_cid="bafy-test",
        tx_hash=None,
        error_message=None,
        created_at=datetime.now(timezone.utc),
    )
    latest_anchor = SimpleNamespace(
        anchor_status="submitted",
        tx_hash="0xabc",
        anchored_at=None,
        error_message=None,
    )
    latest_ipfs = SimpleNamespace(ipfs_cid="bafy-test")

    def _query(*models):
        query = MagicMock()
        if len(models) == 1 and models[0] is TelemetryBatch:
            query.all.return_value = [latest_batch]
            query.order_by.return_value.first.return_value = latest_batch
            query.filter.return_value.first.return_value = latest_batch
            query.filter.return_value.order_by.return_value.first.return_value = latest_batch
            return query
        if models and models[0] is ChainAnchor:
            query.filter.return_value.scalar.return_value = 0
            query.filter.return_value.all.return_value = []
            query.filter.return_value.first.return_value = latest_anchor
            return query
        if models and models[0] is IpfsObject:
            query.filter.return_value.scalar.return_value = 0
            query.filter.return_value.all.return_value = []
            query.filter.return_value.first.return_value = latest_ipfs
            return query
        if len(models) == 1 and models[0] is TelemetryEvent:
            query.filter.return_value.order_by.return_value.first.return_value = latest_event
            return query
        if len(models) == 1 and models[0] is CustodyTransfer:
            query.filter.return_value.order_by.return_value.first.return_value = latest_custody
            return query
        raise AssertionError(f"Unexpected model query: {models}")

    db = MagicMock()
    db.query.side_effect = _query

    class FakeRedis:
        def xlen(self, stream_name):
            return {"telemetry_stream": 4, "custody_stream": 1, "bundle_ready_stream": 0, "anchor_request_stream": 2, "telemetry_dead_letter_stream": 3}[stream_name]

        def close(self):
            return None

    monkeypatch.setattr(ops_module.settings, "TELEMETRY_PIPELINE_MODE", "redis")
    monkeypatch.setattr(ops_module.settings, "REDIS_TELEMETRY_STREAM", "telemetry_stream")
    monkeypatch.setattr(ops_module.settings, "REDIS_CUSTODY_STREAM", "custody_stream")
    monkeypatch.setattr(ops_module.settings, "REDIS_BUNDLE_READY_STREAM", "bundle_ready_stream")
    monkeypatch.setattr(ops_module.settings, "REDIS_ANCHOR_REQUEST_STREAM", "anchor_request_stream")
    monkeypatch.setattr(ops_module.settings, "REDIS_DEAD_LETTER_STREAM", "telemetry_dead_letter_stream")
    monkeypatch.setattr(ops_module, "Redis", SimpleNamespace(from_url=lambda *args, **kwargs: FakeRedis()))
    monkeypatch.setattr(
        ops_module.worker_orchestrator,
        "get_status",
        lambda: {"started": True, "shutdown_requested": False, "workers": {}},
    )
    monkeypatch.setattr(ops_module.worker_orchestrator, "is_healthy", lambda: True)

    result = pipeline_status(shipment_id=shipment_id, db=db, _admin=SimpleNamespace())

    assert result["pipeline"]["batch_status_counts"] == {"anchor_pending": 1}
    assert result["redis"]["dead_letter_stream_len"] == 3
    assert result["workers"]["healthy"] is True
    assert result["shipment"]["shipment_id"] == str(shipment_id)
    assert result["shipment"]["ingest"] == "persisted"
    assert result["shipment"]["custody"] == "verified"
    assert result["shipment"]["batch"] == "anchor_pending"
    assert result["shipment"]["anchor"] == "submitted"
    assert result["shipment"]["latest_bundle_id"] == str(bundle_id)
    assert result["shipment"]["latest_ipfs_cid"] == "bafy-test"
    assert result["shipment"]["latest_tx_hash"] == "0xabc"
