from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Iterable

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iot.http_bridge.device_ingest_bridge import app


def _candidate_ipv4_addresses() -> Iterable[str]:
    seen: set[str] = set()
    hostnames = {socket.gethostname(), socket.getfqdn(), "localhost"}
    for name in hostnames:
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(name, None, socket.AF_INET):
                if family != socket.AF_INET:
                    continue
                ip = sockaddr[0]
                if ip.startswith("127."):
                    continue
                if ip in seen:
                    continue
                seen.add(ip)
                yield ip
        except socket.gaierror:
            continue


def main() -> int:
    host = os.getenv("BRIDGE_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("BRIDGE_PORT", "8081"))
    backend_base_url = os.getenv("BRIDGE_BACKEND_BASE_URL", "https://trustseal.onrender.com").rstrip("/")

    print(f"TrustSeal device bridge -> {backend_base_url}")
    print(f"Listening on {host}:{port}")
    print("Possible LAN IPs for Arduino configs:")
    for ip in _candidate_ipv4_addresses():
        print(f"  - {ip}")

    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
