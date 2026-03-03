# TrustSeal IoT

Full-stack supply chain IoT monitoring system.

- Backend: FastAPI + PostgreSQL + SQLAlchemy + JWT + LangChain + pgvector + OpenRouter
- Frontend: React (Vite) + TypeScript + Tailwind + React Query + Axios + Recharts

## Architecture

- API base path: `/api/v1`
- Auth: JWT Bearer token in `Authorization` header
- Frontend API base URL comes from `VITE_API_BASE_URL`
- CORS origins come from `BACKEND_CORS_ORIGINS`
- Chat/RAG endpoint: `POST /api/v1/chat` (admin only)

## Agentic RAG Architecture (Current)

The chatbot now runs an agentic RAG pipeline using LangChain + pgvector with strict grounding.

Flow:

1. Ingest text through `POST /api/v1/ingest` with `tenant_id` and `device_id` isolation.
2. Chunk text and generate embeddings asynchronously in batches.
3. Store vectors in PostgreSQL (`documents` table) and LangChain PGVector collection.
4. Rewrite follow-up questions using short-term conversation window memory.
5. Retrieve by metadata filter (`tenant_id`, `device_id`) with cosine similarity + MMR.
6. Apply contextual compression to keep only relevant evidence.
7. Use ReAct-style agent tools (`VectorSearchTool`, `ConversationMemoryTool`, `MetadataFilterTool`).
8. Return only grounded answers, else return: `I don’t have enough information to answer that.`

## Project Structure

```text
TrustSeal/
|- frontend/                # React frontend
|  |- src/
|  |- package.json
|  |- .env.example
|- backend/                 # FastAPI backend
|  |- app/
|  |- alembic/
|  |- requirements.txt
|  |- run.py
|  |- .env.example
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env`, and copy `frontend/.env.example` to `frontend/.env`.

Required backend values:

```env
# DB (RAG requires PostgreSQL; SQLite works for non-RAG local paths)
DATABASE_URL=postgresql://user:pass@host:5432/dbname
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
SECRET_KEY=replace-with-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# OpenRouter
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3.5-haiku
OPENROUTER_TIMEOUT_SECONDS=30
OPENROUTER_MAX_TOKENS=512
OPENROUTER_SITE_URL=http://localhost:5173
OPENROUTER_APP_NAME=TrustSeal IoT

# RAG / Vector Search
RAG_COLLECTION_NAME=trustseal_ops
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
RAG_EMBEDDING_DIMENSION=1536
RAG_TOP_K=6
RAG_MIN_RELEVANCE=0.25
RAG_TEMPERATURE=0.2
RAG_MAX_SHIPMENTS=300
RAG_MAX_DEVICES=300
RAG_MAX_SENSOR_LOGS=500
RAG_MAX_CUSTODY_CHECKPOINTS=500
```

Required frontend values:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If you use Supabase, prefer the Supabase pooler `DATABASE_URL` for better IPv4 compatibility.

## Backend Setup

1. Create virtual environment and install dependencies.
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```
2. Run migrations.
```powershell
alembic upgrade head
```
3. Optional: seed data.
```powershell
python -m app.seed_data
```
4. Start backend.
```powershell
python run.py
```

Backend runs at `http://localhost:8000`.

## Frontend Setup

1. Install dependencies.
```powershell
cd frontend
npm install
```
2. Start dev server.
```powershell
npm run dev
```
3. Build for production.
```powershell
npm run build
```

Frontend default dev URL is `http://localhost:5173`.

## Push Vectors to Supabase (pgvector)

Run these from PowerShell:

```powershell
cd d:\TrustSeal\backend

# 1) install deps
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2) apply DB migrations (includes pgvector extension migration)
.\.venv\Scripts\python.exe -m alembic upgrade head

# 3) login and capture admin token
$token = (curl.exe -s -X POST -d "username=admin@trustseal.io" -d "password=pass123" "http://localhost:8000/api/v1/auth/login" | ConvertFrom-Json).access_token

# 4) ingest a document into tenant/device-scoped vector memory
curl.exe -X POST `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{\"tenant_id\":\"tenant-alpha\",\"device_id\":\"DEV-LIVE-001\",\"raw_document\":\"Shipment SHP-2024-002 had moderate temperature variation across the route.\",\"metadata\":{\"source\":\"manual_import\",\"doc_type\":\"knowledge\"}}" `
  http://localhost:8000/api/v1/ingest
```

What this does:

- Enables `vector` extension in Postgres.
- Creates `documents` storage and vector index via Alembic migrations.
- Pushes your provided document into pgvector with tenant/device metadata filters.

## Chat + Agentic RAG Behavior

- `POST /api/v1/chat` runs agentic retrieval with strict tenant/device filter support.
- Chat uses LangChain agent tool-calling with short-term and long-term memory.
- Response format remains:
  - `answer`
  - `sources`
  - `confidence`
  - `session_id`
- If context is not relevant enough, response is `I don’t have enough information to answer that.`

## Sensor Stats Consistency

- New endpoint: `GET /api/v1/shipments/{shipment_id}/sensor-stats`
- Shipment details UI now uses this backend aggregate endpoint, and chat tools use the same SQL stats service.
- This removes UI-vs-chat conflicts for average/min/max temperature and max shock values.

## Access Control and ID Safety

If someone knows a `device_id` or `shipment_id`, they still cannot query data without a valid JWT.

Current route protections:

- `POST /api/v1/chat`: admin only.
- `GET /api/v1/devices/*` and `GET /api/v1/shipments/*`: any authenticated active user.

So:

- Knowing IDs alone is not enough.
- Any logged-in user can still read those resources in current implementation.

If you need stricter privacy, restrict read routes by role and/or ownership (tenant/customer scope).

## Admin Login Example

The development seed creates an administrator account:

- Email: `admin@trustseal.io`
- Password: `pass123`

PowerShell token example:

```powershell
# login and capture token
$token = (curl.exe -s -X POST -d "username=admin@trustseal.io" -d "password=pass123" "http://localhost:8000/api/v1/auth/login" | ConvertFrom-Json).access_token

# list devices
curl.exe -H "Authorization: Bearer $token" http://localhost:8000/api/v1/devices/

# list shipments for a device (replace DEVICE_UUID)
curl.exe -H "Authorization: Bearer $token" "http://localhost:8000/api/v1/shipments/?device_id=DEVICE_UUID"

# ask chat (admin only)
curl.exe -X POST -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d '{"message":"Any risky shipment trends in last logs?"}' http://localhost:8000/api/v1/chat
```

## API Docs

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Postman guide: `postmanGuide.md`

## Common Troubleshooting

`503 RAG vector retrieval requires PostgreSQL`:

- `DATABASE_URL` is not pointing to PostgreSQL.
- Set Postgres/Supabase connection string and restart backend.

`502` from chat endpoint:

- OpenRouter credentials/model/config invalid.
- Verify `OPENROUTER_API_KEY`, base URL, and model name.

`CORS error` in browser:

- Current frontend origin is missing in `BACKEND_CORS_ORIGINS`.
- Restart backend after changing `.env`.

`AttributeError: module 'bcrypt' has no attribute '__about__'`:

- Use pinned dependency from `backend/requirements.txt` (`bcrypt>=4.0.1,<4.1`).
- Reinstall backend dependencies.

## Security Notes

- Do not commit real secrets in `.env`.
- Rotate any leaked API keys immediately.
- Use strong `SECRET_KEY` in production.
- Restrict `BACKEND_CORS_ORIGINS` to trusted domains in production.
