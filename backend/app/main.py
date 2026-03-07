import asyncio
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
import httpx
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, TimeoutError as SATimeoutError
from .core.config import settings
from .database import engine
from .services.realtime import shipment_event_dispatcher
from .services.worker_orchestrator import worker_orchestrator
from .middleware.correlation import CorrelationMiddleware
try:
    from web3 import Web3
except Exception:  # pragma: no cover
    Web3 = None  # type: ignore

if sys.platform.startswith("win"):
    # psycopg async pool requires selector loop on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from .services.chat_service import chat_service

logger = logging.getLogger(__name__)
LOCAL_DEV_CORS_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

# Create FastAPI app
app = FastAPI(title=settings.PROJECT_NAME)


@app.on_event("startup")
def ensure_local_sqlite_schema() -> None:
    # For local dev fallback, create schema automatically when using SQLite.
    if settings.DATABASE_URL.startswith("sqlite"):
        from . import models  # noqa: F401
        from .database import Base, engine

        Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def start_worker_orchestrator() -> None:
    """Start all Redis stream workers via orchestrator."""
    if not settings.RUN_WORKERS:
        logger.info("Worker orchestrator startup skipped for process role=%s", settings.APP_PROCESS_ROLE)
        return
    try:
        worker_orchestrator.startup()
    except Exception:
        logger.exception("Worker orchestrator startup failed. API will continue without Redis stream workers.")


@app.on_event("shutdown")
def stop_worker_orchestrator() -> None:
    """Gracefully shutdown all workers."""
    if not settings.RUN_WORKERS:
        return
    try:
        worker_orchestrator.shutdown(timeout=30.0)
    except Exception:
        logger.exception("Worker orchestrator shutdown failed.")


@app.on_event("startup")
async def start_realtime_dispatcher() -> None:
    shipment_event_dispatcher.start()


@app.on_event("shutdown")
async def stop_realtime_dispatcher() -> None:
    await shipment_event_dispatcher.stop()


@app.on_event("startup")
async def start_agentic_rag() -> None:
    if not settings.AGENTIC_EAGER_STARTUP:
        logger.info("Agentic RAG eager startup disabled; service will initialize on first chat request.")
        return

    try:
        await chat_service.startup()
    except Exception:
        logger.exception("Agentic RAG startup failed. API will run in degraded mode.")


@app.on_event("shutdown")
async def stop_agentic_rag() -> None:
    try:
        await chat_service.shutdown()
    except Exception:
        logger.exception("Agentic RAG shutdown failed.")

# CORS middleware
combined_cors_regex = (
    f"(?:{LOCAL_DEV_CORS_REGEX})|(?:{settings.BACKEND_CORS_ORIGIN_REGEX})"
    if settings.BACKEND_CORS_ORIGIN_REGEX
    else LOCAL_DEV_CORS_REGEX
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=combined_cors_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Correlation-ID"],
    expose_headers=["X-Correlation-ID"],
)

# Correlation ID middleware (for distributed tracing)
app.add_middleware(CorrelationMiddleware)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to TrustSeal IoT API"}

# Health check endpoint
@app.get("/health")
@app.get(settings.API_V1_STR + "/health")
async def health_check():
    rag = await chat_service.health_status()

    postgres = {"enabled": True, "status": "down"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres["status"] = "ok"
    except Exception as exc:
        postgres["error"] = str(exc)

    redis_health = {"enabled": settings.TELEMETRY_PIPELINE_MODE in {"redis", "dual"}}
    if redis_health["enabled"]:
        try:
            r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            r.ping()
            r.close()
            redis_health["status"] = "ok"
        except Exception as exc:
            redis_health["status"] = "down"
            redis_health["error"] = str(exc)
    else:
        redis_health["status"] = "disabled"

    # Worker orchestrator status
    worker_status = worker_orchestrator.get_status()
    workers_health = {
        "enabled": settings.RUN_WORKERS,
        "status": (
            "disabled"
            if not settings.RUN_WORKERS
            else ("ok" if worker_orchestrator.is_healthy() else "degraded")
        ),
        "workers": worker_status.get("workers", {}),
    }

    ipfs_health = {"enabled": settings.IPFS_PIN_ENABLED}
    if ipfs_health["enabled"]:
        if not settings.IPFS_PIN_JWT:
            ipfs_health["status"] = "down"
            ipfs_health["error"] = "IPFS_PIN_JWT missing"
        else:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(settings.IPFS_PIN_ENDPOINT)
                ipfs_health["status"] = "ok" if response.status_code < 500 else "down"
                ipfs_health["http_status"] = response.status_code
            except Exception as exc:
                ipfs_health["status"] = "down"
                ipfs_health["error"] = str(exc)
    else:
        ipfs_health["status"] = "disabled"

    chain_health = {"enabled": settings.CHAIN_ANCHOR_ENABLED}
    if chain_health["enabled"]:
        if Web3 is None:
            chain_health["status"] = "down"
            chain_health["error"] = "web3 unavailable"
        elif not settings.CHAIN_RPC_URL:
            chain_health["status"] = "down"
            chain_health["error"] = "CHAIN_RPC_URL missing"
        else:
            try:
                w3 = Web3(Web3.HTTPProvider(settings.CHAIN_RPC_URL))
                connected = bool(w3.is_connected())
                chain_health["status"] = "ok" if connected else "down"
                if connected:
                    chain_health["latest_block"] = int(w3.eth.block_number)
                else:
                    chain_health["error"] = "RPC not reachable"
            except Exception as exc:
                chain_health["status"] = "down"
                chain_health["error"] = str(exc)
    else:
        chain_health["status"] = "disabled"

    checks = [
        postgres["status"],
        redis_health["status"],
        workers_health["status"],
        ipfs_health["status"],
        chain_health["status"],
    ]
    if rag.get("status") != "ok":
        checks.append("down")
    overall = "ok" if all(s in {"ok", "disabled"} for s in checks) else "degraded"
    return {
        "status": overall,
        "rag": rag.get("status", "degraded"),
        "services": {
            "postgres": postgres,
            "redis": redis_health,
            "workers": workers_health,
            "ipfs": ipfs_health,
            "polygon": chain_health,
        },
    }


@app.exception_handler(OperationalError)
async def handle_database_operational_error(_request: Request, exc: OperationalError) -> JSONResponse:
    logger.exception("Database operational error", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is temporarily unavailable due to connection saturation. Please retry."},
    )


@app.exception_handler(SATimeoutError)
async def handle_database_pool_timeout(_request: Request, exc: SATimeoutError) -> JSONResponse:
    logger.exception("Database connection pool timeout", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database connection pool is busy. Please retry shortly."},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Import and include routers
from .routers import auth, devices, shipments, legs, ws, chat, ingest, proofs, ops

app.include_router(auth.router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(devices.router, prefix=settings.API_V1_STR + "/devices", tags=["devices"])
app.include_router(shipments.router, prefix=settings.API_V1_STR + "/shipments", tags=["shipments"])
app.include_router(legs.router, prefix=settings.API_V1_STR + "/legs", tags=["legs"])
app.include_router(ws.router, prefix=settings.API_V1_STR + "/ws", tags=["ws"])
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["chat"])
app.include_router(ingest.router, prefix=settings.API_V1_STR, tags=["ingest"])
app.include_router(proofs.router, prefix=settings.API_V1_STR + "/proofs", tags=["proofs"])
app.include_router(ops.router, prefix=settings.API_V1_STR + "/ops", tags=["ops"])
from .routers import debug
app.include_router(debug.router, prefix=settings.API_V1_STR + "/debug", tags=["debug"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
