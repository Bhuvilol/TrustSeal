from __future__ import annotations

import argparse
import json
from pathlib import Path


TRACKER_REQUIRED = {
    "event_id",
    "shipment_id",
    "device_id",
    "ts",
    "seq_no",
    "hash_alg",
    "payload_hash",
    "sig_alg",
    "signature",
    "idempotency_key",
}

CUSTODY_REQUIRED = {
    "custody_event_id",
    "shipment_id",
    "leg_id",
    "verifier_device_id",
    "verifier_user_id",
    "ts",
    "fingerprint_result",
    "approval_message_hash",
    "signature",
    "sig_alg",
    "idempotency_key",
}


def validate_line(obj: dict, mode: str) -> tuple[bool, str]:
    required = TRACKER_REQUIRED if mode == "tracker" else CUSTODY_REQUIRED
    missing = sorted(k for k in required if k not in obj)
    if missing:
        return False, f"missing={','.join(missing)}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate firmware serial NDJSON lines")
    parser.add_argument("--file", required=True, help="Captured serial output file path")
    parser.add_argument("--mode", choices=["tracker", "verifier"], required=True)
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"error": "file_not_found", "file": str(path)}))
        return 1

    total = 0
    valid = 0
    invalid = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                print(json.dumps({"line": idx, "valid": False, "reason": "invalid_json"}))
                continue
            ok, reason = validate_line(obj, args.mode)
            if ok:
                valid += 1
            else:
                invalid += 1
            print(json.dumps({"line": idx, "valid": ok, "reason": reason}, separators=(",", ":")))

    print(
        json.dumps(
            {"mode": args.mode, "total_checked": total, "valid": valid, "invalid": invalid},
            separators=(",", ":"),
        )
    )
    return 0 if invalid == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
