from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.custody_transfer import CustodyTransfer
from app.models.ipfs_object import IpfsObject
from app.models.telemetry_batch import TelemetryBatch
from app.services.custody_gate_worker import custody_gate_worker


def test_verify_bundle_custody_moves_to_verified() -> None:
    bundle_id = uuid.uuid4()
    shipment_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        status="ipfs_pinned",
        created_at=datetime.now(timezone.utc),
        error_message=None,
    )
    ipfs_obj = SimpleNamespace(pin_status="pinned")
    custody = SimpleNamespace()

    q_batch = MagicMock()
    q_ipfs = MagicMock()
    q_custody = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    q_ipfs.filter.return_value.first.return_value = ipfs_obj
    q_custody.filter.return_value.order_by.return_value.first.return_value = custody

    db = MagicMock()
    db.query.side_effect = lambda model: {
        TelemetryBatch: q_batch,
        IpfsObject: q_ipfs,
        CustodyTransfer: q_custody,
    }[model]

    ok = custody_gate_worker.verify_bundle_custody(db, bundle_id=str(bundle_id))
    assert ok is True
    assert batch.status == "custody_verified"
    assert batch.error_message is None
    db.commit.assert_called_once()


def test_verify_bundle_custody_rejects_wrong_batch_state() -> None:
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=uuid.uuid4(),
        status="finalized",
        created_at=datetime.now(timezone.utc),
        error_message=None,
    )
    q_batch = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    db = MagicMock()
    db.query.side_effect = lambda model: {TelemetryBatch: q_batch}[model]

    ok = custody_gate_worker.verify_bundle_custody(db, bundle_id=str(bundle_id))
    assert ok is False
    db.commit.assert_not_called()


def test_verify_bundle_custody_rejects_when_no_recent_persisted_event() -> None:
    bundle_id = uuid.uuid4()
    shipment_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        status="ipfs_pinned",
        created_at=datetime.now(timezone.utc),
        error_message=None,
    )
    ipfs_obj = SimpleNamespace(pin_status="pinned")

    q_batch = MagicMock()
    q_ipfs = MagicMock()
    q_custody = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    q_ipfs.filter.return_value.first.return_value = ipfs_obj
    q_custody.filter.return_value.order_by.return_value.first.return_value = None

    db = MagicMock()
    db.query.side_effect = lambda model: {
        TelemetryBatch: q_batch,
        IpfsObject: q_ipfs,
        CustodyTransfer: q_custody,
    }[model]

    ok = custody_gate_worker.verify_bundle_custody(db, bundle_id=str(bundle_id))
    assert ok is False
    assert "missing recent persisted fingerprint match event" in str(batch.error_message)
    db.commit.assert_called_once()
