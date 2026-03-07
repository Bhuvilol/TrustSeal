# Tracker Arduino

Primary Arduino IDE tracker firmware for TrustSeal.

What it does:
- reads BME280, ADXL345, and LDR inputs
- builds signed telemetry packets
- stores queued packets in SPIFFS when offline
- sends telemetry over the A7670C modem to `POST /api/v1/ingest/telemetry`
- authenticates with backend ingest headers:
  - `X-Device-Id`
  - `X-Device-Token`

Key files:
- [tracker_arduino.ino](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/tracker_arduino/tracker_arduino.ino)
- [tracker_config.h](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/tracker_arduino/tracker_config.h)
- [tracker_secrets.h](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/tracker_arduino/tracker_secrets.h)

Default hardware assumptions:
- I2C sensors on `SDA=21`, `SCL=22`
- LDR on `GPIO 34`
- modem UART on `RX=16`, `TX=17`
- APN default `jionet`

Before flashing:
1. Set `TRACKER_API_HOST`, `TRACKER_API_PORT`, and `TRACKER_API_PATH`.
2. Set a real `TRACKER_API_BEARER_TOKEN` value.
3. Provision a real private key in [tracker_secrets.h](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/tracker_arduino/tracker_secrets.h).
4. Make sure backend ingest auth is enabled for the same `TRACKER_DEVICE_ID`.

Preferred local setup:
- run [provision_arduino_devices.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/scripts/provision_arduino_devices.py)
- use the generated ignored files:
  - `tracker_config.local.h`
  - `tracker_secrets.local.h`

Notes:
- The macro name `TRACKER_API_BEARER_TOKEN` is legacy naming only; the sketch sends header-based ingest auth, not `Authorization: Bearer`.
- For local backend testing, point both tracker and verifier Arduino configs to the same backend host.
