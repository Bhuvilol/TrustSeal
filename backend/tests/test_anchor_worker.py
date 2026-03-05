from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import app.services.anchor_worker as anchor_module
from app.models.chain_anchor import ChainAnchor
from app.models.ipfs_object import IpfsObject
from app.models.telemetry_batch import TelemetryBatch
from app.services.anchor_worker import anchor_worker


def test_request_anchor_returns_existing_when_already_anchored() -> None:
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=uuid.uuid4(),
        batch_hash="h1",
        ipfs_cid="cid-1",
        status="anchored",
    )
    existing_anchor = SimpleNamespace(bundle_id=bundle_id, anchor_status="confirmed")

    q_batch = MagicMock()
    q_anchor = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    q_anchor.filter.return_value.first.return_value = existing_anchor

    db = MagicMock()
    db.query.side_effect = lambda model: {
        TelemetryBatch: q_batch,
        ChainAnchor: q_anchor,
    }[model]

    result = anchor_worker.request_anchor(db, bundle_id=str(bundle_id))
    assert result is existing_anchor


def test_process_anchor_marks_failed_when_ipfs_missing() -> None:
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=uuid.uuid4(),
        batch_hash="h2",
        ipfs_cid=None,
        status="anchor_pending",
        error_message=None,
    )

    q_batch = MagicMock()
    q_ipfs = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    q_ipfs.filter.return_value.first.return_value = None

    db = MagicMock()
    db.query.side_effect = lambda model: {
        TelemetryBatch: q_batch,
        IpfsObject: q_ipfs,
    }[model]

    result = anchor_worker.process_anchor(db, bundle_id=str(bundle_id))
    assert result is None
    assert batch.status == "failed"
    assert "ipfs_cid" in (batch.error_message or "")
    db.commit.assert_called_once()


def test_process_anchor_success_updates_batch_and_anchor(monkeypatch) -> None:
    bundle_id = uuid.uuid4()
    shipment_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        batch_hash="h3",
        ipfs_cid="cid-3",
        status="anchor_pending",
        tx_hash=None,
        anchored_at=None,
        error_message=None,
    )
    ipfs_obj = SimpleNamespace(ipfs_cid="cid-3")

    q_batch = MagicMock()
    q_ipfs = MagicMock()
    q_anchor = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    q_ipfs.filter.return_value.first.return_value = ipfs_obj
    q_anchor.filter.return_value.first.return_value = None

    db = MagicMock()
    db.query.side_effect = lambda model: {
        TelemetryBatch: q_batch,
        IpfsObject: q_ipfs,
        ChainAnchor: q_anchor,
    }[model]

    monkeypatch.setattr(
        anchor_module.batch_finalization_service,
        "_anchor_on_chain",
        lambda **kwargs: "0xtxhash",
    )

    result = anchor_worker.process_anchor(db, bundle_id=str(bundle_id))
    assert result is not None
    assert result.tx_hash == "0xtxhash"
    assert result.anchor_status == "confirmed"
    assert batch.status == "anchored"
    assert batch.tx_hash == "0xtxhash"
