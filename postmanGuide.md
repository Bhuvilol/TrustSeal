# TrustSeal Postman Guide (Current Schema)

## Base URLs
- API root: `http://localhost:8000`
- Versioned API: `http://localhost:8000/api/v1`
- WebSocket base: `ws://localhost:8000/api/v1/ws`

## Authentication Flow
1. `POST /api/v1/auth/login` with form-data:
   - `username`: user email
   - `password`: user password
2. Copy `access_token` from response.
3. Add header in Postman for protected routes:
   - `Authorization: Bearer <access_token>`

## Enum Values
- `UserRole`: `factory`, `port`, `warehouse`, `customer`, `admin`, `authority`
- `DeviceStatus`: `active`, `inactive`, `maintenance`
- `ShipmentStatus`: `created`, `in_transit`, `docking`, `completed`, `compromised`
- `LegStatus`: `pending`, `in_progress`, `settled`

## Access Matrix (Current)
- Public:
  - `GET /`
  - `GET /health`
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/verify`
- Any authenticated active user:
  - `GET` routes for devices, shipments, shipment logs/telemetry/stats, sensor logs, legs, custody, `GET /api/v1/auth/me`, `GET /api/v1/debug/whoami`
- Factory:
  - Device `POST/PUT/DELETE`
  - Shipment `POST/PUT/POST settle`
  - Sensor log `POST`
  - Legs `POST/PUT/DELETE/POST start/complete`
- Admin or Customer:
  - Custody `POST/PUT`
- Admin:
  - Custody `DELETE`
  - `POST /api/v1/ingest`
  - `POST /api/v1/chat`

## Health
### GET `/health`
Response:
```json
{
  "status": "ok",
  "rag": "ready"
}
```
Possible degraded example:
```json
{
  "status": "degraded",
  "rag": "requires_postgresql"
}
```

## Auth Endpoints
### POST `/api/v1/auth/register`
Body:
```json
{
  "email": "admin@trustseal.io",
  "name": "System Admin",
  "role": "admin",
  "password": "pass123"
}
```

### POST `/api/v1/auth/login`
Content-Type: `application/x-www-form-urlencoded`
```text
username=admin@trustseal.io
password=pass123
```

### POST `/api/v1/auth/verify`
Body:
```json
{
  "email": "admin@trustseal.io",
  "verification_token": "token-from-register"
}
```

### GET `/api/v1/auth/me`
No body.

## Devices
### GET `/api/v1/devices/`
Query:
- `skip` (default `0`)
- `limit` (default `100`, max `1000`)
- `status` (`active|inactive|maintenance`, optional)

### POST `/api/v1/devices/` (Factory)
```json
{
  "device_uid": "TS-DEV-0009",
  "model": "Tracker X2",
  "firmware_version": "2.1.0",
  "battery_capacity_mAh": 6200,
  "status": "active"
}
```

### GET `/api/v1/devices/{device_id}`

### PUT `/api/v1/devices/{device_id}` (Factory)
```json
{
  "firmware_version": "2.2.0",
  "status": "maintenance"
}
```

### DELETE `/api/v1/devices/{device_id}` (Factory)

## Shipments
### GET `/api/v1/shipments/`
Query:
- `skip`, `limit`
- `status` (optional)
- `device_id` (optional UUID)

### POST `/api/v1/shipments/` (Factory)
```json
{
  "shipment_code": "SHIP-1009",
  "description": "Vaccines container",
  "origin": "Delhi",
  "destination": "Singapore",
  "device_id": "11111111-2222-3333-4444-555555555555"
}
```

### GET `/api/v1/shipments/{shipment_id}`

### PUT `/api/v1/shipments/{shipment_id}` (Factory)
```json
{
  "status": "in_transit",
  "destination": "Rotterdam"
}
```

### POST `/api/v1/shipments/{shipment_id}/logs`
Body: array of sensor logs
```json
[
  {
    "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "temperature": 4.8,
    "humidity": 54.1,
    "shock": 0.1,
    "light_exposure": false,
    "tilt_angle": 1.3,
    "latitude": 1.3521,
    "longitude": 103.8198,
    "speed": 35.2,
    "heading": 220.5,
    "hash_value": "0xloghash001"
  }
]
```

### GET `/api/v1/shipments/{shipment_id}/logs`

### GET `/api/v1/shipments/{shipment_id}/telemetry`
Query:
- `skip` (default `0`)
- `limit` (default `1000`, max `5000`)

### GET `/api/v1/shipments/{shipment_id}/sensor-stats`
Response:
```json
{
  "shipment_id": "uuid",
  "total_logs": 120,
  "temperature_sample_count": 120,
  "average_temperature": 25.67,
  "min_temperature": 15.31,
  "max_temperature": 33.08,
  "max_shock": 0.92,
  "first_recorded_at": "2026-02-20T06:00:00+00:00",
  "last_recorded_at": "2026-02-22T18:30:00+00:00",
  "has_temperature_breach": true
}
```

### POST `/api/v1/shipments/{shipment_id}/settle` (Factory)

## Sensor Logs
### GET `/api/v1/sensor-logs/`
Query:
- `skip`, `limit`
- `shipment_id` (optional UUID)

### POST `/api/v1/sensor-logs/` (Factory)
```json
{
  "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "temperature": 5.1,
  "humidity": 49.9,
  "shock": 0.3,
  "light_exposure": false,
  "tilt_angle": 2.5,
  "latitude": 1.31,
  "longitude": 103.81,
  "speed": 42.6,
  "heading": 188.1,
  "hash_value": "0xloghash002"
}
```

### GET `/api/v1/sensor-logs/{log_id}`

### DELETE `/api/v1/sensor-logs/{log_id}` (Admin)

## Legs
### GET `/api/v1/legs/`
Query:
- `skip`, `limit`
- `shipment_id` (optional UUID)

### POST `/api/v1/legs/` (Factory)
```json
{
  "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "leg_number": 1,
  "from_location": "Mumbai Port",
  "to_location": "Hamburg Port"
}
```

### GET `/api/v1/legs/{leg_id}`

### PUT `/api/v1/legs/{leg_id}` (Factory)
```json
{
  "status": "in_progress",
  "started_at": "2026-03-03T08:00:00Z"
}
```

### POST `/api/v1/legs/{leg_id}/start` (Factory)

### POST `/api/v1/legs/{leg_id}/complete` (Factory)

### DELETE `/api/v1/legs/{leg_id}` (Factory)

## Custody
### GET `/api/v1/custody/`
Query:
- `skip`, `limit`
- `shipment_id` (optional UUID)

### POST `/api/v1/custody/` (Admin or Customer)
```json
{
  "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "leg_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
  "verified_by": null,
  "biometric_verified": true,
  "blockchain_tx_hash": "0xtx123",
  "merkle_root_hash": "0xmerkle123"
}
```

### GET `/api/v1/custody/{checkpoint_id}`

### PUT `/api/v1/custody/{checkpoint_id}` (Admin or Customer)

### DELETE `/api/v1/custody/{checkpoint_id}` (Admin)

## Agentic RAG Endpoints
### POST `/api/v1/ingest` (Admin)
Purpose: chunk + embed + store in PostgreSQL/pgvector with tenant/device isolation.

Body:
```json
{
  "tenant_id": "tenant-alpha",
  "device_id": "DEV-LIVE-001",
  "raw_document": "Shipment SHP-2024-002 had temperature fluctuations ...",
  "metadata": {
    "source": "manual_import",
    "doc_type": "knowledge",
    "shipment_id": "79347f94-fbd0-4c58-b245-687f8a1c3745"
  }
}
```

Response:
```json
{
  "tenant_id": "tenant-alpha",
  "device_id": "DEV-LIVE-001",
  "chunks_inserted": 3,
  "document_ids": [
    "uuid-1",
    "uuid-2",
    "uuid-3"
  ]
}
```

### POST `/api/v1/chat` (Admin)
Purpose: ReAct-style agent with strict grounded retrieval.

Body:
```json
{
  "message": "Summarize thermal risk and next action for SHP-2024-002",
  "tenant_id": "tenant-alpha",
  "device_id": "DEV-LIVE-001",
  "session_id": "ops-session-01",
  "top_k": 5
}
```

`tenant_id` and `device_id` are optional in API schema:
- If missing, backend defaults to `tenant_id=user:<current_user_id>` and `device_id=*`.

Response:
```json
{
  "answer": "Situation: ...",
  "sources": ["uuid-1", "uuid-2"],
  "confidence": "high",
  "session_id": "ops-session-01"
}
```

If similarity threshold is not met:
```json
{
  "answer": "I don’t have enough information to answer that.",
  "sources": [],
  "confidence": "low",
  "session_id": "ops-session-01"
}
```

## Debug
### GET `/api/v1/debug/whoami`

## WebSocket
### WS `/api/v1/ws/shipments/{shipment_id}`
- Optional query token: `?token=<jwt>`
- Connect event:
```json
{
  "event": "ws.connected",
  "shipment_id": "uuid",
  "authenticated": true
}
```
- Ping text `ping` to receive:
```json
{
  "event": "ws.pong",
  "shipment_id": "uuid"
}
```

## Standard Errors
### 401
```json
{"detail":"Could not validate credentials"}
```

### 403
```json
{"detail":"Insufficient permissions for this operation"}
```

### 404
```json
{"detail":"Shipment not found"}
```

### 422
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```
