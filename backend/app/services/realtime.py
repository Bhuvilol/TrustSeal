from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, DefaultDict, Dict, Optional, Set

from fastapi import WebSocket

from ..core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active websocket connections per shipment."""

    def __init__(self) -> None:
        self._connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, shipment_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[shipment_id].add(websocket)

    async def disconnect(self, shipment_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            peers = self._connections.get(shipment_id)
            if not peers:
                return
            peers.discard(websocket)
            if not peers:
                self._connections.pop(shipment_id, None)

    async def broadcast(self, shipment_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self._connections.get(shipment_id, set()))

        if not peers:
            return

        stale: list[WebSocket] = []
        for websocket in peers:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(shipment_id, websocket)

    async def active_connections(self, shipment_id: Optional[str] = None) -> int:
        async with self._lock:
            if shipment_id is not None:
                return len(self._connections.get(shipment_id, set()))
            return sum(len(peers) for peers in self._connections.values())


@dataclass(frozen=True, slots=True)
class ShipmentRealtimeEvent:
    shipment_id: str
    payload: Dict[str, Any]


class ShipmentEventDispatcher:
    """Dispatches realtime events from REST handlers to websocket clients."""

    def __init__(self, manager: ConnectionManager, queue_maxsize: int = 5000) -> None:
        self._manager = manager
        self._queue: asyncio.Queue[ShipmentRealtimeEvent] = asyncio.Queue(maxsize=queue_maxsize)
        self._task: Optional[asyncio.Task[None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._run(), name="shipment-event-dispatcher")
        logger.info("Shipment realtime dispatcher started")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._loop = None
            logger.info("Shipment realtime dispatcher stopped")

    def publish(self, shipment_id: str, payload: Dict[str, Any]) -> None:
        if not self._loop:
            logger.warning("Realtime dispatcher not started; dropping event %s", payload.get("event"))
            return

        event = ShipmentRealtimeEvent(shipment_id=shipment_id, payload=payload)

        def _enqueue() -> None:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Realtime queue is full, dropping event=%s shipment_id=%s",
                    payload.get("event"),
                    shipment_id,
                )

        try:
            self._loop.call_soon_threadsafe(_enqueue)
        except RuntimeError:
            logger.warning("Realtime loop unavailable; dropping event %s", payload.get("event"))

    async def _run(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                await self._manager.broadcast(event.shipment_id, event.payload)
            except Exception:
                logger.exception(
                    "Failed to dispatch realtime event=%s shipment_id=%s",
                    event.payload.get("event"),
                    event.shipment_id,
                )
            finally:
                self._queue.task_done()


def build_realtime_event(event: str, shipment_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": event,
        "shipment_id": shipment_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


shipment_connection_manager = ConnectionManager()
shipment_event_dispatcher = ShipmentEventDispatcher(
    manager=shipment_connection_manager,
    queue_maxsize=settings.REALTIME_QUEUE_MAXSIZE,
)
