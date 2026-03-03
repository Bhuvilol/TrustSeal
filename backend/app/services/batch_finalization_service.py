from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

from ..core.config import settings

try:
    from web3 import Web3
except Exception:  # pragma: no cover
    Web3 = None  # type: ignore


class BatchFinalizationError(Exception):
    pass


class BatchFinalizationService:
    """Optional finalization adapters for IPFS pinning and on-chain custody anchor."""

    def finalize(
        self,
        *,
        shipment_id: str,
        epoch: int,
        batch_hash: str,
        payload_json: str,
    ) -> Dict[str, Optional[str]]:
        ipfs_cid: Optional[str] = None
        tx_hash: Optional[str] = None

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
            tx_hash = self._anchor_on_chain(shipment_id=shipment_id, ipfs_cid=ipfs_cid)

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

    def _anchor_on_chain(self, *, shipment_id: str, ipfs_cid: str) -> str:
        if Web3 is None:
            raise BatchFinalizationError("web3 is not installed, but CHAIN_ANCHOR_ENABLED=true.")

        if not settings.CHAIN_RPC_URL:
            raise BatchFinalizationError("CHAIN_RPC_URL is missing.")
        if not settings.CHAIN_PRIVATE_KEY:
            raise BatchFinalizationError("CHAIN_PRIVATE_KEY is missing.")
        if not settings.CHAIN_CONTRACT_ADDRESS:
            raise BatchFinalizationError("CHAIN_CONTRACT_ADDRESS is missing.")
        if not settings.CHAIN_CONTRACT_ABI_JSON:
            raise BatchFinalizationError("CHAIN_CONTRACT_ABI_JSON is missing.")

        w3 = Web3(Web3.HTTPProvider(settings.CHAIN_RPC_URL))
        if not w3.is_connected():
            raise BatchFinalizationError("Unable to connect to chain RPC.")

        abi = json.loads(settings.CHAIN_CONTRACT_ABI_JSON)
        contract = w3.eth.contract(
            address=w3.to_checksum_address(settings.CHAIN_CONTRACT_ADDRESS),
            abi=abi,
        )
        account = w3.eth.account.from_key(settings.CHAIN_PRIVATE_KEY)
        nonce = w3.eth.get_transaction_count(account.address)

        shipment_arg = shipment_id
        try:
            shipment_arg = w3.to_bytes(hexstr=shipment_id)
        except Exception:
            # Keep plain string if shipment_id is not hex-compatible for bytes32.
            shipment_arg = shipment_id

        tx = contract.functions.transferCustody(
            shipment_arg,
            settings.CHAIN_PREVIOUS_CUSTODIAN,
            ipfs_cid,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "chainId": settings.CHAIN_CHAIN_ID,
                "gas": 400000,
                "gasPrice": w3.eth.gas_price,
            }
        )

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise BatchFinalizationError("Chain transaction reverted.")
        return tx_hash.hex()


batch_finalization_service = BatchFinalizationService()

