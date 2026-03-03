import asyncio
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError, TimeoutError as SATimeoutError
from .core.config import settings
from .services.realtime import shipment_event_dispatcher
from .services.telemetry_stream_service import telemetry_stream_service

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
def start_telemetry_stream_worker() -> None:
    try:
        telemetry_stream_service.startup()
    except Exception:
        logger.exception("Telemetry stream startup failed. API will continue without Redis stream worker.")


@app.on_event("shutdown")
def stop_telemetry_stream_worker() -> None:
    try:
        telemetry_stream_service.shutdown()
    except Exception:
        logger.exception("Telemetry stream shutdown failed.")


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
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to TrustSeal IoT API"}

# Health check endpoint
@app.get("/health")
async def health_check():
    rag = await chat_service.health_status()
    if rag.get("status") == "ok":
        return {"status": "ok", "rag": "ready"}
    return {"status": rag.get("status", "degraded"), "rag": rag.get("rag", "unknown")}


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
from .routers import auth, devices, shipments, sensor_logs, custody, legs, ws, chat

app.include_router(auth.router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(devices.router, prefix=settings.API_V1_STR + "/devices", tags=["devices"])
app.include_router(shipments.router, prefix=settings.API_V1_STR + "/shipments", tags=["shipments"])
app.include_router(sensor_logs.router, prefix=settings.API_V1_STR + "/sensor-logs", tags=["sensor-logs"])
app.include_router(custody.router, prefix=settings.API_V1_STR + "/custody", tags=["custody"])
app.include_router(legs.router, prefix=settings.API_V1_STR + "/legs", tags=["legs"])
app.include_router(ws.router, prefix=settings.API_V1_STR + "/ws", tags=["ws"])
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["chat"])
from .routers import debug
app.include_router(debug.router, prefix=settings.API_V1_STR + "/debug", tags=["debug"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
