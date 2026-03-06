"""
run_worker.py - TrustSeal worker process runner

Starts the application in worker-only mode so Redis consumers can be deployed
separately from the API server in managed environments.
"""

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path


project_root = Path(__file__).parent.absolute()
venv_python = project_root / ".venv" / "Scripts" / "python.exe"
current_python = Path(sys.executable).resolve()
if venv_python.exists():
    target_python = venv_python.resolve()
    if current_python != target_python:
        result = subprocess.run([str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])
        sys.exit(result.returncode)

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ["APP_PROCESS_ROLE"] = "worker"

from app.services.worker_orchestrator import worker_orchestrator  # noqa: E402


async def _main() -> None:
    worker_orchestrator.startup()
    stop_event = asyncio.Event()

    def _stop(*_args) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except ValueError:
            pass

    print("TrustSeal worker process started. Press Ctrl+C to stop.")
    await stop_event.wait()
    worker_orchestrator.shutdown(timeout=30.0)


if __name__ == "__main__":
    asyncio.run(_main())
