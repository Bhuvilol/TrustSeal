# Managed Cloud Deployment

This is the v1 deployment target for TrustSeal:

- Frontend: Vercel
- Backend API: managed Python app host
- Worker runtime: separate process or separate service using the same backend image/code
- Database: managed PostgreSQL
- Redis Streams: managed Redis
- IPFS pinning: Pinata
- Chain RPC: managed Polygon RPC provider
- Contract network for sign-off: Polygon Amoy

## Services

### Frontend

- Build command: `npm run build`
- Output: `frontend/dist`
- Required env:
  - `VITE_API_BASE_URL`

### Backend API

- Start command: `python run.py`
- Process role: `APP_PROCESS_ROLE=api`
- Responsibilities:
  - auth
  - ingest endpoints
  - dashboard/query APIs
  - websocket endpoints
  - admin ops APIs

### Worker Service

- Start command: `python run_worker.py`
- Process role: `APP_PROCESS_ROLE=worker`
- Responsibilities:
  - Redis stream consumption
  - persistence
  - batching
  - IPFS pinning
  - custody gate
  - anchor requests
  - chain reconciliation/indexing

## Environment Groups

### Shared backend env

- database connectivity
- JWT/auth settings
- CORS allowlist
- Redis URL and stream names
- ingest signature/auth/replay settings
- Pinata/IPFS configuration
- chain RPC and contract metadata
- optional RAG settings

### Production-safe defaults

Set these on staging and production:

- `INGEST_VERIFY_SIGNATURES=true`
- `INGEST_DEVICE_AUTH_ENABLED=true`
- `INGEST_VERIFIER_AUTH_ENABLED=true`
- `WS_REQUIRE_AUTH=true`
- `APP_PROCESS_ROLE=api` for API service
- `APP_PROCESS_ROLE=worker` for worker service

## Contract Alignment

1. Deploy contract on Amoy from `contract/`.
2. Commit `contract/deployments/amoy.json`.
3. Copy emitted backend env values from `backend/.env.contract.amoy`.
4. Set backend `CHAIN_CONTRACT_ADDRESS` and `CHAIN_CONTRACT_ABI_PATH`.
5. Run chain indexer or `POST /api/v1/ops/reindex/chain` to reconcile state if needed.

## Staging Bring-Up

1. Provision managed Postgres and Redis.
2. Run backend migrations with `alembic upgrade head`.
3. Deploy backend API service.
4. Deploy worker service.
5. Deploy frontend with staging API base URL.
6. Configure Pinata and Polygon RPC secrets.
7. Deploy/update Amoy contract and backend env.
8. Verify:
   - backend health
   - ops worker status
   - Redis stream access
   - proof endpoints
   - contract event indexing

## Smoke Checklist

1. `POST /api/v1/ingest/telemetry` accepts a valid signed packet.
2. Event appears in Redis and persists to Postgres.
3. Batch finalizes and pins to IPFS.
4. `POST /api/v1/ingest/custody` accepts a valid verifier event.
5. Bundle becomes custody-verified and anchor-pending.
6. Anchor succeeds on Amoy.
7. Shipment proof view shows `bundle_id -> ipfs_cid -> tx_hash`.
8. Intelligence/ops screens show worker and backlog state.

## Operational Notes

- Do not run API and workers in the same process for staging unless resource limits are well understood.
- Keep deployment snapshots in repo; do not depend on generated Hardhat artifact directories at runtime.
- Firmware secret headers are placeholders only and must not be used outside local development.
