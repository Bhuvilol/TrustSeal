from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from ..core.config import ROOT_DIR, settings

try:
    from web3 import Web3
except Exception:  # pragma: no cover
    Web3 = None  # type: ignore


class BatchFinalizationError(Exception):
    pass


logger = logging.getLogger(__name__)


class BatchFinalizationService:
    """Optional finalization adapters for IPFS pinning and on-chain custody anchor."""

    def finalize(
        self,
        *,
        shipment_id: str,
        epoch: int,
        batch_hash: str,
        payload_json: str,
        bundle_id: str | None = None,
    ) -> Dict[str, Optional[str]]:
        ipfs_cid: Optional[str] = None
        tx_hash: Optional[str] = None
        resolved_bundle_id = (bundle_id or f"{shipment_id}:{epoch}").strip()

        if settings.IPFS_PIN_ENABLED:
            ipfs_cid = self._pin_to_ipfs(
                shipment_id=shipment_id,
                epoch=epoch,
                batch_hash=batch_hash,
                payload_json=payload_json,
            )

        if settings.CHAIN_ANCHOR_ENABLED:
            if not ipfs_cid:
                raise BatchFinalizationError("Chain anchoring requires an IPFS CID.")
            tx_hash = self._anchor_on_chain(
                shipment_id=shipment_id,
                bundle_id=resolved_bundle_id,
                bundle_hash=batch_hash,
                ipfs_cid=ipfs_cid,
            )

        return {"ipfs_cid": ipfs_cid, "tx_hash": tx_hash}

    def _pin_to_ipfs(
        self,
        *,
        shipment_id: str,
        epoch: int,
        batch_hash: str,
        payload_json: str,
    ) -> str:
        if not settings.IPFS_PIN_JWT:
            raise BatchFinalizationError("IPFS pinning enabled but IPFS_PIN_JWT is missing.")

        payload: Dict[str, Any] = {
            "pinataMetadata": {
                "name": f"trustseal-{shipment_id}-{epoch}",
            },
            "pinataContent": {
                "shipment_id": shipment_id,
                "epoch": epoch,
                "batch_hash": batch_hash,
                "records": json.loads(payload_json),
            },
        }

        headers = {
            "Authorization": f"Bearer {settings.IPFS_PIN_JWT}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(settings.IPFS_PIN_ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        cid = body.get("IpfsHash")
        if not cid:
            raise BatchFinalizationError("IPFS response missing IpfsHash.")
        return str(cid)

    def _anchor_on_chain(
        self,
        *,
        shipment_id: str,
        bundle_id: str,
        bundle_hash: str,
        ipfs_cid: str,
    ) -> str:
        if Web3 is None:
            raise BatchFinalizationError("web3 is not installed, but CHAIN_ANCHOR_ENABLED=true.")

        if not settings.CHAIN_RPC_URL:
            raise BatchFinalizationError("CHAIN_RPC_URL is missing.")
        if not settings.CHAIN_PRIVATE_KEY:
            raise BatchFinalizationError("CHAIN_PRIVATE_KEY is missing.")
        if not settings.CHAIN_CONTRACT_ADDRESS:
            raise BatchFinalizationError("CHAIN_CONTRACT_ADDRESS is missing.")

        w3 = Web3(Web3.HTTPProvider(settings.CHAIN_RPC_URL))
        if not w3.is_connected():
            raise BatchFinalizationError("Unable to connect to chain RPC.")

        abi = self._load_chain_abi()
        contract = w3.eth.contract(
            address=w3.to_checksum_address(settings.CHAIN_CONTRACT_ADDRESS),
            abi=abi,
        )
        account = w3.eth.account.from_key(settings.CHAIN_PRIVATE_KEY)
        nonce = w3.eth.get_transaction_count(account.address, "pending")
        gas_price = int(w3.eth.gas_price)
        max_attempts = max(1, settings.CHAIN_ANCHOR_MAX_ATTEMPTS)

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                tx = contract.functions.transferCustody(
                    shipment_id,
                    bundle_id,
                    bundle_hash,
                    settings.CHAIN_PREVIOUS_CUSTODIAN,
                    ipfs_cid,
                ).build_transaction(
                    {
                        "from": account.address,
                        "nonce": nonce,
                        "chainId": settings.CHAIN_CHAIN_ID,
                        "gas": 400000,
                        "gasPrice": gas_price,
                    }
                )
                signed = account.sign_transaction(tx)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = w3.eth.wait_for_transaction_receipt(
                    tx_hash,
                    timeout=max(1, settings.CHAIN_RECEIPT_TIMEOUT_SECONDS),
                )
                if receipt.status != 1:
                    raise BatchFinalizationError("Chain transaction reverted.")
                return tx_hash.hex()
            except BatchFinalizationError:
                raise
            except Exception as exc:
                last_error = exc
                lower = str(exc).lower()
                retryable = self._is_retryable_chain_error(lower)
                if not retryable or attempt >= max_attempts:
                    break

                if self._needs_nonce_refresh(lower):
                    nonce = w3.eth.get_transaction_count(account.address, "pending")
                if self._needs_gas_bump(lower):
                    bump = max(1, settings.CHAIN_REPLACEMENT_GAS_BUMP_PERCENT)
                    gas_price = int(gas_price * (1 + (bump / 100.0)))
                else:
                    gas_price = int(gas_price * 1.05)

                delay = self._retry_delay_seconds(attempt)
                logger.warning(
                    "Chain anchor retry attempt=%d/%d nonce=%s gas_price=%s delay_s=%.3f error=%s",
                    attempt,
                    max_attempts,
                    nonce,
                    gas_price,
                    delay,
                    exc,
                )
                time.sleep(delay)

        raise BatchFinalizationError(
            f"Chain anchor failed after {max_attempts} attempts: {last_error}"
        )

    def _retry_delay_seconds(self, attempt: int) -> float:
        base = max(1, settings.CHAIN_ANCHOR_RETRY_BASE_DELAY_MS)
        max_ms = max(base, settings.CHAIN_ANCHOR_RETRY_MAX_DELAY_MS)
        delay_ms = min(base * (2 ** max(0, attempt - 1)), max_ms)
        return delay_ms / 1000.0

    @staticmethod
    def _is_retryable_chain_error(message: str) -> bool:
        retry_tokens = (
            "nonce too low",
            "nonce too high",
            "replacement transaction underpriced",
            "already known",
            "timeout",
            "timed out",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "429",
            "5xx",
        )
        return any(token in message for token in retry_tokens)

    @staticmethod
    def _needs_nonce_refresh(message: str) -> bool:
        return "nonce too low" in message or "nonce too high" in message

    @staticmethod
    def _needs_gas_bump(message: str) -> bool:
        return "replacement transaction underpriced" in message or "already known" in message

    def _load_chain_abi(self) -> list[dict]:
        env_abi = (settings.CHAIN_CONTRACT_ABI_JSON or "").strip()
        if env_abi:
            try:
                parsed = json.loads(env_abi)
            except json.JSONDecodeError as exc:
                raise BatchFinalizationError(f"CHAIN_CONTRACT_ABI_JSON is invalid JSON: {exc}") from exc
            if self._supports_phase5_transfer(parsed):
                return parsed
            logger.warning(
                "Ignoring stale CHAIN_CONTRACT_ABI_JSON (missing phase-5 transferCustody signature); "
                "falling back to CHAIN_CONTRACT_ABI_PATH."
            )

        abi_path = Path(settings.CHAIN_CONTRACT_ABI_PATH)
        if not abi_path.is_absolute():
            backend_relative = ROOT_DIR / abi_path
            abi_path = backend_relative if backend_relative.exists() else Path.cwd() / abi_path
        if not abi_path.exists():
            raise BatchFinalizationError(
                "No valid contract ABI found. Set CHAIN_CONTRACT_ABI_JSON with phase-5 signature "
                "or set CHAIN_CONTRACT_ABI_PATH to a compiled artifact/deployment JSON."
            )

        try:
            data = json.loads(abi_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise BatchFinalizationError(f"Unable to read ABI file {abi_path}: {exc}") from exc

        abi = data.get("abi", data)
        if isinstance(abi, str):
            try:
                abi = json.loads(abi)
            except json.JSONDecodeError as exc:
                raise BatchFinalizationError(f"ABI file {abi_path} contains invalid ABI JSON string: {exc}") from exc
        if not isinstance(abi, list):
            raise BatchFinalizationError(f"ABI file {abi_path} has unsupported format.")
        if not self._supports_phase5_transfer(abi):
            raise BatchFinalizationError(
                "Contract ABI does not match phase-5 signature "
                "(transferCustody(string,string,string,address,string)). Redeploy/compile contract."
            )
        return abi

    @staticmethod
    def _supports_phase5_transfer(abi: list[dict]) -> bool:
        for entry in abi:
            if entry.get("type") != "function":
                continue
            if entry.get("name") != "transferCustody":
                continue
            inputs = entry.get("inputs") or []
            if len(inputs) != 5:
                continue
            expected = ["string", "string", "string", "address", "string"]
            actual = [i.get("type") for i in inputs]
            return actual == expected
        return False


batch_finalization_service = BatchFinalizationService()
