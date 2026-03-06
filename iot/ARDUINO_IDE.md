# Arduino IDE Workflow

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

Verifier notes:

- modem pins remain `RX=26`, `TX=27` until you validate the verifier modem wiring
- fingerprint UART remains `RX=16`, `TX=17`

Suggested order:

1. Open `tracker_arduino.ino` in Arduino IDE.
2. Select the ESP32 board and port.
3. Upload and watch serial output.
4. Confirm modem connectivity and valid signed queueing.
5. Only then move to `verifier_arduino.ino`.
