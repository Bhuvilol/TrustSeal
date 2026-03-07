# Arduino IDE Workflow

This is the primary firmware workflow for device bring-up.

The backend contract of record is still defined by the canonical FastAPI ingest endpoints and the host-side harness under `iot/harness/`, but the Arduino IDE sketches in this folder pair are the main device implementation path.

Open these folders directly in Arduino IDE:

- `iot/tracker_arduino/tracker_arduino.ino`
- `iot/verifier_arduino/verifier_arduino.ino`

Install these Arduino libraries:

- Adafruit BME280 Library
- Adafruit ADXL345
- Adafruit Fingerprint Sensor Library
- ArduinoJson
- TinyGSM
- ArduinoHttpClient

Tracker notes:

- modem pins are set to the values that worked in your Arduino IDE hardware test: `RX=16`, `TX=17`
- APN is set to `jionet`
- default API target is `trustseal.onrender.com:80`; replace it with your staging host if needed

Verifier notes:

- fingerprint UART uses `RX=16`, `TX=17`
- modem UART uses `RX=26`, `TX=27`
- keep those buses separate on the verifier; do not share the fingerprint and modem on the same UART pins

Suggested order:

1. Open `tracker_arduino.ino` in Arduino IDE.
2. Select the ESP32 board and port.
3. Upload and watch serial output.
4. Confirm modem connectivity and valid signed queueing.
5. Only then move to `verifier_arduino.ino`.

Important:

- Backend ingest auth is header-based, not bearer-token based.
- Keep any real device tokens and keys out of these files.
- If you move from the hosted backend to a local/staging backend, update `tracker_config.h` and `verifier_config.h` together so both devices hit the same environment.
- If your backend is HTTPS-only, run the local HTTP bridge in [device_ingest_bridge.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/http_bridge/device_ingest_bridge.py) and point both Arduino sketches at your laptop LAN IP on port `8081`.
- The repo now supports ignored local override headers; generate them with [provision_arduino_devices.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/scripts/provision_arduino_devices.py).
