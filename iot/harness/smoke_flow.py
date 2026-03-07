from __future__ import annotations

import argparse
import json
import time
from typing import Any

import requests

from telemetry_simulator import build_packet as build_telemetry_packet
from custody_simulator import build_packet as build_custody_packet


def _safe_json(response: requests.Response) -> Any:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return response.text


def _print_result(kind: str, response: requests.Response, context: dict[str, Any] | None = None) -> None:
    payload = {
        "kind": kind,
        "status_code": response.status_code,
        "response": _safe_json(response),
    }
    if context:
        payload["context"] = context
    print(json.dumps(payload, separators=(",", ":"), default=str))


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> requests.Response:
    return requests.post(url, headers=headers, json=payload, timeout=20)


def _get(url: str, headers: dict[str, str]) -> requests.Response:
    return requests.get(url, headers=headers, timeout=20)


def _pipeline_settled(base_url: str, shipment_id: str, user_headers: dict[str, str], admin_headers: dict[str, str]) -> bool:
    try:
        custody_response = _get(f"{base_url}/api/v1/shipments/{shipment_id}/custody", user_headers)
        ops_response = _get(f"{base_url}/api/v1/ops/pipeline-status?shipment_id={shipment_id}", admin_headers)
    except requests.RequestException:
        return False

    if not custody_response.ok or not ops_response.ok:
        return False

    custody_payload = _safe_json(custody_response)
    ops_payload = _safe_json(ops_response)
    if not isinstance(custody_payload, list) or not custody_payload:
        return False

    latest_custody = custody_payload[0]
    if not isinstance(latest_custody, dict):
        return False

    shipment_state = ops_payload.get("shipment_state", {}) if isinstance(ops_payload, dict) else {}
    custody_state = shipment_state.get("custody")
    batch_state = shipment_state.get("batch")
    anchor_state = shipment_state.get("anchor")

    if latest_custody.get("ingest_status") == "queued":
        return False

    if custody_state == "queued":
        return False

    if batch_state in {"open", "finalized"}:
        return False

    if anchor_state == "pending":
        return False

    return True


def _wait_for_pipeline_settle(
    base_url: str,
    shipment_id: str,
    user_headers: dict[str, str],
    admin_headers: dict[str, str],
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _pipeline_settled(base_url, shipment_id, user_headers, admin_headers):
            return
        time.sleep(poll_interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="TrustSeal local smoke flow runner")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--read-base-url", default="", help="Optional base URL for shipment/proof/ops reads; defaults to --base-url")
    parser.add_argument("--shipment-id", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--device-uid", default="SIM-TRACKER-001")
    parser.add_argument("--pubkey-id", default="sim-pubkey-001")
    parser.add_argument("--leg-id", required=True)
    parser.add_argument("--verifier-device-id", required=True)
    parser.add_argument("--verifier-user-id", required=True)
    parser.add_argument("--signer-address", default="0x0000000000000000000000000000000000000000")
    parser.add_argument("--telemetry-count", type=int, default=3)
    parser.add_argument("--start-seq", type=int, default=1)
    parser.add_argument("--device-token", default="", help="Optional X-Device-Token for ingest")
    parser.add_argument("--verifier-token", default="", help="Optional X-Verifier-Token for ingest")
    parser.add_argument("--user-token", default="", help="Optional user bearer token for shipment/proof reads")
    parser.add_argument("--admin-token", default="", help="Optional admin bearer token for ops reads")
    parser.add_argument("--settle-seconds", type=float, default=2.0, help="Seconds to wait before readback checks")
    parser.add_argument("--settle-timeout-seconds", type=float, default=20.0, help="Maximum seconds to wait for custody/pipeline settlement")
    parser.add_argument("--settle-poll-seconds", type=float, default=1.0, help="Polling interval while waiting for pipeline settlement")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    read_base_url = (args.read_base_url or args.base_url).rstrip("/")
    telemetry_url = f"{base_url}/api/v1/ingest/telemetry"
    custody_url = f"{base_url}/api/v1/ingest/custody"

    telemetry_headers = {"Content-Type": "application/json"}
    if args.device_token:
        telemetry_headers["X-Device-Id"] = args.device_id
        telemetry_headers["X-Device-Token"] = args.device_token

    for offset in range(args.telemetry_count):
        telemetry_packet = build_telemetry_packet(
            shipment_id=args.shipment_id,
            device_id=args.device_id,
            device_uid=args.device_uid,
            seq_no=args.start_seq + offset,
            pubkey_id=args.pubkey_id,
        )
        response = _post_json(telemetry_url, telemetry_headers, telemetry_packet)
        _print_result(
            "telemetry_ingest",
            response,
            {"event_id": telemetry_packet["event_id"], "seq_no": telemetry_packet["seq_no"]},
        )

    custody_headers = {"Content-Type": "application/json"}
    if args.verifier_token:
        custody_headers["X-Verifier-Device-Id"] = args.verifier_device_id
        custody_headers["X-Verifier-Token"] = args.verifier_token

    custody_packet = build_custody_packet(
        shipment_id=args.shipment_id,
        leg_id=args.leg_id,
        verifier_device_id=args.verifier_device_id,
        verifier_user_id=args.verifier_user_id,
        signer_address=args.signer_address,
    )
    response = _post_json(custody_url, custody_headers, custody_packet)
    _print_result(
        "custody_ingest",
        response,
        {"custody_event_id": custody_packet["custody_event_id"]},
    )

    if args.settle_seconds > 0:
        time.sleep(args.settle_seconds)

    user_headers = {"Authorization": f"Bearer {args.user_token}"} if args.user_token else {}
    admin_headers = {"Authorization": f"Bearer {args.admin_token}"} if args.admin_token else {}

    if user_headers and admin_headers and args.settle_timeout_seconds > 0:
        _wait_for_pipeline_settle(
            read_base_url,
            args.shipment_id,
            user_headers,
            admin_headers,
            args.settle_timeout_seconds,
            args.settle_poll_seconds,
        )

    if args.user_token:
        for kind, path in (
            ("shipment_overview", f"/api/v1/shipments/{args.shipment_id}/overview"),
            ("shipment_telemetry", f"/api/v1/shipments/{args.shipment_id}/telemetry"),
            ("shipment_custody", f"/api/v1/shipments/{args.shipment_id}/custody"),
            ("shipment_latest_proof", f"/api/v1/proofs/shipments/{args.shipment_id}/latest"),
        ):
            response = _get(f"{read_base_url}{path}", user_headers)
            _print_result(kind, response)

    if args.admin_token:
        for kind, path in (
            ("ops_pipeline_status", f"/api/v1/ops/pipeline-status?shipment_id={args.shipment_id}"),
            ("ops_workers_status", "/api/v1/ops/workers/status"),
        ):
            response = _get(f"{read_base_url}{path}", admin_headers)
            _print_result(kind, response)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
