from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.chain_anchor import ChainAnchor
from ..models.custody_transfer import CustodyTransfer
from ..models.ipfs_object import IpfsObject
from ..models.telemetry_batch import TelemetryBatch
from ..models.telemetry_event import TelemetryEvent


class ArchivalService:
    """Retention policy evaluator for telemetry pipeline data."""

    def policy(self) -> dict:
        return {
            "hot_retention_days": settings.ARCHIVE_HOT_RETENTION_DAYS,
            "cold_retention_days": settings.ARCHIVE_COLD_RETENTION_DAYS,
            "purge_retention_days": settings.ARCHIVE_PURGE_RETENTION_DAYS,
            "purge_enabled": settings.ARCHIVE_ENABLE_PURGE,
        }

    def cutoffs(self, *, now: datetime | None = None) -> dict[str, datetime]:
        ref = now or datetime.now(timezone.utc)
        return {
            "hot_cutoff": ref - timedelta(days=max(1, settings.ARCHIVE_HOT_RETENTION_DAYS)),
            "cold_cutoff": ref - timedelta(days=max(1, settings.ARCHIVE_COLD_RETENTION_DAYS)),
            "purge_cutoff": ref - timedelta(days=max(1, settings.ARCHIVE_PURGE_RETENTION_DAYS)),
        }

    def candidate_counts(self, db: Session) -> dict:
        cut = self.cutoffs()
        hot_cutoff = cut["hot_cutoff"]
        cold_cutoff = cut["cold_cutoff"]
        purge_cutoff = cut["purge_cutoff"]

        return {
            "telemetry_events": {
                "cold_archive_candidates": self._count(db, TelemetryEvent.created_at, hot_cutoff),
                "deep_archive_candidates": self._count(db, TelemetryEvent.created_at, cold_cutoff),
                "purge_candidates": self._count(db, TelemetryEvent.created_at, purge_cutoff),
            },
            "custody_transfers": {
                "cold_archive_candidates": self._count(db, CustodyTransfer.created_at, hot_cutoff),
                "deep_archive_candidates": self._count(db, CustodyTransfer.created_at, cold_cutoff),
                "purge_candidates": self._count(db, CustodyTransfer.created_at, purge_cutoff),
            },
            "telemetry_batches": {
                "cold_archive_candidates": self._count(db, TelemetryBatch.created_at, hot_cutoff),
                "deep_archive_candidates": self._count(db, TelemetryBatch.created_at, cold_cutoff),
                "purge_candidates": self._count(db, TelemetryBatch.created_at, purge_cutoff),
            },
            "ipfs_objects": {
                "cold_archive_candidates": self._count(db, IpfsObject.created_at, hot_cutoff),
                "deep_archive_candidates": self._count(db, IpfsObject.created_at, cold_cutoff),
                "purge_candidates": self._count(db, IpfsObject.created_at, purge_cutoff),
            },
            "chain_anchors": {
                "cold_archive_candidates": self._count(db, ChainAnchor.created_at, hot_cutoff),
                "deep_archive_candidates": self._count(db, ChainAnchor.created_at, cold_cutoff),
                "purge_candidates": self._count(db, ChainAnchor.created_at, purge_cutoff),
            },
        }

    def _count(self, db: Session, column, cutoff: datetime) -> int:
        count = db.query(func.count()).filter(column < cutoff).scalar() or 0
        return int(count)


archival_service = ArchivalService()
