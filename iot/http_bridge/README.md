# Device HTTP Bridge

This bridge exists for modem paths that can send plain HTTP but cannot complete HTTPS/TLS reliably.

Flow:

- Tracker/Verifier -> `http://<your-laptop-ip>:8081/api/v1/ingest/...`
- Bridge -> `https://trustseal.onrender.com/api/v1/ingest/...`

## Run

From the repo root:

```powershell
cd backend
.\.venv\Scripts\python ..\iot\http_bridge\device_ingest_bridge.py
```

Optional environment variables:

```powershell
$env:BRIDGE_BACKEND_BASE_URL = "https://trustseal.onrender.com"
$env:BRIDGE_PORT = "8081"
```

Health check:

```text
http://127.0.0.1:8081/health
```

## Tracker settings

Point the tracker Arduino sketch to your laptop's LAN IP:

- `TRACKER_API_HOST "<your-laptop-ip>"`
- `TRACKER_API_PORT 8081`
- `TRACKER_API_PATH "/api/v1/ingest/telemetry"`

Use the same device auth token and headers as before.

## Verifier settings

Point the verifier Arduino sketch to your laptop's LAN IP:

- `VERIFIER_API_HOST "<your-laptop-ip>"`
- `VERIFIER_API_PORT 8081`
- `VERIFIER_API_PATH "/api/v1/ingest/custody"`

## Notes

- The bridge forwards `Authorization`, `Content-Type`, `X-Device-Id`, and `X-Verifier-Device-Id`.
- The real backend remains unchanged.
- The bridge follows HTTPS redirects upstream.
