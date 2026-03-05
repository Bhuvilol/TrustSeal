from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.config import settings
from app.services.ipfs_worker import IpfsWorker


def _db_with_batch_and_no_ipfs(batch) -> MagicMock:
    db = MagicMock()
    q_batch = MagicMock()
    q_existing = MagicMock()
    db.query.side_effect = [q_batch, q_existing]
    q_batch.filter.return_value.first.return_value = batch
    q_existing.filter.return_value.first.return_value = None
    return db


def test_pin_bundle_disabled_captures_content_metadata() -> None:
    worker = IpfsWorker()
    payload_json = '[{"event_id":"e1"}]'
    batch = SimpleNamespace(
        id="bundle-1",
        shipment_id="shipment-1",
        status="finalized",
        ipfs_cid=None,
        error_message=None,
    )
    db = _db_with_batch_and_no_ipfs(batch)

    old_enabled = settings.IPFS_PIN_ENABLED
    try:
        settings.IPFS_PIN_ENABLED = False
        obj = worker.pin_bundle(db, bundle_id="00000000-0000-0000-0000-000000000001", payload_json=payload_json)
        assert obj is not None
        assert batch.status == "ipfs_pinned"
        assert batch.ipfs_cid == "ipfs-disabled"
        assert obj.pin_status == "skipped"
        assert obj.content_hash == hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        assert obj.size_bytes == len(payload_json.encode("utf-8"))
    finally:
        settings.IPFS_PIN_ENABLED = old_enabled

