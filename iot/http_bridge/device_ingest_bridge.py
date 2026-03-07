from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response


BACKEND_BASE_URL = os.getenv("BRIDGE_BACKEND_BASE_URL", "https://trustseal.onrender.com").rstrip("/")
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.getenv("PORT") or os.getenv("BRIDGE_PORT", "8081"))
FORWARD_TIMEOUT_SECONDS = float(os.getenv("BRIDGE_TIMEOUT_SECONDS", "20"))

app = FastAPI(title="TrustSeal Device HTTP Bridge")


def _forward_headers(
    *,
    authorization: str | None,
    content_type: str | None,
    device_id: str | None = None,
    device_token: str | None = None,
    verifier_device_id: str | None = None,
    verifier_token: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if authorization:
        headers["Authorization"] = authorization
    if content_type:
        headers["Content-Type"] = content_type
    if device_id:
        headers["X-Device-Id"] = device_id
    if device_token:
        headers["X-Device-Token"] = device_token
    if verifier_device_id:
        headers["X-Verifier-Device-Id"] = verifier_device_id
    if verifier_token:
        headers["X-Verifier-Token"] = verifier_token
    return headers


async def _forward_json(
    *,
    path: str,
    body: bytes,
    headers: dict[str, str],
) -> Response:
    url = f"{BACKEND_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=FORWARD_TIMEOUT_SECONDS, follow_redirects=True) as client:
        try:
            upstream = await client.post(url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Bridge upstream request failed: {exc}") from exc

    content_type = upstream.headers.get("content-type", "application/json")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=content_type.split(";")[0],
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "backend_base_url": BACKEND_BASE_URL,
    }


@app.post("/api/v1/ingest/telemetry")
async def bridge_telemetry(
    request: Request,
    authorization: str | None = Header(default=None),
    content_type: str | None = Header(default="application/json"),
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
) -> Response:
    body = await request.body()
    return await _forward_json(
        path="/api/v1/ingest/telemetry",
        body=body,
        headers=_forward_headers(
            authorization=authorization,
            content_type=content_type,
            device_id=x_device_id,
            device_token=x_device_token,
        ),
    )


@app.post("/api/v1/ingest/custody")
async def bridge_custody(
    request: Request,
    authorization: str | None = Header(default=None),
    content_type: str | None = Header(default="application/json"),
    x_verifier_device_id: str | None = Header(default=None),
    x_verifier_token: str | None = Header(default=None),
) -> Response:
    body = await request.body()
    return await _forward_json(
        path="/api/v1/ingest/custody",
        body=body,
        headers=_forward_headers(
            authorization=authorization,
            content_type=content_type,
            verifier_device_id=x_verifier_device_id,
            verifier_token=x_verifier_token,
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=BRIDGE_HOST, port=BRIDGE_PORT)
