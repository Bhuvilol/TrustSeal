from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.chain_anchor import ChainAnchor
from app.models.ipfs_object import IpfsObject
from app.models.telemetry_batch import TelemetryBatch
from app.routers.proofs import bundle_ipfs_link, bundle_proof, latest_shipment_proof


def _mock_db_for_bundle(batch, ipfs_obj, anchor):
    q_batch = MagicMock()
    q_ipfs = MagicMock()
    q_anchor = MagicMock()
    q_batch.filter.return_value.order_by.return_value.first.return_value = batch
    q_batch.filter.return_value.first.return_value = batch
    q_ipfs.filter.return_value.first.return_value = ipfs_obj
    q_anchor.filter.return_value.first.return_value = anchor

    db = MagicMock()
    db.query.side_effect = lambda model: {
        TelemetryBatch: q_batch,
        IpfsObject: q_ipfs,
        ChainAnchor: q_anchor,
    }[model]
    return db


def test_latest_shipment_proof_has_linkage_fields() -> None:
    shipment_id = uuid.uuid4()
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        epoch=3,
        status="anchored",
        record_count=12,
        batch_hash="hash-123",
        ipfs_cid=None,
        tx_hash=None,
        anchored_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        error_message=None,
    )
    ipfs_obj = SimpleNamespace(ipfs_cid="bafy123", pin_status="pinned", pinned_at=datetime.now(timezone.utc))
    anchor = SimpleNamespace(
        tx_hash="0xtx123",
        anchor_status="confirmed",
        network="polygon-80002",
        contract_address="0xabc",
        anchored_at=datetime.now(timezone.utc),
    )
    db = _mock_db_for_bundle(batch, ipfs_obj, anchor)

    result = latest_shipment_proof(shipment_id=shipment_id, db=db, current_user=SimpleNamespace())
    assert result["bundle_id"] == str(bundle_id)
    assert result["ipfs_cid"] == "bafy123"
    assert result["tx_hash"] == "0xtx123"
    assert result["proof_linkage"]["bundle_id"] == str(bundle_id)
    assert result["proof_linkage"]["ipfs_cid"] == "bafy123"
    assert result["proof_linkage"]["tx_hash"] == "0xtx123"


def test_bundle_proof_has_linkage_fields() -> None:
    shipment_id = uuid.uuid4()
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        epoch=5,
        status="anchor_pending",
        record_count=50,
        batch_hash="hash-456",
        ipfs_cid="bafy456",
        tx_hash="0xtx456",
        anchored_at=None,
        created_at=datetime.now(timezone.utc),
        error_message=None,
    )
    ipfs_obj = SimpleNamespace(
        ipfs_cid="bafy456",
        pin_status="pinned",
        content_hash="ch1",
        size_bytes=1024,
        pinned_at=datetime.now(timezone.utc),
    )
    anchor = SimpleNamespace(
        tx_hash="0xtx456",
        block_number=1234,
        anchor_status="submitted",
        network="polygon-80002",
        contract_address="0xdef",
        anchored_at=None,
        error_message=None,
    )
    db = _mock_db_for_bundle(batch, ipfs_obj, anchor)

    result = bundle_proof(bundle_id=bundle_id, db=db, current_user=SimpleNamespace())
    assert result["bundle_id"] == str(bundle_id)
    assert result["ipfs_cid"] == "bafy456"
    assert result["tx_hash"] == "0xtx456"
    assert result["proof_linkage"]["bundle_hash"] == "hash-456"


def test_bundle_ipfs_link_exposes_tx_hash() -> None:
    shipment_id = uuid.uuid4()
    bundle_id = uuid.uuid4()
    batch = SimpleNamespace(id=bundle_id, shipment_id=shipment_id, ipfs_cid="bafy789", tx_hash="0xtx789")
    db = _mock_db_for_bundle(batch, SimpleNamespace(ipfs_cid="bafy789"), None)

    result = bundle_ipfs_link(bundle_id=bundle_id, db=db, current_user=SimpleNamespace())
    assert result["bundle_id"] == str(bundle_id)
    assert result["ipfs_cid"] == "bafy789"
    assert result["tx_hash"] == "0xtx789"

