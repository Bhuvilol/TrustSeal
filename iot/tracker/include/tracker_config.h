#ifndef TRACKER_CONFIG_H
#define TRACKER_CONFIG_H

// I2C pins for ESP32 DevKit
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

// LDR analog pin
#define LDR_PIN 34

// Sensor polling interval
#define TELEMETRY_SAMPLE_INTERVAL_MS 5000
#define TELEMETRY_SEND_INTERVAL_MS 2000

// Calibration constants
#define LDR_ADC_MAX 4095.0f
#define LDR_LUX_SCALE 1000.0f

// Shipment/device placeholders for local firmware testing
#define TRACKER_SHIPMENT_ID "ROvhMsIvHIicFREIcS7XSb/FystevE0iJKk/wV0wvzw="
#define TRACKER_DEVICE_ID "0cb901e3-6cf7-4be2-83f4-3a232a283e33"
#define TRACKER_DEVICE_UID "ESP32-TRACKER-001"
#define TRACKER_FIRMWARE_VERSION "0.1.0"

// Local buffering
#define TELEMETRY_QUEUE_FILE "/telemetry_queue.ndjson"
#define TELEMETRY_QUEUE_MAX_ENTRIES 300

// A7670C modem serial wiring (ESP32 UART1)
#define MODEM_BAUD 115200
#define MODEM_TX_PIN 27
#define MODEM_RX_PIN 26

// Airtel APN (India)
#define MODEM_APN "airtelgprs.com"
#define MODEM_APN_USER ""
#define MODEM_APN_PASS ""

// HTTP ingest target (modem client)
#define TRACKER_API_HOST "trustseal.onrender.com"
#define VERIFIER_API_HOST "trustseal.onrender.com"

#define TRACKER_API_PORT 80
#define TRACKER_API_PATH "/api/v1/ingest/telemetry"
#define TRACKER_API_BEARER_TOKEN "Z8sEl7DdJ/PipQm+0MMm4Pk+IlQXT70WT49nBlV9ePU="

// Retry/backoff
#define TELEMETRY_RETRY_BASE_MS 5000
#define TELEMETRY_RETRY_MAX_MS 60000

#endif
