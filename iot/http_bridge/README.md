# Device HTTP Bridge

Use this when Arduino devices can only send plain HTTP but your real backend is HTTPS-only.

What it does:
- accepts device HTTP requests on your local machine or edge host
- forwards them to the real backend over HTTPS
- preserves TrustSeal ingest headers:
  - `X-Device-Id`
  - `X-Device-Token`
  - `X-Verifier-Device-Id`
  - `X-Verifier-Token`

Primary file:
- [device_ingest_bridge.py](/c:/Users/likug/Downloads/TrustSeal/TrustSeal/iot/http_bridge/device_ingest_bridge.py)

Run it:

```powershell
$env:BRIDGE_BACKEND_BASE_URL = "https://trustseal.onrender.com"
$env:BRIDGE_HOST = "0.0.0.0"
$env:BRIDGE_PORT = "8081"
python iot/http_bridge/device_ingest_bridge.py
```

Health check:

```powershell
curl http://127.0.0.1:8081/health
```

Arduino target pattern:
- set tracker and verifier `*_API_HOST` to your laptop or bridge host LAN IP
- set `*_API_PORT` to `8081`
- keep `*_API_PATH` unchanged

Important:
- the bridge only forwards ingest endpoints
- dashboard, proof, and ops reads still go directly to the backend/frontend
- if your devices and laptop are on different networks, this will not work without routing or port exposure
