from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.chain_anchor import ChainAnchor
from app.models.telemetry_batch import TelemetryBatch
from app.services.chain_indexer_service import ChainIndexerService


class _FakeEventAccessor:
    def __init__(self, logs):
        self._logs = logs

    def get_logs(self, *, fromBlock, toBlock):
        return [log for log in self._logs if fromBlock <= int(log.blockNumber) <= toBlock]


class _FakeContractEvents:
    def __init__(self, logs):
        self._logs = logs

    def CustodyTransferred(self):
        return _FakeEventAccessor(self._logs)


class _FakeContract:
    def __init__(self, logs):
        self.events = _FakeContractEvents(logs)


class _FakeWeb3:
    def __init__(self, latest_block: int):
        self.eth = SimpleNamespace(block_number=latest_block)


def test_sync_once_maps_event_to_existing_batch_and_anchor(monkeypatch) -> None:
    service = ChainIndexerService()
    bundle_id = uuid.uuid4()
    shipment_id = uuid.uuid4()

    event = SimpleNamespace(
        args={
            "shipmentId": str(shipment_id),
            "bundleId": str(bundle_id),
            "bundleHash": "hash-1",
            "ipfsCid": "cid-1",
            "timestamp": 1710000000,
        },
        transactionHash=SimpleNamespace(hex=lambda: "0xtx1"),
        blockNumber=123,
    )
    monkeypatch.setattr(
        service,
        "_load_web3_contract",
        lambda: (_FakeWeb3(latest_block=130), _FakeContract([event])),
    )

    batch = SimpleNamespace(
        id=bundle_id,
        shipment_id=shipment_id,
        status="anchor_pending",
        tx_hash=None,
        ipfs_cid=None,
        anchored_at=None,
        error_message="old",
    )
    anchor = SimpleNamespace(
        bundle_id=bundle_id,
        shipment_id=shipment_id,
        network="polygon-80002",
        contract_address="0xold",
        tx_hash=None,
        block_number=None,
        anchor_status="submitted",
        anchored_at=None,
        error_message="old",
    )

    q_batch = MagicMock()
    q_anchor_bundle = MagicMock()
    q_batch.filter.return_value.first.return_value = batch
    q_anchor_bundle.filter.return_value.first.return_value = anchor

    db = MagicMock()

    def query_side_effect(model):
        if model is TelemetryBatch:
            return q_batch
        if model is ChainAnchor:
            return q_anchor_bundle
        raise AssertionError(f"Unexpected query model: {model}")

    db.query.side_effect = query_side_effect

    result = service.sync_once(db, from_block=120, to_block=130, block_batch_size=50)
    assert result["event_count"] == 1
    assert result["mapped_events"] == 1
    assert result["unmatched_events"] == 0
    assert anchor.anchor_status == "confirmed"
    assert anchor.tx_hash == "0xtx1"
    assert anchor.block_number == 123
    assert batch.status == "anchored"
    assert batch.tx_hash == "0xtx1"
    assert batch.ipfs_cid == "cid-1"
    db.commit.assert_called_once()


def test_sync_once_counts_unmatched_event(monkeypatch) -> None:
    service = ChainIndexerService()
    event = SimpleNamespace(
        args={
            "shipmentId": "shipment-external",
            "bundleId": "external-bundle-id",
            "bundleHash": "hash-x",
            "ipfsCid": "cid-x",
            "timestamp": 1710000001,
        },
        transactionHash=SimpleNamespace(hex=lambda: "0xtx2"),
        blockNumber=220,
    )
    monkeypatch.setattr(
        service,
        "_load_web3_contract",
        lambda: (_FakeWeb3(latest_block=230), _FakeContract([event])),
    )

    q_batch = MagicMock()
    q_anchor = MagicMock()
    q_batch.filter.return_value.first.return_value = None
    q_anchor.filter.return_value.first.return_value = None

    db = MagicMock()

    def query_side_effect(model):
        if model is TelemetryBatch:
            return q_batch
        if model is ChainAnchor:
            return q_anchor
        raise AssertionError(f"Unexpected query model: {model}")

    db.query.side_effect = query_side_effect

    result = service.sync_once(db, from_block=200, to_block=225, block_batch_size=100)
    assert result["event_count"] == 1
    assert result["mapped_events"] == 0
    assert result["unmatched_events"] == 1
    db.commit.assert_not_called()

