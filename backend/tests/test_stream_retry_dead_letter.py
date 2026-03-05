from __future__ import annotations

from app.core.config import settings
from app.services.telemetry_stream_service import TelemetryStreamService


class _FakeRedisRetry:
    def __init__(self) -> None:
        self.hash_store: dict[str, dict[str, str]] = {}
        self.stream_calls: list[tuple[str, dict]] = []
        self.deleted: list[str] = []

    def hget(self, key: str, field: str):
        return self.hash_store.get(key, {}).get(field)

    def hset(self, key: str, mapping: dict):
        self.hash_store.setdefault(key, {})
        for k, v in mapping.items():
            self.hash_store[key][k] = str(v)

    def expire(self, key: str, _seconds: int):
        return True

    def delete(self, key: str):
        self.deleted.append(key)
        self.hash_store.pop(key, None)
        return 1

    def xadd(self, stream_name: str, entry: dict):
        self.stream_calls.append((stream_name, entry))
        return "1-0"


def test_handle_processing_failure_retries_before_max() -> None:
    service = TelemetryStreamService()
    fake = _FakeRedisRetry()
    service._redis = fake  # type: ignore[attr-defined]

    old_max = settings.REDIS_RETRY_MAX_ATTEMPTS
    old_base = settings.REDIS_RETRY_BASE_DELAY_MS
    old_cap = settings.REDIS_RETRY_MAX_DELAY_MS
    try:
        settings.REDIS_RETRY_MAX_ATTEMPTS = 3
        settings.REDIS_RETRY_BASE_DELAY_MS = 1
        settings.REDIS_RETRY_MAX_DELAY_MS = 1

        should_retry = service._handle_processing_failure(
            stream_name="telemetry_stream",
            message_id="1-1",
            fields={"payload": "{}"},
        )
        assert should_retry is True
        assert fake.stream_calls == []
    finally:
        settings.REDIS_RETRY_MAX_ATTEMPTS = old_max
        settings.REDIS_RETRY_BASE_DELAY_MS = old_base
        settings.REDIS_RETRY_MAX_DELAY_MS = old_cap


def test_handle_processing_failure_dead_letters_on_max_attempt() -> None:
    service = TelemetryStreamService()
    fake = _FakeRedisRetry()
    service._redis = fake  # type: ignore[attr-defined]

    old_max = settings.REDIS_RETRY_MAX_ATTEMPTS
    old_dlq = settings.REDIS_DEAD_LETTER_STREAM
    old_base = settings.REDIS_RETRY_BASE_DELAY_MS
    old_cap = settings.REDIS_RETRY_MAX_DELAY_MS
    try:
        settings.REDIS_RETRY_MAX_ATTEMPTS = 2
        settings.REDIS_DEAD_LETTER_STREAM = "test_dlq"
        settings.REDIS_RETRY_BASE_DELAY_MS = 1
        settings.REDIS_RETRY_MAX_DELAY_MS = 1

        # First failure: retry.
        assert (
            service._handle_processing_failure(
                stream_name="telemetry_stream",
                message_id="9-9",
                fields={"payload": "{}"},
            )
            is True
        )
        # Second failure: terminal -> dead-letter + no retry.
        assert (
            service._handle_processing_failure(
                stream_name="telemetry_stream",
                message_id="9-9",
                fields={"payload": "{}"},
            )
            is False
        )

        assert len(fake.stream_calls) == 1
        stream_name, entry = fake.stream_calls[0]
        assert stream_name == "test_dlq"
        assert entry["stream_name"] == "telemetry_stream"
        assert entry["original_message_id"] == "9-9"
        assert entry["attempt"] == "2"
    finally:
        settings.REDIS_RETRY_MAX_ATTEMPTS = old_max
        settings.REDIS_DEAD_LETTER_STREAM = old_dlq
        settings.REDIS_RETRY_BASE_DELAY_MS = old_base
        settings.REDIS_RETRY_MAX_DELAY_MS = old_cap
