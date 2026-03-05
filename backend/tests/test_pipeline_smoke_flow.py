from __future__ import annotations

from unittest.mock import MagicMock

import app.services.telemetry_stream_service as stream_module
from app.services.telemetry_stream_service import TelemetryStreamService


def test_stream_smoke_custody_to_anchor_flow(monkeypatch) -> None:
    fake_db = MagicMock()
    call_order: list[str] = []

    monkeypatch.setattr(stream_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        stream_module.persistence_worker,
        "process_stream_payload",
        lambda db, event_type, payload: (call_order.append(f"persist:{event_type}") or True),
    )
    monkeypatch.setattr(
        stream_module.batch_worker,
        "maybe_finalize_shipment_batch",
        lambda db, shipment_id, trigger, force=False: call_order.append("batch:maybe_finalize"),
    )
    monkeypatch.setattr(
        stream_module.batch_worker,
        "build_bundle_payload_json",
        lambda db, bundle_id: (call_order.append("bundle:payload") or '[{"event_id":"e1"}]'),
    )
    monkeypatch.setattr(
        stream_module.ipfs_worker,
        "pin_bundle",
        lambda db, bundle_id, payload_json: (call_order.append("ipfs:pin") or object()),
    )
    monkeypatch.setattr(
        stream_module.custody_gate_worker,
        "verify_bundle_custody",
        lambda db, bundle_id: (call_order.append("custody:verify") or True),
    )
    monkeypatch.setattr(
        stream_module.anchor_worker,
        "request_anchor",
        lambda db, bundle_id: call_order.append("anchor:request"),
    )
    monkeypatch.setattr(
        stream_module.anchor_worker,
        "process_anchor",
        lambda db, bundle_id: call_order.append("anchor:process"),
    )

    service = TelemetryStreamService()
    service._process_custody({"shipment_id": "s1", "custody_event_id": "c1"})
    service._process_bundle_ready({"bundle_id": "b1"})
    service._process_anchor_request({"bundle_id": "b1"})

    assert call_order == [
        "persist:custody",
        "batch:maybe_finalize",
        "bundle:payload",
        "ipfs:pin",
        "custody:verify",
        "anchor:request",
        "anchor:process",
    ]


def test_stream_bundle_ready_raises_when_ipfs_pin_fails(monkeypatch) -> None:
    fake_db = MagicMock()
    monkeypatch.setattr(stream_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        stream_module.batch_worker,
        "build_bundle_payload_json",
        lambda db, bundle_id: '[{"event_id":"e1"}]',
    )
    monkeypatch.setattr(
        stream_module.ipfs_worker,
        "pin_bundle",
        lambda db, bundle_id, payload_json: None,
    )

    service = TelemetryStreamService()
    try:
        service._process_bundle_ready({"bundle_id": "b1"})
        assert False, "Expected RuntimeError for failed IPFS pin"
    except RuntimeError as exc:
        assert "IPFS pin failed" in str(exc)
