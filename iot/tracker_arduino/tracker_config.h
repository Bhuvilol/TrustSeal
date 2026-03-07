#ifndef TRACKER_ARDUINO_CONFIG_H
#define TRACKER_ARDUINO_CONFIG_H

#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22
#define LDR_PIN 34

#define TELEMETRY_SAMPLE_INTERVAL_MS 5000
#define TELEMETRY_SEND_INTERVAL_MS 2000

#define LDR_ADC_MAX 4095.0f
#define LDR_LUX_SCALE 1000.0f

#define TRACKER_SHIPMENT_ID "d8cb6561-7186-43b1-b4b3-f0925875c450"
#define TRACKER_DEVICE_ID "0cb901e3-6cf7-4be2-83f4-3a232a283e33"
#define TRACKER_DEVICE_UID "ESP32-TRACKER-001"
#define TRACKER_FIRMWARE_VERSION "0.1.0"

#define TELEMETRY_QUEUE_FILE "/telemetry_queue.ndjson"
#define TELEMETRY_QUEUE_MAX_ENTRIES 300

// These values are based on the working Arduino IDE modem test.
#define MODEM_BAUD 115200
#define MODEM_TX_PIN 17
#define MODEM_RX_PIN 16

#define MODEM_APN "jionet"
#define MODEM_APN_USER ""
#define MODEM_APN_PASS ""

#define TRACKER_API_HOST "trustseal.onrender.com"
#define TRACKER_API_PORT 80

#define TRACKER_API_PATH "/api/v1/ingest/telemetry"
#define TRACKER_API_BEARER_TOKEN ""
#define TRACKER_API_USE_TLS 0

#define TELEMETRY_RETRY_BASE_MS 5000
#define TELEMETRY_RETRY_MAX_MS 60000

#if __has_include("tracker_config.local.h")
#include "tracker_config.local.h"
#endif

#endif
