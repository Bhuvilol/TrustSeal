# TrustSeal Staging Execution Checklist

This is the step-by-step path to get TrustSeal into a working staging environment.

Use this in order. Do not skip ahead.

## Phase 1: Provision Managed Services

Goal: create the external dependencies the application needs.

### 1. PostgreSQL

- Provision a managed PostgreSQL database.
- Record:
  - host
  - port
  - database name
  - username
  - password
  - SSL mode

### 2. Redis

- Provision a managed Redis instance.
- Record:
  - Redis URL
  - password if required
  - TLS requirement if required by provider

### 3. Pinata

- Create or use an existing Pinata account.
- Generate a JWT for server-side pinning.
- Keep it only in backend and worker secrets.

### 4. Polygon Amoy RPC

- Create an RPC endpoint for Polygon Amoy.
- Record the Amoy HTTPS RPC URL.

### 5. Deployment Targets

- Frontend target: Vercel
- Backend API target: managed Python app host
- Worker target: separate process or separate managed service

## Phase 2: Prepare Environment Variables

Goal: fill in staging configuration with real values.

Use [backend/.env.example](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/backend/.env.example) and [frontend/.env.example](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/frontend/.env.example) as the base.

Also use [md/ENVIRONMENT_MATRIX.md](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/md/ENVIRONMENT_MATRIX.md).

### Backend API

- Set `APP_PROCESS_ROLE=api`
- Enable:
  - `INGEST_VERIFY_SIGNATURES=true`
  - `INGEST_DEVICE_AUTH_ENABLED=true`
  - `INGEST_VERIFIER_AUTH_ENABLED=true`
  - `WS_REQUIRE_AUTH=true`
- Set real DB, Redis, JWT, Pinata, and RPC values.
- Leave `CHAIN_ANCHOR_ENABLED=false` until contract deploy is complete.

### Worker

- Set `APP_PROCESS_ROLE=worker`
- Use the same DB, Redis, Pinata, and chain configuration as backend API.
- After contract deploy, set `CHAIN_ANCHOR_ENABLED=true`.

### Frontend

- Set `VITE_API_BASE_URL` to the staging backend URL.
- Set `VITE_TELEMETRY_WS_ENABLED=true` only after websocket auth is confirmed.

## Phase 3: Deploy Backend and Run Migrations

Goal: bring up the backend and database schema.

### 1. Run migrations

```powershell
cd backend
alembic upgrade head
```

### 2. Deploy API service

Start command:

```powershell
python run.py
```

### 3. Deploy worker service

Start command:

```powershell
python run_worker.py
```

### 4. Verify basics

- API starts successfully
- worker starts successfully
- database migrations are applied
- Redis connectivity works
- worker status endpoint responds

Recommended checks:

- `GET /api/v1/ops/workers/status`
- `GET /api/v1/ops/pipeline-status`

## Phase 4: Deploy Contract to Amoy

Goal: get the final TrustSeal contract live on staging chain.

Follow [contract/DEPLOY.md](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/contract/DEPLOY.md).

### 1. Deploy

```powershell
cd contract
npm run deploy:amoy
```

### 2. Capture outputs

- `contract/deployments/amoy.json`
- `backend/.env.contract.amoy`

### 3. Update backend and worker env

Set:

- `CHAIN_RPC_URL_AMOY`
- `CHAIN_CHAIN_ID=80002`
- `CHAIN_CONTRACT_ADDRESS`
- `CHAIN_CONTRACT_ABI_PATH=../contract/deployments/amoy.json`
- `CHAIN_PRIVATE_KEY`

Then enable:

- `CHAIN_ANCHOR_ENABLED=true`
- `CHAIN_INDEXER_ENABLED=true`

## Phase 5: Smoke Test Without Hardware

Goal: prove the full pipeline before flashing real devices.

### 1. Telemetry ingest

Use:

- [iot/harness/telemetry_simulator.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/harness/telemetry_simulator.py)

Expected result:

- telemetry accepted
- telemetry appears in Postgres
- batch finalizes
- IPFS pin happens or simulated pin metadata appears

### 2. Custody ingest

Use:

- [iot/harness/custody_simulator.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/harness/custody_simulator.py)

Expected result:

- custody accepted
- custody gate passes
- anchor is requested
- Amoy transaction is created
- proof endpoints show `bundle_id -> ipfs_cid -> tx_hash`

### 3. Verify UI

- shipment details page shows telemetry and custody
- proof panel shows CID and tx hash
- intelligence page shows worker and backlog state

## Phase 6: Real Device Preparation

Goal: move from simulators to real hardware.

### Tracker

- provision real `device_id`
- provision real `shipment_id`
- provision real `pubkey_id`
- replace dev private key
- confirm APN and modem connectivity

### Verifier

- provision real `verifier_device_id`
- replace dev private key
- confirm R307S is working
- enroll at least one identity on device

## Phase 7: Real Device End-to-End Run

Goal: prove a real shipment flow in staging.

### Success criteria

- tracker sends signed telemetry
- verifier sends signed custody event with fingerprint match
- batch is pinned to IPFS
- custody gate passes
- anchor lands on Amoy
- frontend shows proof linkage correctly

Capture:

- shipment ID
- bundle ID
- IPFS CID
- tx hash
- screenshots of dashboard and proof panel

## Phase 8: Failure Drills

Goal: validate operational resilience.

Run these after the happy path:

- tracker offline then reconnect
- duplicate telemetry replay
- invalid signature ingest
- Redis unavailable
- IPFS unavailable
- RPC unavailable
- custody reject or no-match

For each drill record:

- expected system behavior
- actual behavior
- recovery path
- whether manual ops action was needed

## Phase 9: Sign-Off Gate

Do not call staging complete until all are true:

- backend tests pass
- frontend build passes
- contract tests pass
- staging migrations applied
- API and worker deployed
- Amoy contract deployed and aligned
- simulator smoke path passes
- real device path passes
- failure drills recorded
