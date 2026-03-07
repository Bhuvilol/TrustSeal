# Verifier Arduino

Primary Arduino IDE verifier firmware for TrustSeal.

What it does:
- reads the R307S fingerprint sensor
- creates signed custody approval packets
- stores queued custody packets in SPIFFS when offline
- sends custody packets over the A7670C modem to `POST /api/v1/ingest/custody`
- authenticates with backend ingest headers:
  - `X-Verifier-Device-Id`
  - `X-Verifier-Token`

Key files:
- [verifier_arduino.ino](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/verifier_arduino/verifier_arduino.ino)
- [verifier_config.h](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/verifier_arduino/verifier_config.h)
- [verifier_secrets.h](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/verifier_arduino/verifier_secrets.h)

Default hardware assumptions:
- fingerprint UART on `RX=16`, `TX=17`
- modem UART on `RX=26`, `TX=27`
- APN default `jionet`

Before flashing:
1. Set `VERIFIER_API_HOST`, `VERIFIER_API_PORT`, and `VERIFIER_API_PATH`.
2. Set a real `VERIFIER_API_BEARER_TOKEN` value.
3. Provision a real private key in [verifier_secrets.h](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/verifier_arduino/verifier_secrets.h).
4. Make sure backend ingest auth is enabled for the same `VERIFIER_DEVICE_ID`.
5. Confirm the `VERIFIER_SHIPMENT_ID` and `VERIFIER_LEG_ID` match a real open shipment leg.

Preferred local setup:
- run [provision_arduino_devices.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/scripts/provision_arduino_devices.py)
- use the generated ignored files:
  - `verifier_config.local.h`
  - `verifier_secrets.local.h`

Notes:
- The macro name `VERIFIER_API_BEARER_TOKEN` is legacy naming only; the sketch sends header-based ingest auth, not `Authorization: Bearer`.
- The verifier needs separate UART wiring for the fingerprint sensor and modem. Do not place both on the same pins.
