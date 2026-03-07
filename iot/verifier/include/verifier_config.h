#ifndef VERIFIER_CONFIG_H
#define VERIFIER_CONFIG_H

// R307S UART (ESP32 UART1)
#define FP_BAUD 57600
#define FP_TX_PIN 17
#define FP_RX_PIN 16

// Scan cadence
#define FP_SCAN_INTERVAL_MS 1500
#define CUSTODY_SEND_INTERVAL_MS 2000

// Canonical IDs (replace with real values per device/shipment context)
#define VERIFIER_DEVICE_ID "4fedec9d-eca7-428f-9803-d6728d874c54"
#define VERIFIER_USER_ID "a7110eff-cc43-4a64-a962-9d63ec8d46ee"
#define VERIFIER_SHIPMENT_ID "d8cb6561-7186-43b1-b4b3-f0925875c450"
#define VERIFIER_LEG_ID "b29e85bb-2bcc-4107-b614-d239932a0265"

// On-chain signer identity to include in custody packet
#define VERIFIER_SIGNER_ADDRESS "0x0000000000000000000000000000000000000000"

// Local buffering
#define CUSTODY_QUEUE_FILE "/custody_queue.ndjson"
#define CUSTODY_QUEUE_MAX_ENTRIES 200

// A7670C modem serial wiring (ESP32 UART2)
#define MODEM_BAUD 115200
#define MODEM_TX_PIN 27
#define MODEM_RX_PIN 26

// Airtel APN (India)
#define MODEM_APN "airtelgprs.com"
#define MODEM_APN_USER ""
#define MODEM_APN_PASS ""

// HTTP ingest target (modem client)
#define VERIFIER_API_HOST "trustseal.onrender.com"
#define VERIFIER_API_PORT 80
#define VERIFIER_API_PATH "/api/v1/ingest/custody"
#define VERIFIER_API_BEARER_TOKEN ""

// Retry/backoff
#define CUSTODY_RETRY_BASE_MS 5000
#define CUSTODY_RETRY_MAX_MS 60000

#endif
