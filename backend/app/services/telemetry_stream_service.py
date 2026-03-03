from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from redis import Redis
from redis.exceptions import RedisError, ResponseError

from ..core.config import settings
from ..database import SessionLocal
from ..models.telemetry_batch import TelemetryBatch
from .batch_finalization_service import BatchFinalizationError, batch_finalization_service

logger = logging.getLogger(__name__)


class TelemetryStreamService:
    """Redis Stream ingestion + worker-based custody batch finalization."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending_finalizations: set[str] = set()
        self._shipment_buffers: Dict[str, List[Tuple[str, dict]]] = {}

    @property
    def mode(self) -> str:
        return settings.TELEMETRY_PIPELINE_MODE

    @property
    def stream_enabled(self) -> bool:
        return self.mode in {"redis", "dual"}

    def startup(self) -> None:
        if not self.stream_enabled:
            return

        self._redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._redis.ping()
        self._ensure_consumer_group()

        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, name="telemetry-stream-worker", daemon=True)
        self._worker_thread.start()
        logger.info("Telemetry stream worker started")

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None

        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                logger.exception("Failed to close Redis connection")
        self._redis = None

    def publish_sensor_log(self, payload: dict) -> str | None:
        if not self.stream_enabled:
            return None
        if self._redis is None:
            logger.warning("Telemetry stream unavailable; Redis client not initialized")
            return None

        shipment_id = str(payload.get("shipment_id", "")).strip()
        if not shipment_id:
            logger.warning("Telemetry payload missing shipment_id")
            return None

        entry = {
            "shipment_id": shipment_id,
            "recorded_at": str(payload.get("recorded_at", "")),
            "payload": json.dumps(payload, separators=(",", ":"), sort_keys=True),
        }
        return self._redis.xadd(settings.REDIS_TELEMETRY_STREAM, entry)

    def request_custody_finalization(self, shipment_id: str) -> None:
        if not self.stream_enabled:
            return
        with self._lock:
            self._pending_finalizations.add(shipment_id)

    def _ensure_consumer_group(self) -> None:
        if self._redis is None:
            return
        try:
            self._redis.xgroup_create(
                name=settings.REDIS_TELEMETRY_STREAM,
                groupname=settings.REDIS_TELEMETRY_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def _worker_loop(self) -> None:
        assert self._redis is not None
        stream = settings.REDIS_TELEMETRY_STREAM
        group = settings.REDIS_TELEMETRY_CONSUMER_GROUP
        consumer = settings.REDIS_TELEMETRY_CONSUMER_NAME
        count = max(1, settings.REDIS_TELEMETRY_READ_COUNT)
        block_ms = max(1, settings.REDIS_TELEMETRY_BLOCK_MS)

        while not self._stop_event.is_set():
            try:
                response = self._redis.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: ">"},
                    count=count,
                    block=block_ms,
                )
            except RedisError:
                logger.exception("Redis stream read failed")
                time.sleep(1.0)
                continue

            if not response:
                self._finalize_pending()
                continue

            for _stream_name, entries in response:
                for message_id, fields in entries:
                    shipment_id = str(fields.get("shipment_id", "")).strip()
                    payload_raw = fields.get("payload")
                    if not shipment_id or not payload_raw:
                        self._redis.xack(stream, group, message_id)
                        continue

                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        logger.warning("Invalid telemetry payload JSON; acking message_id=%s", message_id)
                        self._redis.xack(stream, group, message_id)
                        continue

                    with self._lock:
                        self._shipment_buffers.setdefault(shipment_id, []).append((message_id, payload))

            self._finalize_pending()

    def _finalize_pending(self) -> None:
        with self._lock:
            shipment_ids = list(self._pending_finalizations)

        for shipment_id in shipment_ids:
            try:
                self._finalize_shipment(shipment_id)
            except Exception:
                logger.exception("Telemetry shipment finalization failed for shipment_id=%s", shipment_id)

    def _finalize_shipment(self, shipment_id: str) -> None:
        if self._redis is None:
            return
        stream = settings.REDIS_TELEMETRY_STREAM
        group = settings.REDIS_TELEMETRY_CONSUMER_GROUP

        with self._lock:
            buffered = self._shipment_buffers.get(shipment_id, [])
            if not buffered:
                self._pending_finalizations.discard(shipment_id)
                return
            self._shipment_buffers[shipment_id] = []
            self._pending_finalizations.discard(shipment_id)

        payloads = [item[1] for item in buffered]
        message_ids = [message_id for message_id, _payload in buffered]
        canonical = json.dumps(payloads, separators=(",", ":"), sort_keys=True)
        batch_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        epoch_key = f"trustseal:shipment:{shipment_id}:epoch"
        epoch = self._redis.incr(epoch_key)
        batch_key = f"trustseal:batch:{shipment_id}:{epoch}"
        idempotency_key = f"trustseal:anchor:{shipment_id}:{epoch}:{batch_hash}"
        if self._redis.setnx(idempotency_key, "processing") == 0:
            logger.info(
                "Skipping duplicate finalization shipment_id=%s epoch=%s",
                shipment_id,
                epoch,
            )
            if message_ids:
                self._redis.xack(stream, group, *message_ids)
            return
        self._redis.expire(idempotency_key, 60 * 60 * 24 * 7)

        self._redis.hset(
            batch_key,
            mapping={
                "shipment_id": shipment_id,
                "epoch": str(epoch),
                "record_count": str(len(payloads)),
                "batch_hash": batch_hash,
                "status": "pending_ipfs_anchor",
                "payload_json": canonical,
                "finalized_at": str(time.time()),
            },
        )
        self._upsert_batch_metadata(
            shipment_id=shipment_id,
            epoch=epoch,
            record_count=len(payloads),
            batch_hash=batch_hash,
            status="pending_ipfs_anchor",
            ipfs_cid=None,
            tx_hash=None,
            error_message=None,
            anchored_at=None,
        )

        try:
            if settings.TELEMETRY_FINALIZATION_ENABLED:
                finalization = batch_finalization_service.finalize(
                    shipment_id=shipment_id,
                    epoch=epoch,
                    batch_hash=batch_hash,
                    payload_json=canonical,
                )
                self._redis.hset(
                    batch_key,
                    mapping={
                        "status": "anchored",
                        "ipfs_cid": finalization.get("ipfs_cid") or "",
                        "tx_hash": finalization.get("tx_hash") or "",
                        "anchored_at": str(time.time()),
                    },
                )
                self._upsert_batch_metadata(
                    shipment_id=shipment_id,
                    epoch=epoch,
                    record_count=len(payloads),
                    batch_hash=batch_hash,
                    status="anchored",
                    ipfs_cid=finalization.get("ipfs_cid"),
                    tx_hash=finalization.get("tx_hash"),
                    error_message=None,
                    anchored_at=datetime.now(timezone.utc),
                )
            else:
                self._redis.hset(batch_key, mapping={"status": "pending_ipfs_anchor"})
        except BatchFinalizationError as exc:
            self._redis.hset(
                batch_key,
                mapping={
                    "status": "finalization_failed",
                    "finalization_error": str(exc),
                    "failed_at": str(time.time()),
                },
            )
            self._upsert_batch_metadata(
                shipment_id=shipment_id,
                epoch=epoch,
                record_count=len(payloads),
                batch_hash=batch_hash,
                status="finalization_failed",
                ipfs_cid=None,
                tx_hash=None,
                error_message=str(exc),
                anchored_at=None,
            )
            logger.exception(
                "Batch finalization failed shipment_id=%s epoch=%s",
                shipment_id,
                epoch,
            )
        finally:
            if message_ids:
                self._redis.xack(stream, group, *message_ids)

        logger.info(
            "Telemetry batch finalized shipment_id=%s epoch=%s records=%s",
            shipment_id,
            epoch,
            len(payloads),
        )

    def _upsert_batch_metadata(
        self,
        *,
        shipment_id: str,
        epoch: int,
        record_count: int,
        batch_hash: str,
        status: str,
        ipfs_cid: str | None,
        tx_hash: str | None,
        error_message: str | None,
        anchored_at: datetime | None,
    ) -> None:
        try:
            shipment_uuid = uuid.UUID(str(shipment_id))
        except (TypeError, ValueError):
            logger.warning("Skipping metadata persistence due to invalid shipment_id=%s", shipment_id)
            return

        db = SessionLocal()
        try:
            existing = (
                db.query(TelemetryBatch)
                .filter(TelemetryBatch.shipment_id == shipment_uuid, TelemetryBatch.epoch == epoch)
                .first()
            )
            if existing is None:
                existing = TelemetryBatch(
                    shipment_id=shipment_uuid,
                    epoch=epoch,
                    record_count=record_count,
                    batch_hash=batch_hash,
                    status=status,
                    ipfs_cid=ipfs_cid,
                    tx_hash=tx_hash,
                    error_message=error_message,
                    anchored_at=anchored_at,
                )
                db.add(existing)
            else:
                existing.record_count = record_count
                existing.batch_hash = batch_hash
                existing.status = status
                existing.ipfs_cid = ipfs_cid
                existing.tx_hash = tx_hash
                existing.error_message = error_message
                existing.anchored_at = anchored_at

            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to persist telemetry batch metadata shipment_id=%s epoch=%s",
                shipment_id,
                epoch,
            )
        finally:
            db.close()


telemetry_stream_service = TelemetryStreamService()
