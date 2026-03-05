from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.dependencies import (
    _parse_token_registry,
    _validate_ingest_token,
    require_device_ingest_auth,
    require_verifier_ingest_auth,
)


def test_parse_token_registry_handles_invalid_json() -> None:
    assert _parse_token_registry("not-json") == {}


def test_validate_ingest_token_success() -> None:
    registry = {"device-1": "token-1"}
    assert _validate_ingest_token("device-1", "token-1", registry) is True
    assert _validate_ingest_token("device-1", "wrong", registry) is False


def test_require_device_ingest_auth_rejects_invalid_token_when_enabled() -> None:
    prev_enabled = settings.INGEST_DEVICE_AUTH_ENABLED
    prev_registry = settings.INGEST_DEVICE_TOKENS_JSON
    try:
        settings.INGEST_DEVICE_AUTH_ENABLED = True
        settings.INGEST_DEVICE_TOKENS_JSON = '{"device-a":"token-a"}'
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_device_ingest_auth(x_device_id="device-a", x_device_token="wrong"))
        assert exc.value.status_code == 401
    finally:
        settings.INGEST_DEVICE_AUTH_ENABLED = prev_enabled
        settings.INGEST_DEVICE_TOKENS_JSON = prev_registry


def test_require_verifier_ingest_auth_accepts_valid_token_when_enabled() -> None:
    prev_enabled = settings.INGEST_VERIFIER_AUTH_ENABLED
    prev_registry = settings.INGEST_VERIFIER_TOKENS_JSON
    try:
        settings.INGEST_VERIFIER_AUTH_ENABLED = True
        settings.INGEST_VERIFIER_TOKENS_JSON = '{"verifier-a":"token-a"}'
        ctx = asyncio.run(
            require_verifier_ingest_auth(
                x_verifier_device_id="verifier-a",
                x_verifier_token="token-a",
            )
        )
        assert ctx.channel == "verifier"
        assert ctx.identity == "verifier-a"
    finally:
        settings.INGEST_VERIFIER_AUTH_ENABLED = prev_enabled
        settings.INGEST_VERIFIER_TOKENS_JSON = prev_registry
