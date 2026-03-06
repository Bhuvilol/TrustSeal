# TrustSeal System Architecture and Data Flow

This document describes the TrustSeal IoT-to-blockchain pipeline as implemented in this repository. It focuses on the concrete system shape in code today: ESP32-based tracker and verifier devices, FastAPI ingestion, Redis Streams worker orchestration, PostgreSQL persistence, Pinata-backed IPFS pinning, and Polygon custody anchoring via the `SupplyChainRelay` smart contract.

## 1. System Goal

TrustSeal creates tamper-evident shipment custody records by combining:

- signed IoT telemetry from shipment trackers
- verifier-submitted custody approval events backed by fingerprint checks
- off-chain batch storage in IPFS
- on-chain custody anchoring on Polygon

The design keeps large telemetry off-chain while placing a compact cryptographic reference on-chain. In this repo, that reference is the IPFS CID plus the batch hash and bundle identity emitted by the contract.

## 2. High-Level Architecture

```text
Tracker ESP32 / Verifier ESP32
        |
        v
 FastAPI ingest API
        |
        v
   Redis Streams
        |
        v
 Persistence Worker
        |
        v
   Batch Worker
        |
        v
    IPFS Worker
        |
        v
 Custody Gate Worker
        |
        v
   Anchor Worker
        |
        v
 Polygon SupplyChainRelay
```

Supporting systems:

- PostgreSQL stores canonical operational state, metadata, indexes, bundle status, and chain anchor records.
- Pinata provides the IPFS pinning API used by the backend when `IPFS_PIN_ENABLED=true`.
- The React frontend reads shipment, proof, and ops views from the backend.
- Optional harness scripts under `iot/harness/` simulate tracker and verifier traffic.

## 3. Core Requirements and How the Repo Meets Them

### Tamper Evidence

- Devices sign telemetry and custody packets before upload.
- The backend can verify signatures and replay windows during ingest.
- Batches are hashed before pinning.
- IPFS stores content by CID, so changing bundle contents changes the identifier.
- Polygon anchoring makes the custody record append-only in practice.

### Scalability

- Ingestion is decoupled from downstream processing through Redis Streams consumer groups.
- Workers process telemetry, custody, bundle-ready, and anchor-request streams independently.
- PostgreSQL handles query-heavy operational reads while IPFS holds bundle payloads.

### Low Power Edge Devices

- The hardware guide uses ESP32 plus low-power digital sensors such as BME280 and ADXL345.
- The tracker and verifier firmware support local queueing so intermittent backhaul does not force continuous radio activity.

### Low Cost Anchoring

- Only custody-relevant finalized bundles are pinned and anchored.
- Raw telemetry is not written on-chain.
- The contract stores compact custody records rather than full sensor payloads.

### Reliability

- Redis stream retries use bounded exponential backoff.
- Failed stream messages are sent to a dead-letter stream.
- Devices buffer outbound records locally and retry until accepted.
- Batch and anchor state is persisted in PostgreSQL and can be reconstructed or replayed.

## 4. Physical and Edge Components

### Tracker Device

The tracker is an ESP32-based device with environmental and tamper-related sensors:

- **ESP32 MCU**: dual-core MCU with Wi-Fi/Bluetooth and common embedded interfaces such as UART, SPI, and I2C. Espressif documents operating ranges, power modes, and peripheral support in the ESP32 datasheet.
- **Bosch BME280**: temperature, humidity, and pressure sensor on I2C/SPI. Bosch documents its compact package and low-power operating profile.
- **Analog Devices ADXL345**: 3-axis accelerometer used for shock and motion detection. Analog Devices documents low-power operation and programmable measurement ranges.
- **LDR**: analog light sensor for simple enclosure-open or exposure detection.
- **SIMCom A7670C modem**: cellular backhaul from the tracker to the backend.

In this repo, the tracker wiring and firmware assumptions are documented in [iot/HARDWARE_SETUP_GUIDE.md](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/HARDWARE_SETUP_GUIDE.md) and [iot/tracker/README.md](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/tracker/README.md).

### Verifier Device

The verifier is also ESP32-based and includes:

- **R307S fingerprint module** connected over UART
- **A7670C modem** for custody event submission

The verifier performs an identity check at a custody handoff and sends a signed custody approval packet to the backend. In production, the fingerprint match should remain local to the verifier path; only the result and associated metadata should flow into backend records.

### Edge and Simulation Tools

The repo includes host-side simulators:

- [iot/harness/telemetry_simulator.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/harness/telemetry_simulator.py)
- [iot/harness/custody_simulator.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/harness/custody_simulator.py)

These are useful for validating end-to-end flow without hardware.

## 5. Backend Components

### 5.1 Ingestion API

The FastAPI ingress endpoints are:

- `POST /api/v1/ingest/telemetry`
- `POST /api/v1/ingest/custody`

The implementation is in [backend/app/routers/ingest.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/routers/ingest.py).

At ingest time the backend can enforce:

- device or verifier channel authentication
- signature verification
- duplicate suppression by event ID and idempotency key
- replay protection using timestamps and sequence numbers

On successful validation, the request is acknowledged with `202 Accepted`, recorded in PostgreSQL, and published into Redis Streams for downstream processing.

### 5.2 Redis Stream Orchestrator

The stream orchestrator is implemented in [backend/app/services/telemetry_stream_service.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/telemetry_stream_service.py).

It manages four streams:

- `telemetry_stream`
- `custody_stream`
- `bundle_ready_stream`
- `anchor_request_stream`

Each stream is consumed through a Redis consumer group. Processing failures are retried with exponential backoff and eventually copied to the configured dead-letter stream, `telemetry_dead_letter_stream`, if retry attempts are exhausted.

### 5.3 Persistence Worker

The persistence stage is implemented in [backend/app/services/persistence_worker.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/persistence_worker.py).

Its responsibility is:

- normalize stream payloads into database rows
- enforce the `queued -> persisted` state transition
- ensure telemetry and custody events exist canonically in PostgreSQL even if stream payloads are replayed

### 5.4 Batch Worker

The batch stage is implemented in [backend/app/services/batch_worker.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/batch_worker.py).

The worker:

- groups persisted telemetry events by `shipment_id`
- finalizes a bundle when either the minimum record threshold is met or the maximum batching window elapses
- forces batch finalization on custody events when `BATCH_FORCE_ON_CUSTODY=true`
- computes a canonical SHA-256 batch hash
- creates a `telemetry_batches` row with a monotonic per-shipment `epoch`

After finalization, it emits a `bundle_ready` event for IPFS processing.

### 5.5 IPFS Worker

The IPFS stage is implemented in [backend/app/services/ipfs_worker.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/ipfs_worker.py).

Its behavior is:

- reconstruct the finalized bundle payload JSON
- compute a local SHA-256 content hash
- call the Pinata pinning API when pinning is enabled
- store the returned CID in PostgreSQL
- transition the bundle from `finalized -> ipfs_pinned`

When pinning is disabled for local development, the worker records `ipfs-disabled` and a `skipped` pin status to keep the pipeline testable without external network dependencies.

### 5.6 Custody Gate Worker

The custody gate is implemented in [backend/app/services/custody_gate_worker.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/custody_gate_worker.py).

This is the explicit policy bridge between raw telemetry processing and custody anchoring. It checks that:

- the bundle is already IPFS-pinned or deliberately skipped in dev mode
- a recent valid custody transfer exists for the same shipment
- the custody event has a fingerprint result of `match`
- the custody event has already reached `persisted`

Only then does the batch advance from `ipfs_pinned -> custody_verified`.

### 5.7 Anchor Worker

The chain anchor stage is implemented in [backend/app/services/anchor_worker.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/anchor_worker.py) and [backend/app/services/batch_finalization_service.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/services/batch_finalization_service.py).

It performs:

- creation of a `chain_anchors` record
- transition `custody_verified -> anchor_pending`
- publication of an `anchor_request` stream message
- on-chain execution of `transferCustody(...)`
- transaction receipt waiting, retry, gas bumping, and nonce refresh
- final transition to `anchored` on success or `failed` on terminal error

### 5.8 PostgreSQL

PostgreSQL is the canonical operational datastore for:

- device, shipment, user, and ACL metadata
- raw telemetry event rows
- custody transfer rows
- telemetry batch rows
- IPFS object rows
- chain anchor rows

Relevant models include:

- [backend/app/models/telemetry_event.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/models/telemetry_event.py)
- [backend/app/models/custody_transfer.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/models/custody_transfer.py)
- [backend/app/models/telemetry_batch.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/models/telemetry_batch.py)
- [backend/app/models/ipfs_object.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/models/ipfs_object.py)
- [backend/app/models/chain_anchor.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/app/models/chain_anchor.py)

## 6. Blockchain Component

The contract is [contract/contracts/SupplyChainRelay.sol](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/contract/contracts/SupplyChainRelay.sol).

The core contract behavior is:

- only authorized callers may anchor custody
- one `(shipmentId, bundleId)` pair can only be anchored once
- the contract stores the current custodian per shipment
- each successful transfer emits a `CustodyTransferred` event

The current phase-5 transfer function is:

```solidity
transferCustody(
    string shipmentId,
    string bundleId,
    string bundleHash,
    address previousCustodian,
    string ipfsCid
)
```

The event stores:

- `shipmentId`
- `bundleId`
- `bundleHash`
- `previousCustodian`
- `newCustodian`
- `ipfsCid`
- `timestamp`

This means the on-chain proof is not just a CID pointer. It also includes a stable bundle identifier and the repository-computed batch hash used before IPFS pinning.

## 7. End-to-End Data Flow

### 7.1 Telemetry Path

1. The tracker samples temperature, humidity, shock, light, battery, and optional GPS data.
2. Firmware creates a telemetry packet containing `event_id`, `shipment_id`, `device_id`, `ts`, `seq_no`, metrics, payload hash, and signature.
3. The tracker sends the packet to `POST /api/v1/ingest/telemetry`.
4. The backend authenticates the channel if enabled, verifies the signature if enabled, rejects duplicates and replays, stores the row, and publishes a `telemetry` event into Redis Streams.
5. The persistence worker transitions the event to `persisted`.
6. The batch worker accumulates persisted telemetry for the shipment and finalizes a batch when configured thresholds are met.
7. The worker computes the canonical bundle JSON and SHA-256 batch hash, stores the batch row, and publishes a `bundle_ready` event.
8. The IPFS worker pins the bundle payload and stores the returned CID.
9. The custody gate waits until a matching recent custody approval exists.
10. The anchor worker sends the on-chain transaction and records the resulting transaction hash.

### 7.2 Custody Path

1. The verifier performs a fingerprint check and produces a custody packet containing `custody_event_id`, `shipment_id`, `leg_id`, verifier identities, fingerprint outcome, signer address, approval message hash, and signature.
2. The verifier sends the packet to `POST /api/v1/ingest/custody`.
3. The backend runs the same ingest protections: auth, signature verification, dedupe, and replay checks.
4. The custody event is written to PostgreSQL and published into `custody_stream`.
5. The persistence worker advances the custody row to `persisted`.
6. The batch worker can force immediate finalization of the shipment bundle when custody is the trigger.
7. Once the resulting bundle is pinned, the custody gate verifies that a recent persisted `fingerprint_result == "match"` event exists.
8. If the gate passes, the batch becomes eligible for chain anchoring.

### 7.3 Bundle Payload Shape

The bundle payload reconstructed in the backend is a canonical JSON array ordered by event timestamp. Each element contains:

- `event_id`
- `ts`
- `seq_no`
- `metrics`
- `gps`
- `payload_hash`
- `device_id`

This canonicalization matters because the backend computes `batch_hash = sha256(canonical_json)` before pinning and uses that hash during chain anchoring.

## 8. State Machine

The implemented batch lifecycle is stricter than the generic architecture summary:

```text
telemetry/custody event:
verified -> queued -> persisted -> bundled

bundle:
open -> finalized -> ipfs_pinned -> custody_verified -> anchor_pending -> anchored
                                            \-> failed

anchor:
pending -> submitted -> confirmed
                 \-> failed
```

This staged model exists to make recovery and observability explicit. A bundle can fail independently in IPFS, custody gating, or blockchain anchoring without losing the upstream event history.

## 9. Interfaces and Protocols

### Device to Backend

- transport: HTTPS
- payload: JSON
- integrity: signature over payload and timestamp fields
- auth: optional bearer token or device/verifier auth enforcement

### Backend to Redis

- transport: Redis protocol over TCP
- structure: append-only stream entries with event metadata and compact JSON payload

### Backend to IPFS

- provider: Pinata pinning API
- endpoint: `pinJSONToIPFS`
- payload: JSON object containing metadata plus bundle content

### Backend to Polygon

- protocol: Ethereum JSON-RPC over HTTP(S)
- client: `web3.py`
- contract call: `transferCustody(...)`

### Backend to Frontend

- transport: HTTPS and optional websocket channels
- data source: PostgreSQL-backed APIs and proof lookup endpoints

## 10. Reliability and Recovery

### Device-Side Buffering

The tracker and verifier are designed to queue outbound packets locally and retry until the backend acknowledges them. That protects against ordinary modem outages and transient API failures.

### Queue Retry and Dead-Letter Handling

Redis stream processing uses:

- bounded retry attempts
- exponential backoff
- dead-letter routing when retries are exhausted

This avoids silent data loss while preventing one poison message from blocking the stream indefinitely.

### Batch Recovery

Because batch status is stored in PostgreSQL, a crashed worker can resume processing from persisted rows and replay stream stages without losing canonical shipment history.

### Chain Retry

Chain anchoring includes:

- nonce refresh when needed
- gas bumping for replacement transactions
- receipt timeout handling
- capped retry attempts

### Failure Domains

Typical failure points and outcomes:

- ingest API unavailable: device retries later
- Redis unavailable: API rejects with queue-unavailable semantics
- IPFS unavailable: batch transitions to `failed`
- missing custody proof: batch remains blocked before anchoring
- chain RPC or revert: anchor row and batch row record the failure state and message

## 11. Security Model

### Cryptographic Integrity

- payload hash and signature fields protect packets in transit
- IPFS CIDs and the repository batch hash protect bundle integrity
- chain events protect custody ordering and anchor permanence

### Authentication and Authorization

- devices and verifiers can be authenticated separately
- only authorized chain callers can invoke `transferCustody`
- shipment access controls are modeled in PostgreSQL

### Replay Protection

Replay resistance is based on:

- timestamp validation windows
- sequence numbers for telemetry
- idempotency keys and event IDs

### Privacy

The repo design keeps biometric templates off-chain. The backend stores the outcome of verification, not the fingerprint image or template itself.

## 12. Deployment and Configuration Notes

The main configuration surface is [backend/.env.example](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/.env.example).

Important groups:

- Redis stream names, consumer group, retries, and dead-letter settings
- batch thresholds such as `BATCH_MIN_RECORDS` and `BATCH_MAX_WINDOW_SECONDS`
- custody gate age window via `CUSTODY_GATE_MAX_AGE_SECONDS`
- IPFS pinning toggle and Pinata JWT
- Polygon RPC, chain ID, contract address, ABI path, and signer key

Current default development posture:

- signature verification is disabled by default
- device and verifier auth are disabled by default
- IPFS pinning is disabled by default
- chain anchoring is disabled by default

That is appropriate for local iteration, but production deployment should enable all four.

## 13. Why This Architecture Fits TrustSeal

This repository intentionally separates:

- high-volume telemetry ingestion
- durable operational state
- immutable off-chain evidence
- low-frequency public blockchain anchoring

That separation is the reason the system can scale operationally without paying chain fees for every reading, while still producing a verifiable custody proof for each finalized shipment handoff.

## 14. Reference Sources

The implementation choices in this repo align with the following official or vendor sources:

1. Bosch Sensortec, BME280 product page and datasheet: <https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/>
2. Analog Devices, ADXL345 product page and datasheet: <https://www.analog.com/en/products/adxl345.html>
3. Espressif, ESP32 series documentation and datasheet portal: <https://www.espressif.com/en/products/socs/esp32>
4. Redis documentation, Streams data type: <https://redis.io/docs/latest/develop/data-types/streams/>
5. IPFS documentation, concepts and content addressing: <https://docs.ipfs.tech/concepts/how-ipfs-works/>
6. IPFS documentation, content identifiers (CID): <https://docs.ipfs.tech/concepts/content-addressing/>
7. Pinata documentation, pinning API: <https://docs.pinata.cloud/api-reference/endpoint/ipfs/pin-json-to-ipfs>
8. Polygon documentation portal: <https://docs.polygon.technology/>
9. PostgreSQL documentation portal: <https://www.postgresql.org/docs/>

Notes:

- Exact A7670C and R307S module specifications vary by board vendor and distributor packaging. For this repo, the hardware guide should be treated as the primary integration reference, while final production selections should be validated against the exact modem and fingerprint module datasheets being sourced.
