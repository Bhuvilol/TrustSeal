# TrustSeal IoT Completion Plan

## Summary

Complete TrustSeal as a production-ready managed-cloud system with these locked boundaries:

- Core product scope: end-to-end supply-chain integrity platform
- Release bar: production-ready
- Deployment model: managed cloud
- Chain target for sign-off: Polygon Amoy only
- Hardware target: real tracker and verifier devices proven in staging
- Biometric target: full enrollment and template-management flow
- RAG/chat: retained as a secondary supported feature, not the core product path

The finished v1 must support:

1. Real tracker device telemetry signed on-device and delivered over network to backend ingest.
2. Real verifier device fingerprint match and signed custody approval flow.
3. Backend validation, replay/idempotency enforcement, Redis stream processing, Postgres persistence, IPFS pinning, custody gating, and Amoy anchor creation.
4. Frontend dashboards showing shipment state, telemetry timeline, custody timeline, proof chain, and operational status.
5. Production-oriented deployment, security, observability, runbooks, CI/CD, and staging validation with real devices.

## Current State

Based on repo inspection:

- Canonical ingest, worker pipeline, proof endpoints, and contract flow are present in partial/advanced form.
- Frontend has been partially shifted to canonical shipment/proof/ops APIs.
- Legacy backend paths for `sensor_logs` and `custody_checkpoints` were the main cleanup surface.
- Contract deploy flow exists and writes deployment snapshots.
- IoT tracker, verifier, and harness directories exist and are part of the active repo.
- Managed-service assumptions already exist in config: Supabase-style Postgres, Redis, Pinata, Polygon RPC, Vercel-style frontend hosting.

## Target Architecture

### Runtime Topology

- Frontend: Vercel
- Backend API: managed app host
- Worker execution: same backend deployment if acceptable for load, otherwise separate managed worker service using same codebase/config
- Postgres: managed PostgreSQL, preferably Supabase or equivalent
- Redis Streams: managed Redis
- IPFS pinning: Pinata
- Chain RPC: managed Polygon RPC provider
- Contract: single active Amoy deployment with deployment snapshot committed in `contract/deployments/amoy.json`

### Locked Data Path

`Tracker -> /api/v1/ingest/telemetry -> Redis -> Postgres -> batch -> IPFS -> custody gate -> Amoy anchor`

`Verifier -> fingerprint match + signer -> /api/v1/ingest/custody -> Redis -> Postgres -> custody gate unlock`

## Workstreams

### 1. Backend Canonicalization

Finish removal of legacy runtime behavior and make canonical models the only supported path.

Tasks:
- Remove all remaining runtime dependencies on `sensor_logs` and `custody_checkpoints`.
- Keep a dedicated stats schema file, but rename it from `sensor_log.py` to a canonical name such as `sensor_stats.py`.
- Ensure `shipments`, `proofs`, and `ops` routers expose only canonical pipeline-derived data.
- Remove obsolete comments, compatibility branches, and route references.
- Review tests and fixtures so no test depends on deleted legacy modules.

Public interface impact:
- Supported read/write API surface becomes:
  - `POST /api/v1/ingest/telemetry`
  - `POST /api/v1/ingest/custody`
  - `GET /api/v1/shipments/*`
  - `GET /api/v1/proofs/*`
  - `GET/POST /api/v1/ops/*`
  - `POST /api/v1/chat` and `POST /api/v1/ingest` for RAG only

### 2. Database and Migration Hardening

Bring DB schema to a final production migration state.

Tasks:
- Review all Alembic migrations for canonical pipeline completeness.
- Add any missing constraints/indexes for:
  - `telemetry_events`
  - `custody_transfers`
  - `telemetry_batches`
  - `ipfs_objects`
  - `chain_anchors`
  - `shipment_access`
- Add additive migration(s) for any post-cleanup schema changes.
- Decide whether legacy tables remain as unused historical tables or are dropped by migration.
Default for v1: keep them if already deployed anywhere, but mark them unsupported and unused in app code.
- Add migration verification step in CI.

Acceptance:
- Fresh `alembic upgrade head` works on empty DB.
- Upgrade path works from current repo migration state.
- All canonical uniqueness and foreign-key invariants are enforced.

### 3. Security and Identity

Move all security toggles from dev defaults to production-safe defaults and document exact operating modes.

Tasks:
- Enable and test:
  - `INGEST_VERIFY_SIGNATURES=true`
  - `INGEST_DEVICE_AUTH_ENABLED=true`
  - `INGEST_VERIFIER_AUTH_ENABLED=true`
  - `WS_REQUIRE_AUTH=true`
- Replace dev firmware keys with per-device and per-verifier provisioned keys.
- Define and implement key registry management:
  - device public key registration
  - verifier public key registration
  - rotation procedure
  - revocation procedure
- Implement production JWT/CORS hardening.
- Enforce HTTPS-only external traffic.
- Define secret storage strategy for managed cloud.
- Add least-privilege service separation for backend, worker, DB, Redis, IPFS, RPC.

Acceptance:
- Unsigned, replayed, duplicate, wrong-token, wrong-device, and wrong-verifier requests are rejected.
- Device identity and payload identity remain bound.
- WebSocket telemetry stream access is authenticated.

### 4. Tracker Firmware Completion

Complete the tracker as a real staging device flow.

Tasks:
- Build and validate the current PlatformIO tracker project.
- Prove:
  - sensor acquisition
  - local queue persistence
  - signature generation
  - retry/backoff
  - A7670C connectivity
  - backend ACK dequeue behavior
- Upgrade transport from plain HTTP to TLS if the modem/library path is viable.
If modem TLS is unstable in staging, lock an approved secure gateway or APN tunnel strategy and document it explicitly.
- Add key provisioning flow for device identity.
- Add manufacturing/config script or documented procedure for:
  - `device_id`
  - `shipment_id`
  - `pubkey_id`
  - private key install
  - APN/network configuration

Acceptance:
- Real tracker posts valid telemetry to staging backend and drains local queue on ACK.
- Network interruption produces retained queue and later successful replay.
- At least one staged shipment is driven by real tracker input.

### 5. Verifier Firmware and Enrollment System

Complete the verifier hardware path including full enrollment lifecycle.

Tasks:
- Build and validate the verifier PlatformIO project.
- Implement enrollment procedure for R307S templates:
  - create person record
  - associate verifier user identity
  - enroll template to device
  - list/check templates
  - revoke/delete template
- Decide where enrollment management lives:
  - recommended: backend-managed metadata + device-local template store
- Add backend APIs for verifier enrollment metadata and authorization.
- Ensure custody packet signing and transport are production-safe.
- Document operator workflow for verifier use during custody transfer.

Acceptance:
- Operator can enroll a person, match on device, generate a valid custody event, and unlock bundle anchoring.
- No anchor is emitted without valid recent custody evidence.

### 6. Worker Runtime and Reliability

Turn the Redis pipeline into an operationally reliable production service.

Tasks:
- Finalize worker deployment model:
  - recommended: separate worker process/service using same codebase
- Add startup separation for API-only versus worker-enabled processes.
- Add worker health endpoints or status reporting to ops API.
- Add replay-safe reconciliation job scheduling.
- Harden DLQ processing and operator requeue behavior.
- Define concurrency and throughput targets for staging and production.

Acceptance:
- Workers can be restarted independently.
- Stuck batches can be detected and reprocessed safely.
- DLQ behavior is observable and recoverable.

### 7. IPFS and Chain Reliability

Finish the proof side as an operationally reliable path.

Tasks:
- Validate Pinata pin flow with real staging credentials.
- Ensure CID capture, `content_hash`, and `size_bytes` are always recorded.
- Confirm contract event indexer sync and reconciliation on Amoy.
- Harden anchor retry/replacement behavior under nonce conflicts and RPC transient failures.
- Lock Amoy deployment artifact and backend chain env alignment.
- Add explorer/deep links in frontend proof UI.

Acceptance:
- `bundle_id -> ipfs_cid -> tx_hash` linkage is correct for real staging runs.
- Backend can recover anchor state from chain events.
- Proof endpoints remain correct after worker restarts.

### 8. Frontend Completion

Finish canonical frontend integration and operational UX.

Tasks:
- Complete Step 48-style canonical API consumption everywhere.
- Ensure pages use:
  - shipment overview
  - telemetry timeline
  - custody timeline
  - latest proof
  - ops pipeline status
- Add real pending/failed/retried stage UX.
- Add operator views for:
  - retry anchor
  - retry IPFS
  - retry custody gate
  - dead-letter reprocess
- Remove remaining synthetic or non-canonical data presentation from core screens.
- Keep RAG/chat UI as secondary admin capability.

Acceptance:
- A user can follow one shipment from telemetry through proof.
- A support/admin operator can diagnose failed pipeline stages from UI.
- No core page silently falls back to fake or legacy data.

### 9. RAG/Chat Secondary Completion

Keep the feature supported but scoped.

Tasks:
- Keep `POST /api/v1/chat` and `POST /api/v1/ingest` functional.
- Ensure degraded behavior is explicit if RAG infra is unavailable.
- Separate chat operationally from the critical pipeline in docs and monitoring.
- Restrict chat to admin/internal roles.
- Add minimum health checks and smoke tests.

Acceptance:
- Chat works if configured.
- Chat failure does not impact ingest, workers, proofs, or shipment views.

### 10. Deployment and CI/CD

Build the managed-cloud delivery path.

Tasks:
- Add or finalize CI for:
  - backend tests
  - frontend build
  - contract tests
  - migration check
- Add environment promotion flow:
  - local
  - staging
  - production
- Add deployment docs for:
  - backend service
  - worker service
  - frontend
  - managed Postgres
  - managed Redis
  - Pinata
  - RPC provider
- Define environment variable matrix by environment.
- Add smoke checks after deploy.

Acceptance:
- Fresh staging deployment is reproducible from repo docs.
- CI gates merges on test/build success.
- Contract deployment and backend env sync are deterministic.

### 11. Observability and Operations

Bring the system to production readiness.

Tasks:
- Structured logging everywhere with correlation/request/shipment IDs.
- Metrics for:
  - ingest rate
  - replay rejects
  - signature failures
  - queue backlog
  - batch finalization latency
  - IPFS failures
  - custody gate blocks
  - anchor success/failure
  - chain index lag
- Alerts for worker failure, Redis backlog, IPFS outage, chain outage, and DB saturation.
- Runbooks for:
  - anchor stuck
  - queue backlog
  - IPFS failure
  - verifier mismatch/enrollment issue
  - staging hardware issue
  - contract/RPC outage

Acceptance:
- An operator can tell why a shipment is blocked and what action to take.
- Common failure cases have documented recovery.

### 12. Staging Validation With Real Devices

This is the sign-off milestone.

Tasks:
- Provision staging env with real managed services.
- Flash real tracker and verifier devices.
- Enroll at least one verifier identity on device.
- Run at least one full staged shipment:
  - tracker telemetry
  - batch creation
  - IPFS pin
  - verifier match
  - custody acceptance
  - Amoy anchor
  - frontend proof visibility
- Run failure drills:
  - tracker offline then reconnect
  - Redis unavailable
  - IPFS unavailable
  - RPC unavailable
  - duplicate/replay ingest
  - custody rejection
- Capture evidence and final checklist.

Acceptance:
- One complete staged shipment succeeds end to end using real devices.
- Defined failure drills behave as expected.
- Proof chain is auditable from UI and backend.

## Public Interfaces and Type Changes

### Backend APIs

Canonical v1 interfaces to support and document:

- `POST /api/v1/ingest/telemetry`
- `POST /api/v1/ingest/custody`
- `GET /api/v1/shipments`
- `GET /api/v1/shipments/{shipment_id}`
- `GET /api/v1/shipments/{shipment_id}/overview`
- `GET /api/v1/shipments/{shipment_id}/telemetry`
- `GET /api/v1/shipments/{shipment_id}/sensor-stats`
- `GET /api/v1/shipments/{shipment_id}/legs`
- `GET /api/v1/shipments/{shipment_id}/custody`
- `GET /api/v1/proofs/shipments/{shipment_id}/latest`
- `GET /api/v1/proofs/bundles/{bundle_id}`
- `GET /api/v1/proofs/bundles/{bundle_id}/ipfs-link`
- `GET /api/v1/ops/pipeline-status`
- `POST /api/v1/ops/retry/anchor`
- `POST /api/v1/ops/retry/ipfs`
- `POST /api/v1/ops/retry/custody-gate`
- `POST /api/v1/ops/reprocess/dead-letter`
- `POST /api/v1/ops/reconcile`
- `POST /api/v1/ops/reindex/chain`

### Type and Naming Cleanup

Planned cleanup:
- rename backend `schemas/sensor_log.py` to a canonical stats-oriented file
- keep frontend on `TelemetryEvent`, `CustodyTransfer`, `ShipmentLatestProof`, `BundleProof`, `PipelineStatusResponse`
- remove remaining legacy naming from docs/comments

## Tests and Validation

### Backend

- Unit tests:
  - ingest verification
  - replay/idempotency
  - state machine guards
  - worker retry/DLQ
  - custody gate
  - anchor retry
  - chain indexer
  - ops/proofs/shipment routers
- Integration tests:
  - ingest -> Redis -> persistence
  - persistence -> batch -> IPFS
  - custody event -> gate -> anchor request
  - anchor submit -> chain index -> proof endpoints
- Migration tests:
  - fresh upgrade
  - upgrade from current migration chain

### Frontend

- build must pass
- API contract tests or typed mock tests for canonical endpoints
- key UI smoke coverage:
  - shipment details
  - proof panel
  - intelligence/ops
  - device logs
  - QR lookup

### Contract

- authorization
- custody sequence enforcement
- duplicate bundle prevention
- event integrity
- deploy script output correctness

### Firmware and Harness

- tracker signing and retry
- verifier match/no-match flow
- enrollment flows
- simulator compatibility with backend contracts
- serial NDJSON validator

### Staging Scenarios

- happy path with real devices
- tracker backlog drain after outage
- duplicate telemetry replay
- invalid signature rejection
- custody no-match block
- IPFS failure and retry
- chain RPC timeout and retry
- proof reconstruction from DB + chain index

## Rollout Sequence

1. Final backend canonical cleanup and type renames
2. Stabilize tests and migrations
3. Finalize frontend canonical screens
4. Finalize tracker firmware and secure provisioning
5. Finalize verifier firmware and enrollment lifecycle
6. Lock contract deployment and chain env
7. Add CI/CD and deployment docs
8. Stand up staging managed services
9. Run real-device staged shipment
10. Run failure drills and close gaps
11. Freeze release checklist
12. Promote to production

## Execution Docs

Use these documents for the actual staging rollout:

- [Staging Execution Checklist](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/md/STAGING_EXECUTION_CHECKLIST.md)
- [Environment Matrix](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/md/ENVIRONMENT_MATRIX.md)
- [Managed Cloud Deployment](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/md/MANAGED_CLOUD_DEPLOYMENT.md)
- [Contract Deploy Guide](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/contract/DEPLOY.md)

## Assumptions and Defaults Chosen

- v1 production readiness means strong staging validation plus production-grade deployment/ops posture, not immediate Polygon mainnet launch.
- Polygon Amoy is the required chain for v1 sign-off.
- Hosting target is managed cloud, not self-hosted Docker/VPS.
- Real devices are required in staging.
- Fingerprint enrollment is part of v1, not deferred.
- RAG/chat remains supported but is not on the critical path and must not block core shipment/proof functionality.
- Legacy `sensor_logs` and `custody_checkpoints` are removed from runtime code; if legacy DB tables already exist, they may remain physically present until a later cleanup migration unless an explicit drop migration is added.
- Backend test execution environment currently lacks `pytest`; enabling that is part of the delivery work, not a planning blocker.
