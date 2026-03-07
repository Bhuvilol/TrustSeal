#ifndef VERIFIER_ARDUINO_CONFIG_H
#define VERIFIER_ARDUINO_CONFIG_H

#define FP_BAUD 57600
#define FP_TX_PIN 17
#define FP_RX_PIN 16

#define FP_SCAN_INTERVAL_MS 1500
#define CUSTODY_SEND_INTERVAL_MS 2000

#define VERIFIER_DEVICE_ID "4fedec9d-eca7-428f-9803-d6728d874c54"
#define VERIFIER_USER_ID "a7110eff-cc43-4a64-a962-9d63ec8d46ee"
#define VERIFIER_SHIPMENT_ID "d8cb6561-7186-43b1-b4b3-f0925875c450"
#define VERIFIER_LEG_ID "b29e85bb-2bcc-4107-b614-d239932a0265"

#define VERIFIER_SIGNER_ADDRESS "0x0000000000000000000000000000000000000000"

#define CUSTODY_QUEUE_FILE "/custody_queue.ndjson"
#define CUSTODY_QUEUE_MAX_ENTRIES 200

#define VERIFIER_WIFI_SSID ""
#define VERIFIER_WIFI_PASSWORD ""
#define VERIFIER_NTP_SERVER_1 "pool.ntp.org"
#define VERIFIER_NTP_SERVER_2 "time.nist.gov"

#define VERIFIER_API_HOST "trustseal.onrender.com"
#define VERIFIER_API_PORT 80
#define VERIFIER_API_PATH "/api/v1/ingest/custody"
#define VERIFIER_API_BEARER_TOKEN ""
#define VERIFIER_API_USE_TLS 0

#define CUSTODY_RETRY_BASE_MS 5000
#define CUSTODY_RETRY_MAX_MS 60000

#if __has_include("verifier_config.local.h")
#include "verifier_config.local.h"
#endif

#endif
