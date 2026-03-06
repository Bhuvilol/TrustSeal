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
#define VERIFIER_USER_ID "verifier_001"
#define VERIFIER_SHIPMENT_ID "ROvhMsIvHIicFREIcS7XSb/FystevE0iJKk/wV0wvzw="
#define VERIFIER_LEG_ID "gK4j0+KmxDPNOke3O63yhsDnHb0Vr2BSFBaGDfBqkTU="

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
#define VERIFIER_API_HOST "https://trustseal.onrender.com"
#define VERIFIER_API_PORT 80
#define VERIFIER_API_PATH "/api/v1/ingest/custody"
#define VERIFIER_API_BEARER_TOKEN "HLiUuqINiHTNX0fkaFnDcqgMR+wL7p30Y6pGWEvMuqA="

// Retry/backoff
#define CUSTODY_RETRY_BASE_MS 5000
#define CUSTODY_RETRY_MAX_MS 60000

#endif
