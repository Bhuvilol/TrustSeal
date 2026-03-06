from __future__ import annotations

import argparse
import json
import random
from typing import Any

import requests

from common import new_uuid, sha256_hex_from_obj, utc_now_iso


def build_packet(
    shipment_id: str,
    device_id: str,
    device_uid: str,
    seq_no: int,
    pubkey_id: str,
) -> dict[str, Any]:
    event_id = new_uuid()
    payload_core = {
        "event_id": event_id,
        "shipment_id": shipment_id,
        "device_id": device_id,
        "device_uid": device_uid,
        "ts": utc_now_iso(),
        "seq_no": seq_no,
        "temperature_c": round(random.uniform(2.0, 8.0), 2),
        "humidity_pct": round(random.uniform(55.0, 80.0), 2),
        "shock_g": round(random.uniform(0.0, 1.5), 3),
        "light_lux": round(random.uniform(10.0, 250.0), 2),
        "tilt_deg": round(random.uniform(-10.0, 10.0), 2),
        "gps": None,
        "battery_pct": round(random.uniform(50.0, 100.0), 1),
        "network_type": "cellular",
        "firmware_version": "sim-0.1.0",
        "sig_alg": "ecdsa-secp256r1",
        "pubkey_id": pubkey_id,
        "idempotency_key": event_id,
    }
    payload_hash = sha256_hex_from_obj(payload_core)
    packet = {
        **payload_core,
        "hash_alg": "sha256",
        "payload_hash": payload_hash,
        "signature": "sim-signature-base64",
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="TrustSeal telemetry ingest simulator")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--shipment-id", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--device-uid", default="SIM-TRACKER-001")
    parser.add_argument("--pubkey-id", default="sim-pubkey-001")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--start-seq", type=int, default=1)
    parser.add_argument("--token", default="", help="Optional bearer token")
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/api/v1/ingest/telemetry"
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    for i in range(args.count):
        packet = build_packet(
            shipment_id=args.shipment_id,
            device_id=args.device_id,
            device_uid=args.device_uid,
            seq_no=args.start_seq + i,
            pubkey_id=args.pubkey_id,
        )
        response = requests.post(url, headers=headers, json=packet, timeout=15)
        print(
            json.dumps(
                {
                    "idx": i + 1,
                    "status_code": response.status_code,
                    "event_id": packet["event_id"],
                    "response": response.json() if response.content else {},
                },
                separators=(",", ":"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
