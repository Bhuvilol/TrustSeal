# TrustSeal Environment Matrix

This file defines what each runtime needs in staging.

## Backend API

### Required

- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `BACKEND_CORS_ORIGINS`
- `POSTGRES_SERVER`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`
- `REDIS_URL`
- `APP_PROCESS_ROLE=api`
- `INGEST_VERIFY_SIGNATURES=true`
- `INGEST_DEVICE_AUTH_ENABLED=true`
- `INGEST_VERIFIER_AUTH_ENABLED=true`
- `INGEST_DEVICE_TOKENS_JSON`
- `INGEST_VERIFIER_TOKENS_JSON`
- `INGEST_DEVICE_PUBLIC_KEYS_JSON`
- `INGEST_VERIFIER_PUBLIC_KEYS_JSON`
- `WS_REQUIRE_AUTH=true`

### Required after contract deploy

- `CHAIN_RPC_URL_AMOY`
- `CHAIN_CHAIN_ID=80002`
- `CHAIN_CONTRACT_ADDRESS`
- `CHAIN_CONTRACT_ABI_PATH=../contract/deployments/amoy.json`
- `CHAIN_INDEXER_ENABLED=true`

### Usually enabled

- `TELEMETRY_PIPELINE_MODE=dual`
- `CHAIN_ANCHOR_ENABLED=false` on API unless API is also used for ops fallback

## Worker

### Required

- all database settings
- all Redis settings
- all ingest verification settings
- `APP_PROCESS_ROLE=worker`
- `IPFS_PIN_ENABLED=true`
- `IPFS_PIN_ENDPOINT=https://api.pinata.cloud/pinning/pinJSONToIPFS`
- `IPFS_PIN_JWT`

### Required after contract deploy

- `CHAIN_RPC_URL_AMOY`
- `CHAIN_CHAIN_ID=80002`
- `CHAIN_PRIVATE_KEY`
- `CHAIN_CONTRACT_ADDRESS`
- `CHAIN_CONTRACT_ABI_PATH=../contract/deployments/amoy.json`
- `CHAIN_ANCHOR_ENABLED=true`
- `CHAIN_INDEXER_ENABLED=true`

## Frontend

### Required

- `VITE_API_BASE_URL`

### Optional after websocket validation

- `VITE_TELEMETRY_WS_ENABLED=true`

## Contract Deployment

### Required for Amoy deploy

- `CHAIN_RPC_URL_AMOY`
- `CHAIN_PRIVATE_KEY`

### Outputs after deploy

- `contract/deployments/amoy.json`
- `backend/.env.contract.amoy`

## Pinata

### Required

- server-side Pinata JWT only

### Must not be exposed to frontend

- `IPFS_PIN_JWT`

## Device/Verifier Identity Material

### Tracker provisioning inputs

- `device_id`
- `shipment_id`
- `pubkey_id`
- device private key
- matching server-side public key in `INGEST_DEVICE_PUBLIC_KEYS_JSON`
- matching device token in `INGEST_DEVICE_TOKENS_JSON` if token auth is used

### Verifier provisioning inputs

- `verifier_device_id`
- verifier private key
- matching server-side public key in `INGEST_VERIFIER_PUBLIC_KEYS_JSON`
- matching verifier token in `INGEST_VERIFIER_TOKENS_JSON` if token auth is used

## Recommended Staging Defaults

- `BATCH_MIN_RECORDS=10`
- `BATCH_MAX_WINDOW_SECONDS=60`
- `BATCH_FORCE_ON_CUSTODY=true`
- `CUSTODY_GATE_MAX_AGE_SECONDS=1800`
- `CHAIN_ANCHOR_MAX_ATTEMPTS=3`
- `CHAIN_INDEXER_CONFIRMATIONS=2`

These keep staging feedback fast without changing the core pipeline model.
