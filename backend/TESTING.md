# Backend Testing

## Setup

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

## Run

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

## Scope

- ingest verification validation
- idempotency checks
- custody-gate state transition enforcement
- anchor worker retry/idempotency guards
- stream orchestration smoke flow (`custody -> batch -> ipfs -> custody gate -> anchor`)
