from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Iterable, List

from .prompts import INSUFFICIENT_CONTEXT_RESPONSE


@dataclass(slots=True)
class MemoryTurn:
    user_message: str
    assistant_message: str
    created_at: datetime


class ShortTermConversationMemory:
    def __init__(self, *, window_size: int, ttl_minutes: int) -> None:
        self._window_size = max(1, window_size)
        self._ttl = timedelta(minutes=max(5, ttl_minutes))
        self._store: Dict[str, Deque[MemoryTurn]] = defaultdict(deque)
        self._last_updated: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def get_recent_turns(self, scope_key: str) -> List[MemoryTurn]:
        async with self._lock:
            self._evict_expired()
            self._last_updated[scope_key] = datetime.now(timezone.utc)
            return list(self._store.get(scope_key, deque()))

    async def append_turn(self, scope_key: str, user_message: str, assistant_message: str) -> None:
        async with self._lock:
            self._evict_expired()
            turns = self._store[scope_key]
            turns.append(
                MemoryTurn(
                    user_message=user_message,
                    assistant_message=assistant_message,
                    created_at=datetime.now(timezone.utc),
                )
            )
            while len(turns) > self._window_size:
                turns.popleft()
            self._last_updated[scope_key] = datetime.now(timezone.utc)

    def _evict_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            scope_key
            for scope_key, updated in self._last_updated.items()
            if now - updated > self._ttl
        ]
        for scope_key in expired:
            self._store.pop(scope_key, None)
            self._last_updated.pop(scope_key, None)


def format_history_for_prompt(turns: Iterable[MemoryTurn]) -> str:
    lines: list[str] = []
    for turn in turns:
        lines.append(f"User: {turn.user_message}")
        lines.append(f"Assistant: {turn.assistant_message}")
    return "\n".join(lines).strip()


def should_persist_long_term(user_message: str, assistant_message: str) -> bool:
    if not assistant_message or assistant_message.strip() == INSUFFICIENT_CONTEXT_RESPONSE:
        return False
    text = assistant_message.lower()
    indicators = ("recommendation", "next action", "risk", "temperature", "breach", "alert")
    has_indicator = any(token in text for token in indicators)
    return has_indicator or len(assistant_message) >= 240 or any(ch.isdigit() for ch in assistant_message)
