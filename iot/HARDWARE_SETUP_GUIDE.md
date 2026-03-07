# IoT Hardware Setup Guide

Complete guide to connect and test TrustSeal IoT hardware.

---

## Hardware Components

### Tracker Device
- **ESP32 DevKit** (main controller)
- **BME280** (temperature, humidity, pressure sensor)
- **ADXL345** (3-axis accelerometer for shock detection)
- **LDR** (light sensor)
- **A7670C** (cellular modem for data transmission)

### Verifier Device
- **ESP32 DevKit** (main controller)
- **R307S** (fingerprint sensor module)
- **A7670C** (cellular modem for data transmission)

---

## Step 1: Hardware Wiring

### Tracker Wiring

**I2C Sensors (BME280 + ADXL345)**:
```
ESP32          BME280/ADXL345
GPIO 21   →    SDA
GPIO 22   →    SCL
3.3V      →    VCC
GND       →    GND
```

**Light Sensor (LDR)**:
```
ESP32          LDR
GPIO 34   →    Signal (with 10kΩ pull-down resistor)
3.3V      →    VCC
```

**A7670C Cellular Modem**:
```
ESP32          A7670C
GPIO 27   →    RX
GPIO 26   →    TX
5V        →    VCC (or use external 5V power supply)
GND       →    GND
```

### Verifier Wiring

**R307S Fingerprint Sensor**:
```
ESP32          R307S
GPIO 17   →    TX (R307S RX)
GPIO 16   →    RX (R307S TX)
5V        →    VCC
GND       →    GND
```

**A7670C Cellular Modem**:
```
ESP32          A7670C
GPIO 27   →    RX
GPIO 26   →    TX
5V        →    VCC
GND       →    GND
```

---

## Step 2: Choose Firmware Workflow

Primary workflow for current bring-up:

1. Use Arduino IDE with:
   - `iot/tracker_arduino/tracker_arduino.ino`
   - `iot/verifier_arduino/verifier_arduino.ino`
2. Keep `iot/harness/` available for backend smoke tests before hardware flashing.

PlatformIO trees still exist, but they are not the preferred bring-up path for today.

If your deployed backend is HTTPS-only, run the local bridge first:

```powershell
python scripts/run_device_bridge.py
```

Then point both Arduino configs to your laptop LAN IP on port `8081`.

Generate matching local tokens and private keys with:

```powershell
backend\.venv\Scripts\python.exe scripts/provision_arduino_devices.py
```

---

## Step 3: Configure Tracker Firmware

### 3.1 Edit Configuration

Open `iot/tracker_arduino/tracker_config.h` and set:

```cpp
// Modem Configuration
#define MODEM_RX_PIN 16
#define MODEM_TX_PIN 17
#define MODEM_BAUD 115200
#define MODEM_APN "jionet"  // Change to your carrier

// API Configuration
#define TRACKER_API_HOST "your-server-host"
#define TRACKER_API_PORT 80
#define TRACKER_API_PATH "/api/v1/ingest/telemetry"

// Legacy bearer-token field still exists in firmware, but backend canonical ingest auth is:
// X-Device-Id + X-Device-Token
// Keep real tokens outside committed files.
```

### 3.2 Build and Flash

```powershell
Open `iot/tracker_arduino/tracker_arduino.ino` in Arduino IDE
Select the ESP32 board and port
Upload the sketch
Open Serial Monitor
```

### 3.3 What to Observe

**Serial Output** should show:
```
Initializing sensors...
BME280 initialized
ADXL345 initialized
Connecting to cellular network...
Network connected
Sending telemetry...
{"event_id":"...","temperature_c":25.5,...}
Response: 202 Accepted
Packet dequeued
```

**Success Indicators**:
- ✅ Sensors initialize without errors
- ✅ Cellular modem connects to network
- ✅ HTTP POST returns 202 Accepted
- ✅ Packets are dequeued from local queue

---

## Step 4: Configure Verifier Firmware

### 4.1 Edit Configuration

Open `iot/verifier_arduino/verifier_config.h` and set:

```cpp
// Fingerprint Sensor
#define FP_TX_PIN 17
#define FP_RX_PIN 16
#define FP_BAUD 57600

// Modem Configuration
#define MODEM_RX_PIN 26
#define MODEM_TX_PIN 27
#define MODEM_BAUD 115200
#define MODEM_APN "jionet"

// API Configuration
#define VERIFIER_API_HOST "your-server-host"
#define VERIFIER_API_PORT 80
#define VERIFIER_API_PATH "/api/v1/ingest/custody"
```

### 4.2 Enroll Fingerprints

Before first use, enroll fingerprints in R307S:
1. Use R307S demo software or Arduino sketch
2. Enroll at least one fingerprint (ID: 1)
3. Note the template ID for testing

### 4.3 Build and Flash

```powershell
Open `iot/verifier_arduino/verifier_arduino.ino` in Arduino IDE
Select the ESP32 board and port
Upload the sketch
Open Serial Monitor
```

Important wiring note:
- `FP_RX_PIN` / `FP_TX_PIN` are for the R307S fingerprint sensor.
- `MODEM_RX_PIN` / `MODEM_TX_PIN` are a separate UART for the A7670C modem.
- Do not put both devices on the same ESP32 pins.

### 4.4 What to Observe

**Serial Output** should show:
```
Initializing R307S...
R307S initialized
Place finger on sensor...
Fingerprint detected
Match found: ID=1, Score=120
Sending custody event...
{"custody_event_id":"...","fingerprint_result":"match",...}
Response: 202 Accepted
```

**Success Indicators**:
- ✅ R307S initializes
- ✅ Fingerprint scan works
- ✅ Match detected
- ✅ HTTP POST returns 202 Accepted

---

## Step 5: Test Without Hardware (Simulators)

If you don't have hardware yet, use the test harnesses:

### 5.1 Setup Simulators

```powershell
cd iot/harness
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 5.2 Simulate Telemetry

```powershell
python telemetry_simulator.py `
  --base-url http://localhost:8000 `
  --shipment-id 11111111-1111-1111-1111-111111111111 `
  --device-id 22222222-2222-2222-2222-222222222222 `
  --count 5 `
  --device-token your-device-token
```

**What to Observe**:
```
Sending telemetry event 1/5...
✓ Event accepted: event_id=...
Sending telemetry event 2/5...
✓ Event accepted: event_id=...
...
```

### 5.3 Simulate Custody Transfer

```powershell
python custody_simulator.py `
  --base-url http://localhost:8000 `
  --shipment-id 11111111-1111-1111-1111-111111111111 `
  --leg-id 33333333-3333-3333-3333-333333333333 `
  --verifier-device-id 44444444-4444-4444-4444-444444444444 `
  --verifier-user-id 55555555-5555-5555-5555-555555555555 `
  --verifier-token your-verifier-token
```

**What to Observe**:
```
Sending custody event...
✓ Custody event accepted: custody_event_id=...
```

---

## Step 6: Verify Backend Processing

### 6.1 Check Pipeline Status

```powershell
curl -H "Authorization: Bearer <admin-token>" "http://localhost:8000/api/v1/ops/pipeline-status?shipment_id=<shipment-id>"
```

**Look for**:
```json
{
  "redis": {
    "telemetry_stream_len": 5,  // Events in queue
    "custody_stream_len": 1
  }
}
```

### 6.2 Check Worker Logs

In backend terminal, look for:
```
[persistence_worker] Processing event from stream
[persistence_worker] Event persisted: event_id=...
[batch_worker] Checking for finalization triggers
[batch_worker] Batch created for shipment: ...
```

### 6.3 Query Telemetry

```powershell
curl "http://localhost:8000/api/v1/shipments/11111111-1111-1111-1111-111111111111/telemetry"
```

**Expected**: List of telemetry events

---

## Step 7: Troubleshooting

### Tracker Issues

**Problem**: Sensors not initializing
- Check I2C wiring (SDA/SCL)
- Verify 3.3V power supply
- Check I2C address (BME280: 0x76 or 0x77, ADXL345: 0x53)

**Problem**: Cellular modem not connecting
- Check UART wiring (RX/TX crossed)
- Verify APN settings for your carrier
- Check SIM card is inserted and activated
- Ensure 5V power supply (A7670C needs more current)

**Problem**: HTTP POST fails
- Verify backend is running and accessible
- Check API_HOST and API_PORT settings
- Test with curl from same network
- Check firewall rules

### Verifier Issues

**Problem**: R307S not responding
- Check UART wiring (RX/TX crossed)
- Verify baud rate (57600)
- Check 5V power supply
- Try R307S demo software first

**Problem**: Fingerprint not matching
- Re-enroll fingerprint
- Clean sensor surface
- Press finger firmly
- Check lighting conditions

### Simulator Issues

**Problem**: Connection refused
- Verify backend is running: `curl http://localhost:8000/health`
- Check firewall settings
- Use correct IP address (not localhost if remote)

**Problem**: 422 Validation Error
- Check required fields in payload
- Verify hash format (64-character hex)
- Check timestamp format (ISO 8601)

---

## Step 8: Monitor End-to-End Flow

### 8.1 Send Test Data

**Option A**: Use hardware
- Power on tracker
- Wait for telemetry transmission
- Trigger verifier with fingerprint

**Option B**: Use simulators
```powershell
# Terminal 1: Send telemetry
python telemetry_simulator.py --base-url http://localhost:8000 --count 10

# Terminal 2: Send custody
python custody_simulator.py --base-url http://localhost:8000
```

### 8.2 Watch Backend Logs

Look for complete flow:
```
[ingest] Telemetry received: event_id=...
[persistence_worker] Event persisted
[batch_worker] Batch finalized: bundle_id=...
[ipfs_worker] Pinning to IPFS...
[ipfs_worker] IPFS CID captured: Qm...
[custody_gate_worker] Custody verified
[anchor_worker] Submitting to blockchain...
[anchor_worker] Transaction confirmed: tx_hash=0x...
```

### 8.3 Check Frontend

1. Start frontend: `cd frontend && npm run dev`
2. Open http://localhost:5173
3. Navigate to shipment details
4. Verify ProofPanel shows:
   - Bundle ID
   - IPFS CID with link
   - Blockchain transaction with link

---

## Hardware Checklist

### Before Deployment

- [ ] All sensors tested and calibrated
- [ ] Cellular modem connects reliably
- [ ] SIM card activated with data plan
- [ ] API endpoints accessible from device network
- [ ] Firmware flashed with production keys
- [ ] Local queue tested (power loss recovery)
- [ ] Battery life tested
- [ ] Enclosure protects from environment
- [ ] Device IDs registered in backend
- [ ] Fingerprints enrolled in verifier

### Production Settings

- [ ] Change development keys to production keys
- [ ] Replace placeholder secret headers with provisioned keys
- [ ] Enable signature verification in backend
- [ ] Enable device authentication
- [ ] Set up monitoring and alerts
- [ ] Configure retry limits appropriately
- [ ] Test failover scenarios
- [ ] Document device provisioning process

---

## Quick Reference

### Tracker Serial Commands
```
# View queue status
queue

# Clear queue
clear

# Force send
send
```

### Verifier Serial Commands
```
# Enroll fingerprint
enroll <id>

# Delete fingerprint
delete <id>

# Test match
test
```

### Backend Endpoints
```
POST /api/v1/ingest/telemetry     # Tracker data
POST /api/v1/ingest/custody       # Verifier data
GET  /api/v1/ops/pipeline-status  # Check processing
GET  /api/v1/shipments/{id}/telemetry  # Query data
```

---

## Support

For issues:
1. Check serial monitor output
2. Review backend logs
3. Test with simulators first
4. Verify network connectivity
5. Check API documentation: http://localhost:8000/docs

