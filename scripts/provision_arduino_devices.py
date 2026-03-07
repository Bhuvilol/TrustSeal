from __future__ import annotations

import base64
import json
import os
import re
import secrets
import socket
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV = ROOT / "backend" / ".env"
TRACKER_CONFIG_LOCAL = ROOT / "iot" / "tracker_arduino" / "tracker_config.local.h"
VERIFIER_CONFIG_LOCAL = ROOT / "iot" / "verifier_arduino" / "verifier_config.local.h"
TRACKER_SECRETS_LOCAL = ROOT / "iot" / "tracker_arduino" / "tracker_secrets.local.h"
VERIFIER_SECRETS_LOCAL = ROOT / "iot" / "verifier_arduino" / "verifier_secrets.local.h"

TRACKER_DEVICE_ID = "0cb901e3-6cf7-4be2-83f4-3a232a283e33"
VERIFIER_DEVICE_ID = "4fedec9d-eca7-428f-9803-d6728d874c54"


def _first_lan_ip() -> str:
    seen: set[str] = set()
    for name in (socket.gethostname(), socket.getfqdn(), "localhost"):
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(name, None, socket.AF_INET):
                if family != socket.AF_INET:
                    continue
                ip = sockaddr[0]
                if ip.startswith("127.") or ip in seen:
                    continue
                seen.add(ip)
                return ip
        except socket.gaierror:
            continue
    return "192.168.1.100"


def _new_token() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def _generate_keypair() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


def _replace_env_line(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*?(?=^\w[\w_]*=|\Z)", re.MULTILINE | re.DOTALL)
    replacement = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(lambda _match: replacement, content)
    return content.rstrip() + "\n" + replacement + "\n"


def _replace_env_block(content: str, start_key: str, end_marker: str, replacement_lines: list[str]) -> str:
    pattern = re.compile(
        rf"^{re.escape(start_key)}=.*?(?=^{re.escape(end_marker)})",
        re.MULTILINE | re.DOTALL,
    )
    replacement = "\n".join(replacement_lines) + "\n"
    if pattern.search(content):
        return pattern.sub(lambda _match: replacement, content)
    return content.rstrip() + "\n" + replacement


def _c_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n\"\n  \"")
    return f"  \"{escaped}\";"


def main() -> int:
    if not BACKEND_ENV.exists():
        raise SystemExit(f"Missing {BACKEND_ENV}")

    bridge_host = os.getenv("DEVICE_BRIDGE_HOST", _first_lan_ip())
    bridge_port = int(os.getenv("DEVICE_BRIDGE_PORT", "443"))
    device_api_use_tls = os.getenv("DEVICE_API_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    verifier_wifi_ssid = os.getenv("VERIFIER_WIFI_SSID", "")
    verifier_wifi_password = os.getenv("VERIFIER_WIFI_PASSWORD", "")

    tracker_private_pem, tracker_public_pem = _generate_keypair()
    verifier_private_pem, verifier_public_pem = _generate_keypair()

    tracker_pubkey_id = "tracker-key-arduino-01"
    tracker_token = _new_token()
    verifier_token = _new_token()

    env_content = BACKEND_ENV.read_text(encoding="utf-8")
    env_content = _replace_env_block(
        env_content,
        "INGEST_DEVICE_TOKENS_JSON",
        "# Archival",
        [
            f'INGEST_DEVICE_TOKENS_JSON={json.dumps({TRACKER_DEVICE_ID: tracker_token}, separators=(",", ":"))}',
            f'INGEST_VERIFIER_TOKENS_JSON={json.dumps({VERIFIER_DEVICE_ID: verifier_token}, separators=(",", ":"))}',
            f'INGEST_DEVICE_PUBLIC_KEYS_JSON={json.dumps({tracker_pubkey_id: tracker_public_pem}, separators=(",", ":"))}',
            f'INGEST_VERIFIER_PUBLIC_KEYS_JSON={json.dumps({VERIFIER_DEVICE_ID: verifier_public_pem}, separators=(",", ":"))}',
            "INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS=300",
            "INGEST_REPLAY_MAX_EVENT_AGE_SECONDS=86400",
        ],
    )
    BACKEND_ENV.write_text(env_content, encoding="utf-8")

    TRACKER_CONFIG_LOCAL.write_text(
        "\n".join(
            [
                "#undef TRACKER_API_HOST",
                f'#define TRACKER_API_HOST "{bridge_host}"',
                "#undef TRACKER_API_PORT",
                f"#define TRACKER_API_PORT {bridge_port}",
                "#undef TRACKER_API_USE_TLS",
                f"#define TRACKER_API_USE_TLS {1 if device_api_use_tls else 0}",
                "#undef TRACKER_API_BEARER_TOKEN",
                f'#define TRACKER_API_BEARER_TOKEN "{tracker_token}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    VERIFIER_CONFIG_LOCAL.write_text(
        "\n".join(
            [
                "#undef VERIFIER_WIFI_SSID",
                f'#define VERIFIER_WIFI_SSID "{verifier_wifi_ssid}"',
                "#undef VERIFIER_WIFI_PASSWORD",
                f'#define VERIFIER_WIFI_PASSWORD "{verifier_wifi_password}"',
                "#undef VERIFIER_API_HOST",
                f'#define VERIFIER_API_HOST "{bridge_host}"',
                "#undef VERIFIER_API_PORT",
                f"#define VERIFIER_API_PORT {bridge_port}",
                "#undef VERIFIER_API_USE_TLS",
                f"#define VERIFIER_API_USE_TLS {1 if device_api_use_tls else 0}",
                "#undef VERIFIER_API_BEARER_TOKEN",
                f'#define VERIFIER_API_BEARER_TOKEN "{verifier_token}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    TRACKER_SECRETS_LOCAL.write_text(
        "\n".join(
            [
                f"static const char *TRACKER_PRIVATE_KEY_PEM =",
                _c_string_literal(tracker_private_pem),
                f'static const char *TRACKER_PUBKEY_ID = "{tracker_pubkey_id}";',
                "",
            ]
        ),
        encoding="utf-8",
    )
    VERIFIER_SECRETS_LOCAL.write_text(
        "\n".join(
            [
                "static const char *VERIFIER_PRIVATE_KEY_PEM =",
                _c_string_literal(verifier_private_pem),
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Provisioned Arduino device credentials for bridge host {bridge_host}:{bridge_port}")
    print(f"Wrote {TRACKER_CONFIG_LOCAL.relative_to(ROOT)}")
    print(f"Wrote {VERIFIER_CONFIG_LOCAL.relative_to(ROOT)}")
    print(f"Wrote {TRACKER_SECRETS_LOCAL.relative_to(ROOT)}")
    print(f"Wrote {VERIFIER_SECRETS_LOCAL.relative_to(ROOT)}")
    print(f"Updated {BACKEND_ENV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ModuleNotFoundError as exc:
        if exc.name == "cryptography":
            raise SystemExit(
                "The 'cryptography' package is required. Use backend/.venv Python or install it in your current interpreter."
            ) from exc
        raise
