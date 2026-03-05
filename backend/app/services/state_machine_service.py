from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TransitionResult:
    ok: bool
    error: str | None = None


class StateMachineService:
    TELEMETRY_INGEST_TRANSITIONS = {
        "received": {"verified", "rejected"},
        "verified": {"queued", "rejected"},
        "queued": {"persisted", "rejected"},
        "persisted": {"bundled"},
        "bundled": set(),
        "rejected": set(),
    }

    BATCH_TRANSITIONS = {
        "open": {"finalized", "failed"},
        "finalized": {"ipfs_pinned", "failed"},
        "ipfs_pinned": {"custody_verified", "failed"},
        "custody_verified": {"anchor_pending", "failed"},
        "anchor_pending": {"anchored", "failed"},
        "anchored": set(),
        "failed": {"finalized", "ipfs_pinned", "anchor_pending"},
    }

    ANCHOR_TRANSITIONS = {
        "pending": {"submitted", "failed"},
        "submitted": {"confirmed", "failed"},
        "confirmed": set(),
        "failed": {"pending", "submitted"},
    }

    def can_transition(self, *, machine: str, from_state: str, to_state: str) -> bool:
        transitions = self._machine(machine)
        if from_state == to_state:
            return True
        allowed = transitions.get(from_state, set())
        return to_state in allowed

    def ensure_transition(self, *, machine: str, from_state: str, to_state: str) -> TransitionResult:
        if self.can_transition(machine=machine, from_state=from_state, to_state=to_state):
            return TransitionResult(ok=True)
        return TransitionResult(
            ok=False,
            error=f"Invalid transition on {machine}: {from_state} -> {to_state}",
        )

    def _machine(self, machine: str) -> dict[str, set[str]]:
        if machine == "telemetry_ingest":
            return self.TELEMETRY_INGEST_TRANSITIONS
        if machine == "batch":
            return self.BATCH_TRANSITIONS
        if machine == "anchor":
            return self.ANCHOR_TRANSITIONS
        raise ValueError(f"Unknown state machine: {machine}")


state_machine_service = StateMachineService()
