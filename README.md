# TrustSeal IoT

Full-stack supply-chain integrity platform with signed IoT telemetry, Redis-backed pipeline processing, IPFS bundle storage, and Polygon custody anchoring.

Detailed architecture reference: [md/TRUSTSEAL_SYSTEM_ARCHITECTURE.md](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/md/TRUSTSEAL_SYSTEM_ARCHITECTURE.md)

## Stack

- Backend: FastAPI, PostgreSQL, Redis Streams, SQLAlchemy, Alembic
- Frontend: React, Vite, TypeScript, Tailwind, React Query
- Blockchain: Solidity on Polygon Amoy or Polygon mainnet
- Storage: IPFS via Pinata
- IoT: ESP32 tracker and verifier firmware with local queueing

## Locked Pipeline

```text
IoT Tracker -> Backend Ingest -> Redis Streams -> PostgreSQL
                                          |
                                          v
                                    Batch Workers
                                          |
                                          v
                                      IPFS Pin
                                          |
                                          v
                                    Custody Gate
                                          |
                                          v
                                   Polygon Anchor
```

Core flow:

1. Trackers submit signed telemetry to `POST /api/v1/ingest/telemetry`.
2. Verifiers submit signed custody approval packets to `POST /api/v1/ingest/custody`.
3. Redis workers persist, batch, pin to IPFS, enforce custody gating, and anchor on-chain.
4. Dashboard APIs read canonical data from Postgres and proof linkage from IPFS and chain records.

## Repo Layout

```text
backend/   FastAPI API, DB models, migrations, workers, tests
contract/  Solidity contract, tests, deploy scripts, deployment snapshots
frontend/  React dashboard
iot/       tracker firmware, verifier firmware, harness scripts
md/        supplemental docs, including system architecture
```

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python run.py
```

Backend runs at `http://localhost:8000`.

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

## Contract Setup

```powershell
cd contract
npm install
npm test
npm run deploy:amoy
```

Deployment metadata is written to `contract/deployments/<network>.json` and a backend env snippet is emitted to `backend/.env.contract.<network>`.

## Firmware and Harness

- `iot/tracker/`: tracker firmware scaffold with local SPIFFS queue, signing, cellular transport
- `iot/verifier/`: verifier firmware scaffold with fingerprint flow, signing, custody queue
- `iot/harness/`: host-side telemetry and custody simulators plus serial NDJSON validation

PlatformIO CLI is required to build firmware locally.

## Important Environment Notes

Copy:

- `backend/.env.example` -> `backend/.env`
- `frontend/.env.example` -> `frontend/.env`

Important backend groups:

- Database and auth
- Redis stream settings
- Ingest signature and replay validation
- IPFS pinning
- Chain RPC, contract address, and ABI path
- Optional RAG and chat configuration

Important frontend group:

- `VITE_API_BASE_URL`

## ABI Source

The backend defaults `CHAIN_CONTRACT_ABI_PATH` to `contract/deployments/amoy.json`, not Hardhat build output. That keeps deployment metadata as the stable runtime source and avoids committing generated `artifacts/` or `cache/` directories.

## Main API Areas

- `POST /api/v1/ingest/telemetry`
- `POST /api/v1/ingest/custody`
- `GET /api/v1/shipments/*`
- `GET /api/v1/proofs/*`
- `GET/POST /api/v1/ops/*`
- `POST /api/v1/chat` and `POST /api/v1/ingest` for the RAG subsystem

## Delivery Model

- Frontend target: managed Vercel deployment
- Backend target: managed FastAPI app host
- Worker target: separate worker process or service using the same backend codebase
- Database target: managed PostgreSQL
- Queue target: managed Redis Streams
- IPFS target: Pinata
- Chain target for v1 sign-off: Polygon Amoy

Managed-cloud rollout details: [md/MANAGED_CLOUD_DEPLOYMENT.md](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/md/MANAGED_CLOUD_DEPLOYMENT.md)

## Current Notes

- Runtime APIs are now centered on canonical ingest, shipment, proof, and ops endpoints.
- Deployment snapshots under `contract/deployments/` are intended to stay in repo; Hardhat build outputs are not.
- Firmware directories still contain dev-only secret placeholders and must be provisioned with real per-device keys before staging or production.

## Security

- Do not commit real secrets.
- Replace dev firmware keys before real deployment.
- Use HTTPS or mTLS for production device channels.
- Restrict CORS and JWT secrets in production.
