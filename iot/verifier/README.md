# TrustSeal Verifier Firmware (Step 27)

This folder implements Step 26 + Step 27 for verifier hardware:

- ESP32
- R307S fingerprint module (UART)

## What this step covers

- Initializes R307S and performs scan/search loop.
- Detects outcomes: `match`, `no_match`, `error`.
- Builds canonical custody packet JSON aligned to backend schema.
- Computes `approval_message_hash` (`SHA-256`).
- Signs hash using `ECDSA secp256r1`.
- Buffers signed custody packets locally in SPIFFS queue.
- Sends queued packets via A7670C cellular HTTP with retry/backoff.
- Dequeues packets only on ACK (`202 accepted`) or duplicate (`409`).

## Pin defaults

Defined in `include/verifier_config.h`:

- `FP_TX_PIN = 17`
- `FP_RX_PIN = 16`
- `FP_BAUD = 57600`
- `MODEM_TX_PIN = 27`
- `MODEM_RX_PIN = 26`
- `MODEM_BAUD = 115200`

Before upload, set these in `include/verifier_config.h`:

- `MODEM_APN` (Airtel default: `airtelgprs.com`)
- `VERIFIER_API_HOST`, `VERIFIER_API_PORT`, `VERIFIER_API_PATH`
- `VERIFIER_API_BEARER_TOKEN` (if backend route is auth-protected)

## Build/Flash

```powershell
cd iot/verifier
pio run
pio run -t upload
pio device monitor
```

## Sample output packet

```json
{"custody_event_id":"00123456-0000-0001-1af2-aabbccddeeff","shipment_id":"00000000-0000-0000-0000-000000000001","leg_id":"00000000-0000-0000-0000-000000000401","verifier_device_id":"00000000-0000-0000-0000-000000000201","verifier_user_id":"00000000-0000-0000-0000-000000000301","ts":"2026-01-01T00:00:05Z","fingerprint_result":"match","fingerprint_score":120,"fingerprint_template_id":"3","digital_signer_address":"0x0000000000000000000000000000000000000000","approval_message_hash":"...","signature":"...","sig_alg":"ecdsa-secp256r1","idempotency_key":"00123456-0000-0001-1af2-aabbccddeeff"}
```

## ACK and retry policy

- `202` with `{"success":true,"data":{"accepted":true}}` => dequeue
- `409` duplicate => dequeue
- `400/401/403/422` => drop packet
- network/5xx => keep and retry with exponential backoff

## Security note

`include/verifier_secrets.h` contains a development key only. Replace with per-device provisioned key before production.

## Next step

- Step 28: firmware telemetry/custody test harnesses.
