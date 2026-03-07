# TrustSeal Firmware Test Harnesses (Step 28)

This folder provides host-side scripts to test firmware contracts without reflashing every change.

## Scripts

- `telemetry_simulator.py`
  - Generates canonical telemetry packets.
  - Computes `payload_hash` exactly like backend verification.
  - Sends to `POST /api/v1/ingest/telemetry`.
  - Supports `X-Device-Id` / `X-Device-Token` ingest auth.

- `custody_simulator.py`
  - Generates custody packets with `fingerprint_result=match`.
  - Computes `approval_message_hash`.
  - Sends to `POST /api/v1/ingest/custody`.
  - Supports `X-Verifier-Device-Id` / `X-Verifier-Token` ingest auth.

- `smoke_flow.py`
  - Runs a compact end-to-end smoke path against the backend.
  - Sends telemetry, sends one custody approval, then optionally queries shipment/proof/ops APIs.
  - Useful for staging validation with real JWTs and ingest channel tokens.

- `serial_ndjson_validator.py`
  - Validates captured firmware serial NDJSON lines for required fields.
  - Modes: `tracker`, `verifier`.

## Setup

```powershell
cd iot/harness
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Example: telemetry ingest simulation

```powershell
python telemetry_simulator.py `
  --base-url http://localhost:8000 `
  --shipment-id 11111111-1111-1111-1111-111111111111 `
  --device-id 22222222-2222-2222-2222-222222222222 `
  --count 3
```

## Example: custody ingest simulation

```powershell
python custody_simulator.py `
  --base-url http://localhost:8000 `
  --shipment-id 11111111-1111-1111-1111-111111111111 `
  --leg-id 33333333-3333-3333-3333-333333333333 `
  --verifier-device-id 44444444-4444-4444-4444-444444444444 `
  --verifier-user-id 55555555-5555-5555-5555-555555555555
```

## Example: smoke the full canonical flow

```powershell
python smoke_flow.py `
  --base-url http://localhost:8000 `
  --shipment-id 11111111-1111-1111-1111-111111111111 `
  --device-id 22222222-2222-2222-2222-222222222222 `
  --leg-id 33333333-3333-3333-3333-333333333333 `
  --verifier-device-id 44444444-4444-4444-4444-444444444444 `
  --verifier-user-id 55555555-5555-5555-5555-555555555555 `
  --device-token your-device-token `
  --verifier-token your-verifier-token `
  --user-token your-user-jwt `
  --admin-token your-admin-jwt
```

## Example: validate captured serial logs

```powershell
python serial_ndjson_validator.py --mode tracker --file .\tracker_serial.log
python serial_ndjson_validator.py --mode verifier --file .\verifier_serial.log
```

## Notes

- These harnesses test API contract behavior and field shape.
- They do not replace hardware-in-the-loop tests.
- Use header-based ingest auth for canonical backend validation. The legacy Arduino bearer-token sketches are not the backend contract of record.
