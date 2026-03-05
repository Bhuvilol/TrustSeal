from __future__ import annotations

import json
import logging
import time
import threading
import uuid
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import RedisError, ResponseError

from ..core.config import settings
from ..database import SessionLocal
from .anchor_worker import anchor_worker
from .batch_worker import batch_worker
from .custody_gate_worker import custody_gate_worker
from .ipfs_worker import ipfs_worker
from .persistence_worker import persistence_worker

logger = logging.getLogger(__name__)


class TelemetryStreamService:
    """Redis stream orchestrator for telemetry -> bundle -> ipfs -> custody -> anchor."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._stop_event = threading.Event()
        self._worker_threads: dict[str, threading.Thread] = {}

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
        self._worker_threads = {}
        for stream_name in self._stream_names():
            worker = threading.Thread(
                target=self._worker_loop,
                kwargs={"stream_name": stream_name},
                name=f"trustseal-stream-worker-{stream_name}",
                daemon=True,
            )
            worker.start()
            self._worker_threads[stream_name] = worker
        logger.info("TrustSeal stream workers started count=%d", len(self._worker_threads))

    def shutdown(self) -> None:
        self._stop_event.set()
        for worker in self._worker_threads.values():
            if worker.is_alive():
                worker.join(timeout=2.0)
        self._worker_threads = {}

        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                logger.exception("Failed to close Redis connection")
        self._redis = None

    def publish_sensor_log(self, payload: dict) -> str | None:
        return self._publish_stream_event(
            stream_name=settings.REDIS_TELEMETRY_STREAM,
            event_type="telemetry",
            payload=payload,
        )

    def publish_custody_event(self, payload: dict) -> str | None:
        return self._publish_stream_event(
            stream_name=settings.REDIS_CUSTODY_STREAM,
            event_type="custody",
            payload=payload,
        )

    def publish_bundle_ready(self, payload: dict) -> str | None:
        return self._publish_stream_event(
            stream_name=settings.REDIS_BUNDLE_READY_STREAM,
            event_type="bundle_ready",
            payload=payload,
        )

    def publish_anchor_request(self, payload: dict) -> str | None:
        return self._publish_stream_event(
            stream_name=settings.REDIS_ANCHOR_REQUEST_STREAM,
            event_type="anchor_request",
            payload=payload,
        )

    def request_custody_finalization(self, shipment_id: str) -> None:
        """Compatibility trigger for manual/legacy custody checkpoints."""
        if not self.stream_enabled:
            return
        db = SessionLocal()
        try:
            batch_worker.finalize_shipment_batch(db, shipment_id=str(shipment_id))
        except Exception:
            logger.exception("Manual custody finalization trigger failed shipment_id=%s", shipment_id)
        finally:
            db.close()

    def _publish_stream_event(self, *, stream_name: str, event_type: str, payload: dict) -> str | None:
        if not self.stream_enabled:
            return None
        if self._redis is None:
            logger.warning("Stream unavailable; Redis client not initialized for event_type=%s", event_type)
            return None

        normalized = self._normalize_event_payload(event_type=event_type, payload=payload)
        if normalized is None:
            logger.warning("Stream payload rejected for event_type=%s", event_type)
            return None

        stream_event_id = str(payload.get("stream_event_id") or uuid.uuid4())
        entry = {
            "stream_event_id": stream_event_id,
            "event_type": event_type,
            "shipment_id": str(normalized.get("shipment_id") or ""),
            "bundle_id": str(normalized.get("bundle_id") or ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": json.dumps(normalized, separators=(",", ":"), sort_keys=True),
        }
        return self._redis.xadd(stream_name, entry)

    def _normalize_event_payload(self, *, event_type: str, payload: dict) -> dict | None:
        shipment_id = str(payload.get("shipment_id") or "").strip()
        if not shipment_id:
            return None

        if event_type == "telemetry":
            event_id = str(payload.get("event_id") or payload.get("id") or uuid.uuid4())
            ts = str(payload.get("ts") or payload.get("recorded_at") or datetime.now(timezone.utc).isoformat())
            seq_no_raw = payload.get("seq_no", 0)
            try:
                seq_no = int(seq_no_raw)
            except (TypeError, ValueError):
                seq_no = 0

            normalized = {
                "event_type": "telemetry",
                "event_id": event_id,
                "shipment_id": shipment_id,
                "device_id": str(payload.get("device_id") or ""),
                "ts": ts,
                "seq_no": max(seq_no, 0),
                "metrics": payload.get("metrics"),
                "gps": payload.get("gps"),
                "payload_hash": str(payload.get("payload_hash") or ""),
                "signature": str(payload.get("signature") or ""),
                "idempotency_key": str(payload.get("idempotency_key") or event_id),
            }
            if normalized["metrics"] is None:
                normalized["metrics"] = {
                    "temperature_c": payload.get("temperature"),
                    "humidity_pct": payload.get("humidity"),
                    "shock_g": payload.get("shock"),
                    "light_lux": payload.get("light_exposure"),
                    "tilt_deg": payload.get("tilt_angle"),
                    "battery_pct": payload.get("battery_pct"),
                }
            return normalized

        if event_type == "custody":
            custody_event_id = str(payload.get("custody_event_id") or payload.get("id") or uuid.uuid4())
            ts = str(payload.get("ts") or payload.get("timestamp") or datetime.now(timezone.utc).isoformat())
            return {
                "event_type": "custody",
                "custody_event_id": custody_event_id,
                "shipment_id": shipment_id,
                "leg_id": str(payload.get("leg_id") or ""),
                "verifier_user_id": str(payload.get("verifier_user_id") or ""),
                "verifier_device_id": str(payload.get("verifier_device_id") or ""),
                "ts": ts,
                "fingerprint_result": payload.get("fingerprint_result"),
                "fingerprint_score": payload.get("fingerprint_score"),
                "fingerprint_template_id": payload.get("fingerprint_template_id"),
                "digital_signer_address": str(payload.get("digital_signer_address") or ""),
                "approval_message_hash": str(payload.get("approval_message_hash") or ""),
                "signature": str(payload.get("signature") or ""),
                "idempotency_key": str(payload.get("idempotency_key") or custody_event_id),
            }

        if event_type == "bundle_ready":
            bundle_id = str(payload.get("bundle_id") or "").strip()
            if not bundle_id:
                return None
            return {
                "event_type": "bundle_ready",
                "shipment_id": shipment_id,
                "bundle_id": bundle_id,
                "epoch": payload.get("epoch"),
                "record_count": payload.get("record_count"),
                "batch_hash": payload.get("batch_hash"),
                "created_at": str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
            }

        if event_type == "anchor_request":
            bundle_id = str(payload.get("bundle_id") or "").strip()
            if not bundle_id:
                return None
            return {
                "event_type": "anchor_request",
                "shipment_id": shipment_id,
                "bundle_id": bundle_id,
                "batch_hash": payload.get("batch_hash"),
                "ipfs_cid": payload.get("ipfs_cid"),
                "created_at": str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
            }

        return None

    def _ensure_consumer_group(self) -> None:
        if self._redis is None:
            return
        for stream_name in self._stream_names():
            try:
                self._redis.xgroup_create(
                    name=stream_name,
                    groupname=settings.REDIS_TELEMETRY_CONSUMER_GROUP,
                    id="0",
                    mkstream=True,
                )
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    def _stream_names(self) -> list[str]:
        return [
            settings.REDIS_TELEMETRY_STREAM,
            settings.REDIS_CUSTODY_STREAM,
            settings.REDIS_BUNDLE_READY_STREAM,
            settings.REDIS_ANCHOR_REQUEST_STREAM,
        ]

    def _worker_loop(self, *, stream_name: str) -> None:
        assert self._redis is not None
        streams = {stream_name: ">"}
        group = settings.REDIS_TELEMETRY_CONSUMER_GROUP
        consumer = f"{settings.REDIS_TELEMETRY_CONSUMER_NAME}-{stream_name}"
        count = max(1, settings.REDIS_TELEMETRY_READ_COUNT)
        block_ms = max(1, settings.REDIS_TELEMETRY_BLOCK_MS)

        while not self._stop_event.is_set():
            try:
                response = self._redis.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams=streams,
                    count=count,
                    block=block_ms,
                )
            except RedisError:
                logger.exception("Redis stream read failed stream=%s", stream_name)
                continue

            if not response:
                continue

            for _, entries in response:
                for message_id, fields in entries:
                    success = False
                    should_ack = False
                    try:
                        self._process_stream_entry(stream_name=stream_name, fields=fields)
                        success = True
                        should_ack = True
                    except Exception:
                        logger.exception(
                            "Stream message processing failed stream=%s message_id=%s",
                            stream_name,
                            message_id,
                        )
                        retrying = self._handle_processing_failure(
                            stream_name=stream_name,
                            message_id=message_id,
                            fields=fields,
                        )
                        if retrying:
                            continue
                        should_ack = True
                    if success:
                        self._clear_retry_attempt(stream_name=stream_name, message_id=message_id)
                    if should_ack:
                        try:
                            self._redis.xack(stream_name, group, message_id)
                        except Exception:
                            logger.exception("Stream ack failed stream=%s message_id=%s", stream_name, message_id)

    def _process_stream_entry(self, *, stream_name: str, fields: dict) -> None:
        raw_payload = fields.get("payload")
        payload = self._decode_payload(raw_payload)
        event_type = str(fields.get("event_type") or payload.get("event_type") or "").strip()

        if stream_name == settings.REDIS_TELEMETRY_STREAM or event_type == "telemetry":
            self._process_telemetry(payload)
            return
        if stream_name == settings.REDIS_CUSTODY_STREAM or event_type == "custody":
            self._process_custody(payload)
            return
        if stream_name == settings.REDIS_BUNDLE_READY_STREAM or event_type == "bundle_ready":
            self._process_bundle_ready(payload)
            return
        if stream_name == settings.REDIS_ANCHOR_REQUEST_STREAM or event_type == "anchor_request":
            self._process_anchor_request(payload)
            return

        logger.warning("Unknown stream event ignored stream=%s event_type=%s", stream_name, event_type)

    def _decode_payload(self, raw_payload: str | None) -> dict:
        if not raw_payload:
            return {}
        try:
            obj = json.loads(raw_payload)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            logger.warning("Invalid stream payload JSON")
            return {}

    def _process_telemetry(self, payload: dict) -> None:
        db = SessionLocal()
        try:
            ok = persistence_worker.process_stream_payload(db, event_type="telemetry", payload=payload)
            if not ok:
                return
            shipment_id = str(payload.get("shipment_id") or "").strip()
            if not shipment_id:
                return
            batch_worker.maybe_finalize_shipment_batch(
                db,
                shipment_id=shipment_id,
                trigger="telemetry",
                force=False,
            )
        finally:
            db.close()

    def _process_custody(self, payload: dict) -> None:
        db = SessionLocal()
        try:
            ok = persistence_worker.process_stream_payload(db, event_type="custody", payload=payload)
            if not ok:
                return
            shipment_id = str(payload.get("shipment_id") or "").strip()
            if not shipment_id:
                return
            batch_worker.maybe_finalize_shipment_batch(
                db,
                shipment_id=shipment_id,
                trigger="custody",
                force=settings.BATCH_FORCE_ON_CUSTODY,
            )
        finally:
            db.close()

    def _process_bundle_ready(self, payload: dict) -> None:
        db = SessionLocal()
        try:
            bundle_id = str(payload.get("bundle_id") or "").strip()
            if not bundle_id:
                raise RuntimeError("bundle_ready payload missing bundle_id")
            payload_json = batch_worker.build_bundle_payload_json(db, bundle_id=bundle_id)
            if not payload_json:
                raise RuntimeError(f"Bundle payload missing for bundle_id={bundle_id}")
            pinned = ipfs_worker.pin_bundle(db, bundle_id=bundle_id, payload_json=payload_json)
            if pinned is None:
                raise RuntimeError(f"IPFS pin failed for bundle_id={bundle_id}")
            verified = custody_gate_worker.verify_bundle_custody(db, bundle_id=bundle_id)
            if not verified:
                return
            anchor_worker.request_anchor(db, bundle_id=bundle_id)
        finally:
            db.close()

    def _process_anchor_request(self, payload: dict) -> None:
        db = SessionLocal()
        try:
            bundle_id = str(payload.get("bundle_id") or "").strip()
            if not bundle_id:
                return
            anchor_worker.process_anchor(db, bundle_id=bundle_id)
        finally:
            db.close()

    def _retry_hash_key(self, *, stream_name: str, message_id: str) -> str:
        return f"retry:{stream_name}:{message_id}"

    def _read_retry_attempt(self, *, stream_name: str, message_id: str) -> int:
        if self._redis is None:
            return 0
        key = self._retry_hash_key(stream_name=stream_name, message_id=message_id)
        raw = self._redis.hget(key, "attempt")
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    def _set_retry_attempt(self, *, stream_name: str, message_id: str, attempt: int) -> None:
        if self._redis is None:
            return
        key = self._retry_hash_key(stream_name=stream_name, message_id=message_id)
        self._redis.hset(
            key,
            mapping={
                "attempt": attempt,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._redis.expire(key, 60 * 60 * 24)

    def _clear_retry_attempt(self, *, stream_name: str, message_id: str) -> None:
        if self._redis is None:
            return
        key = self._retry_hash_key(stream_name=stream_name, message_id=message_id)
        self._redis.delete(key)

    def _compute_retry_delay_seconds(self, attempt: int) -> float:
        base = max(1, settings.REDIS_RETRY_BASE_DELAY_MS)
        max_ms = max(base, settings.REDIS_RETRY_MAX_DELAY_MS)
        delay_ms = min(base * (2 ** max(0, attempt - 1)), max_ms)
        return delay_ms / 1000.0

    def _dead_letter(
        self,
        *,
        stream_name: str,
        message_id: str,
        fields: dict,
        attempt: int,
    ) -> None:
        if self._redis is None:
            return
        entry = {
            "stream_name": stream_name,
            "original_message_id": message_id,
            "attempt": str(attempt),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "fields": json.dumps(fields, separators=(",", ":"), sort_keys=True),
        }
        self._redis.xadd(settings.REDIS_DEAD_LETTER_STREAM, entry)

    def _handle_processing_failure(self, *, stream_name: str, message_id: str, fields: dict) -> bool:
        """
        Returns True when caller should continue loop without ack (retry path),
        returns False when caller should proceed with ack (DLQ terminal path).
        """
        attempt = self._read_retry_attempt(stream_name=stream_name, message_id=message_id) + 1
        self._set_retry_attempt(stream_name=stream_name, message_id=message_id, attempt=attempt)

        max_attempts = max(1, settings.REDIS_RETRY_MAX_ATTEMPTS)
        if attempt >= max_attempts:
            self._dead_letter(
                stream_name=stream_name,
                message_id=message_id,
                fields=fields,
                attempt=attempt,
            )
            self._clear_retry_attempt(stream_name=stream_name, message_id=message_id)
            return False

        delay_seconds = self._compute_retry_delay_seconds(attempt)
        logger.warning(
            "Stream retry scheduled stream=%s message_id=%s attempt=%d delay_s=%.3f",
            stream_name,
            message_id,
            attempt,
            delay_seconds,
        )
        time.sleep(delay_seconds)
        return True


telemetry_stream_service = TelemetryStreamService()
