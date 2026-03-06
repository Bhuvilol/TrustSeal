from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.chain_anchor import ChainAnchor
from ..models.telemetry_batch import TelemetryBatch
from .batch_finalization_service import BatchFinalizationError, batch_finalization_service
from .state_machine_service import state_machine_service

try:
    from web3 import Web3
except Exception:  # pragma: no cover
    Web3 = None  # type: ignore


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndexerResult:
    scanned_from_block: int
    scanned_to_block: int
    event_count: int
    mapped_events: int
    unmatched_events: int
    latest_chain_block: int


class ChainIndexerService:
    """Indexes CustodyTransferred events from chain back into Postgres."""

    def sync_once(
        self,
        db: Session,
        *,
        from_block: int | None = None,
        to_block: int | None = None,
        block_batch_size: int | None = None,
    ) -> dict[str, int]:
        w3, contract = self._load_web3_contract()
        latest_chain_block = int(w3.eth.block_number)
        confirmations = max(0, settings.CHAIN_INDEXER_CONFIRMATIONS)
        safe_to_block = max(0, latest_chain_block - confirmations)

        resolved_from = self._resolve_from_block(db, from_block)
        resolved_to = safe_to_block if to_block is None else min(int(to_block), safe_to_block)
        if resolved_from > resolved_to:
            return asdict(IndexerResult(
                scanned_from_block=resolved_from,
                scanned_to_block=resolved_to,
                event_count=0,
                mapped_events=0,
                unmatched_events=0,
                latest_chain_block=latest_chain_block,
            ))

        batch_size = max(1, int(block_batch_size or settings.CHAIN_INDEXER_BLOCK_BATCH_SIZE))
        events_total = 0
        mapped_total = 0
        unmatched_total = 0

        cursor = resolved_from
        while cursor <= resolved_to:
            chunk_to = min(resolved_to, cursor + batch_size - 1)
            logs = self._get_custody_logs(contract, from_block=cursor, to_block=chunk_to)
            events_total += len(logs)
            for event in logs:
                mapped = self._ingest_event(
                    db,
                    event=event,
                    network=f"polygon-{settings.CHAIN_CHAIN_ID}",
                    contract_address=str(settings.CHAIN_CONTRACT_ADDRESS or ""),
                )
                if mapped:
                    mapped_total += 1
                else:
                    unmatched_total += 1
            cursor = chunk_to + 1

        return asdict(IndexerResult(
            scanned_from_block=resolved_from,
            scanned_to_block=resolved_to,
            event_count=events_total,
            mapped_events=mapped_total,
            unmatched_events=unmatched_total,
            latest_chain_block=latest_chain_block,
        ))

    @staticmethod
    def _get_custody_logs(contract: Any, *, from_block: int, to_block: int) -> list[Any]:
        accessor = contract.events.CustodyTransferred()
        try:
            return accessor.get_logs(
                from_block=from_block,
                to_block=to_block,
            )
        except TypeError:
            return accessor.get_logs(
                fromBlock=from_block,
                toBlock=to_block,
            )

    def _load_web3_contract(self) -> tuple[Any, Any]:
        if Web3 is None:
            raise BatchFinalizationError("web3 is not installed.")
        if not settings.CHAIN_RPC_URL:
            raise BatchFinalizationError("CHAIN_RPC_URL is missing.")
        if not settings.CHAIN_CONTRACT_ADDRESS:
            raise BatchFinalizationError("CHAIN_CONTRACT_ADDRESS is missing.")

        w3 = Web3(Web3.HTTPProvider(settings.CHAIN_RPC_URL))
        if not w3.is_connected():
            raise BatchFinalizationError("Unable to connect to chain RPC.")
        abi = batch_finalization_service._load_chain_abi()
        contract = w3.eth.contract(
            address=w3.to_checksum_address(settings.CHAIN_CONTRACT_ADDRESS),
            abi=abi,
        )
        return w3, contract

    def _resolve_from_block(self, db: Session, from_block: int | None) -> int:
        if from_block is not None:
            return max(0, int(from_block))
        start_block = max(0, settings.CHAIN_INDEXER_START_BLOCK)
        max_seen = (
            db.query(func.max(ChainAnchor.block_number))
            .filter(ChainAnchor.network == f"polygon-{settings.CHAIN_CHAIN_ID}")
            .scalar()
        )
        if max_seen is None:
            return start_block
        return max(start_block, int(max_seen) + 1)

    def _ingest_event(
        self,
        db: Session,
        *,
        event: Any,
        network: str,
        contract_address: str,
    ) -> bool:
        args = getattr(event, "args", {}) or {}
        shipment_id_raw = str(args.get("shipmentId") or "").strip()
        bundle_id_raw = str(args.get("bundleId") or "").strip()
        ipfs_cid = str(args.get("ipfsCid") or "").strip() or None
        tx_hash = self._tx_hash_hex(getattr(event, "transactionHash", None))
        block_number = int(getattr(event, "blockNumber", 0) or 0)
        anchored_at = self._event_time_utc(args.get("timestamp"))

        batch = self._find_batch_by_bundle_id(db, bundle_id_raw)
        anchor = None
        if batch is not None:
            anchor = db.query(ChainAnchor).filter(ChainAnchor.bundle_id == batch.id).first()
        if anchor is None and tx_hash:
            anchor = db.query(ChainAnchor).filter(ChainAnchor.tx_hash == tx_hash).first()

        if anchor is None and batch is not None:
            anchor = ChainAnchor(
                bundle_id=batch.id,
                shipment_id=batch.shipment_id,
                network=network,
                contract_address=contract_address,
                anchor_status="pending",
            )
            db.add(anchor)
            db.flush()

        if anchor is None:
            logger.warning(
                "Chain event unmatched tx_hash=%s shipment_id=%s bundle_id=%s",
                tx_hash,
                shipment_id_raw,
                bundle_id_raw,
            )
            return False

        self._promote_anchor_to_confirmed(anchor)
        anchor.network = network
        anchor.contract_address = contract_address
        anchor.tx_hash = tx_hash or anchor.tx_hash
        anchor.block_number = block_number or anchor.block_number
        anchor.anchored_at = anchored_at
        anchor.error_message = None

        if batch is not None:
            if ipfs_cid and not batch.ipfs_cid:
                batch.ipfs_cid = ipfs_cid
            batch.tx_hash = tx_hash or batch.tx_hash
            self._promote_batch_to_anchored(batch, anchored_at=anchored_at)

        db.commit()
        return True

    def _find_batch_by_bundle_id(self, db: Session, bundle_id_raw: str) -> TelemetryBatch | None:
        try:
            bundle_uuid = uuid.UUID(bundle_id_raw)
        except (TypeError, ValueError):
            return None
        return db.query(TelemetryBatch).filter(TelemetryBatch.id == bundle_uuid).first()

    @staticmethod
    def _tx_hash_hex(tx_hash: Any) -> str | None:
        if tx_hash is None:
            return None
        try:
            return tx_hash.hex()
        except Exception:
            raw = str(tx_hash).strip()
            return raw or None

    @staticmethod
    def _event_time_utc(raw_timestamp: Any) -> datetime:
        try:
            ts = int(raw_timestamp)
            if ts > 0:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass
        return datetime.now(timezone.utc)

    def _promote_anchor_to_confirmed(self, anchor: ChainAnchor) -> None:
        if anchor.anchor_status == "confirmed":
            return
        if anchor.anchor_status == "failed":
            for step in ("pending", "submitted", "confirmed"):
                self._apply_anchor_transition(anchor, step)
            return
        if anchor.anchor_status == "pending":
            self._apply_anchor_transition(anchor, "submitted")
            self._apply_anchor_transition(anchor, "confirmed")
            return
        if anchor.anchor_status == "submitted":
            self._apply_anchor_transition(anchor, "confirmed")
            return

    def _apply_anchor_transition(self, anchor: ChainAnchor, to_state: str) -> None:
        transition = state_machine_service.ensure_transition(
            machine="anchor",
            from_state=anchor.anchor_status,
            to_state=to_state,
        )
        if transition.ok:
            anchor.anchor_status = to_state

    def _promote_batch_to_anchored(self, batch: TelemetryBatch, *, anchored_at: datetime) -> None:
        if batch.status == "anchored":
            batch.anchored_at = anchored_at
            batch.error_message = None
            return

        if batch.status in {"failed", "custody_verified"}:
            transition = state_machine_service.ensure_transition(
                machine="batch",
                from_state=batch.status,
                to_state="anchor_pending",
            )
            if transition.ok:
                batch.status = "anchor_pending"

        transition = state_machine_service.ensure_transition(
            machine="batch",
            from_state=batch.status,
            to_state="anchored",
        )
        if transition.ok:
            batch.status = "anchored"
            batch.anchored_at = anchored_at
            batch.error_message = None


chain_indexer_service = ChainIndexerService()
