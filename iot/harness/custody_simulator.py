from __future__ import annotations

import argparse
import json
import random
from typing import Any

import requests

from common import new_uuid, sha256_hex_from_obj, utc_now_iso


def build_packet(
    shipment_id: str,
    leg_id: str,
    verifier_device_id: str,
    verifier_user_id: str,
    signer_address: str,
) -> dict[str, Any]:
    custody_event_id = new_uuid()
    fingerprint_score = round(random.uniform(70.0, 99.9), 1)
    fingerprint_template_id = str(random.randint(1, 10))

    core = {
        "custody_event_id": custody_event_id,
        "shipment_id": shipment_id,
        "leg_id": leg_id,
        "verifier_device_id": verifier_device_id,
        "verifier_user_id": verifier_user_id,
        "ts": utc_now_iso(),
        "fingerprint_result": "match",
        "fingerprint_score": fingerprint_score,
        "fingerprint_template_id": fingerprint_template_id,
        "digital_signer_address": signer_address,
        "sig_alg": "ecdsa-secp256r1",
        "idempotency_key": custody_event_id,
    }
    approval_hash = sha256_hex_from_obj(core)

    packet: dict[str, Any] = {
        **core,
        "approval_message_hash": approval_hash,
        "signature": "sim-signature-base64",
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="TrustSeal custody ingest simulator")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--shipment-id", required=True)
    parser.add_argument("--leg-id", required=True)
    parser.add_argument("--verifier-device-id", required=True)
    parser.add_argument("--verifier-user-id", required=True)
    parser.add_argument("--signer-address", default="0x0000000000000000000000000000000000000000")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--token", default="", help="Optional bearer token")
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/api/v1/ingest/custody"
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    for i in range(args.count):
        packet = build_packet(
            shipment_id=args.shipment_id,
            leg_id=args.leg_id,
            verifier_device_id=args.verifier_device_id,
            verifier_user_id=args.verifier_user_id,
            signer_address=args.signer_address,
        )
        response = requests.post(url, headers=headers, json=packet, timeout=15)
        print(
            json.dumps(
                {
                    "idx": i + 1,
                    "status_code": response.status_code,
                    "custody_event_id": packet["custody_event_id"],
                    "response": response.json() if response.content else {},
                },
                separators=(",", ":"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
