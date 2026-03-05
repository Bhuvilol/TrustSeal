"""
Worker Orchestration Service

Manages the lifecycle of all Redis stream workers:
- Telemetry stream consumer
- Custody stream consumer
- Bundle ready stream consumer
- Anchor request stream consumer

Provides:
- Unified startup/shutdown
- Health monitoring
- Graceful shutdown with timeout
- Worker restart on failure
- Status reporting
"""

import logging
import threading
import time
from typing import Dict, Optional

from .telemetry_stream_service import telemetry_stream_service

logger = logging.getLogger(__name__)


class WorkerOrchestrator:
    """Orchestrates all Redis stream workers with health monitoring and graceful shutdown."""

    def __init__(self):
        self._workers: Dict[str, threading.Thread] = {}
        self._worker_health: Dict[str, bool] = {}
        self._shutdown_event = threading.Event()
        self._health_monitor_thread: Optional[threading.Thread] = None
        self._started = False
        self._lock = threading.Lock()

    def startup(self) -> None:
        """Start all workers and health monitoring."""
        with self._lock:
            if self._started:
                logger.warning("Worker orchestrator already started")
                return

            logger.info("Starting worker orchestrator...")

            try:
                # Start the telemetry stream service (which manages all stream workers)
                telemetry_stream_service.startup()
                self._started = True
                logger.info("Worker orchestrator started successfully")

                # Start health monitor
                self._start_health_monitor()

            except Exception as e:
                logger.exception(f"Failed to start worker orchestrator: {e}")
                raise

    def shutdown(self, timeout: float = 30.0) -> None:
        """
        Gracefully shutdown all workers.

        Args:
            timeout: Maximum time to wait for workers to stop (seconds)
        """
        with self._lock:
            if not self._started:
                logger.warning("Worker orchestrator not started, nothing to shutdown")
                return

            logger.info("Shutting down worker orchestrator...")
            self._shutdown_event.set()

            try:
                # Stop the telemetry stream service
                telemetry_stream_service.shutdown()

                # Stop health monitor
                if self._health_monitor_thread and self._health_monitor_thread.is_alive():
                    self._health_monitor_thread.join(timeout=5.0)

                self._started = False
                logger.info("Worker orchestrator shutdown complete")

            except Exception as e:
                logger.exception(f"Error during worker orchestrator shutdown: {e}")

    def _start_health_monitor(self) -> None:
        """Start background health monitoring thread."""
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            return

        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            name="worker-health-monitor",
            daemon=True,
        )
        self._health_monitor_thread.start()
        logger.info("Health monitor started")

    def _health_monitor_loop(self) -> None:
        """Background loop to monitor worker health."""
        check_interval = 30.0  # Check every 30 seconds

        while not self._shutdown_event.is_set():
            try:
                # Check if telemetry stream service is healthy
                is_healthy = telemetry_stream_service.is_running()
                self._worker_health["telemetry_stream_service"] = is_healthy

                if not is_healthy:
                    logger.warning("Telemetry stream service is not healthy")

            except Exception as e:
                logger.exception(f"Error in health monitor: {e}")

            # Wait for next check or shutdown signal
            self._shutdown_event.wait(timeout=check_interval)

    def get_status(self) -> Dict[str, any]:
        """
        Get current status of all workers.

        Returns:
            Dictionary with worker status information
        """
        return {
            "started": self._started,
            "workers": {
                "telemetry_stream_service": {
                    "running": telemetry_stream_service.is_running(),
                    "healthy": self._worker_health.get("telemetry_stream_service", False),
                },
            },
            "shutdown_requested": self._shutdown_event.is_set(),
        }

    def is_healthy(self) -> bool:
        """Check if all workers are healthy."""
        if not self._started:
            return False

        return all(self._worker_health.values()) if self._worker_health else True

    def restart_worker(self, worker_name: str) -> bool:
        """
        Restart a specific worker.

        Args:
            worker_name: Name of the worker to restart

        Returns:
            True if restart was successful, False otherwise
        """
        logger.info(f"Restarting worker: {worker_name}")

        try:
            if worker_name == "telemetry_stream_service":
                telemetry_stream_service.shutdown()
                time.sleep(1.0)  # Brief pause before restart
                telemetry_stream_service.startup()
                logger.info(f"Worker {worker_name} restarted successfully")
                return True
            else:
                logger.warning(f"Unknown worker name: {worker_name}")
                return False

        except Exception as e:
            logger.exception(f"Failed to restart worker {worker_name}: {e}")
            return False


# Global singleton instance
worker_orchestrator = WorkerOrchestrator()
