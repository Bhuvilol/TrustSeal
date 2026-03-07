# TrustSeal Tracker Firmware (Step 25)

This folder implements the Step 23 tracker sensor-read pipeline using:

- ESP32 DevKit
- BME280 (temperature/humidity/pressure)
- ADXL345 (3-axis acceleration/shock estimate)
- LDR (ambient light)

## What this step covers

- Initializes I2C and analog input.
- Samples sensors on a fixed interval.
- Builds unsigned payload JSON and computes `SHA-256` hash.
- Signs payload hash with `ECDSA secp256r1` (placeholder key slot in firmware).
- Buffers signed packets locally in `SPIFFS` queue file.
- Emits packet JSON to Serial including queue depth.

This firmware now covers:

- Step 23: sensor read pipeline
- Step 24: packet hashing/signing + local buffering
- Step 25: A7670C cellular send + ACK dequeue + retry backoff

## Pin defaults

Defined in `include/tracker_config.h`:

- `I2C_SDA_PIN = 21`
- `I2C_SCL_PIN = 22`
- `LDR_PIN = 34`

Adjust these to match your wiring.

## Build/Flash (PlatformIO)

1. Install PlatformIO (VS Code extension or CLI).
2. From this folder run:

```powershell
pio run
pio run -t upload
pio device monitor
```

Before upload, set these in `include/tracker_config.h`:

- `MODEM_RX_PIN`, `MODEM_TX_PIN`, `MODEM_BAUD` (ESP32 <-> A7670C UART)
- `MODEM_APN` (Airtel default: `airtelgprs.com`)
- `TRACKER_API_HOST`, `TRACKER_API_PORT`, `TRACKER_API_PATH`
- `TRACKER_API_BEARER_TOKEN` remains for legacy compatibility only. The backend canonical auth contract is `X-Device-Id` plus `X-Device-Token`.

You should see JSON lines like:

```json
{"event_id":"00123456-0000-0001-0cfa-aabbccddeeff","shipment_id":"00000000-0000-0000-0000-000000000001","device_id":"00000000-0000-0000-0000-000000000101","device_uid":"ESP32-TRACKER-001","ts":"2026-03-06T20:15:40Z","seq_no":1,"temperature_c":28.4,"humidity_pct":62.1,"shock_g":0.99,"light_lux":293.0,"tilt_deg":1.2,"gps":null,"battery_pct":100.0,"network_type":"wifi","firmware_version":"0.1.0","hash_alg":"sha256","payload_hash":"...","sig_alg":"ecdsa-secp256r1","signature":"...","pubkey_id":"fb9fcd1d0eea5545","idempotency_key":"00123456-0000-0001-0cfa-aabbccddeeff"}
```

`network_type` can be changed to `"cellular"` if you want that label in backend analytics.

At runtime, queue draining behavior is:

- `202` with `{"success":true,"data":{"accepted":true}}`: dequeue
- `409` duplicate: dequeue
- `400/401/403/422`: drop packet as permanent reject
- network/5xx: keep packet and retry with exponential backoff

## A7670C notes

- This implementation uses TinyGSM with SIM7600-compatible profile, which works for A7670C AT command family in most setups.
- Current transport target is plain HTTP (`port 80`) for simpler modem compatibility. If you want TLS (`https`) next, we can switch to secure modem client mode in a dedicated step.

## Local queue

- File path: `SPIFFS:/telemetry_queue.ndjson`
- Max entries: `TELEMETRY_QUEUE_MAX_ENTRIES` (default `300`)
- Oldest packets are trimmed when queue exceeds cap.

## Key management note

`include/tracker_secrets.h` is now a placeholder only. Provision a real per-device private key and pubkey identifier before real deployment.

## Next Step

- Step 26: implement verifier firmware fingerprint capture + match flow.
