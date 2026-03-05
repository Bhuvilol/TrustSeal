from __future__ import annotations

from types import SimpleNamespace

import app.services.batch_finalization_service as bfs_module
from app.core.config import settings
from app.services.batch_finalization_service import batch_finalization_service


class _FakeTxHash:
    def __init__(self, value: str) -> None:
        self._value = value

    def hex(self) -> str:
        return self._value


class _FakeReceipt:
    status = 1


class _FakeAccountObj:
    address = "0xabc"

    def sign_transaction(self, tx: dict):
        return SimpleNamespace(raw_transaction=b"raw", tx=tx)


class _FakeAccountModule:
    def from_key(self, _key: str) -> _FakeAccountObj:
        return _FakeAccountObj()


class _FakeContractFunctions:
    def transferCustody(self, *_args, **_kwargs):
        return self

    def build_transaction(self, tx: dict):
        return tx


class _FakeContract:
    functions = _FakeContractFunctions()


class _FakeEth:
    def __init__(self, scenario: list[str]) -> None:
        self._scenario = scenario
        self._send_idx = 0
        self.gas_price = 100
        self.account = _FakeAccountModule()
        self.nonce_calls = 0

    def get_transaction_count(self, _address: str, _tag: str = "pending") -> int:
        self.nonce_calls += 1
        return 7

    def contract(self, address: str, abi: list[dict]):  # noqa: ARG002
        return _FakeContract()

    def send_raw_transaction(self, _raw: bytes):
        token = self._scenario[self._send_idx]
        self._send_idx += 1
        if token == "nonce_low":
            raise Exception("nonce too low")
        if token == "underpriced":
            raise Exception("replacement transaction underpriced")
        return _FakeTxHash("0xtesthash")

    def wait_for_transaction_receipt(self, _tx_hash, timeout: int):  # noqa: ARG002
        return _FakeReceipt()


class _FakeWeb3:
    scenario: list[str] = ["ok"]

    class HTTPProvider:
        def __init__(self, _url: str) -> None:
            pass

    def __init__(self, _provider) -> None:
        self.eth = _FakeEth(list(self.__class__.scenario))

    def is_connected(self) -> bool:
        return True

    def to_checksum_address(self, value: str) -> str:
        return value


def test_chain_error_classification() -> None:
    assert batch_finalization_service._is_retryable_chain_error("nonce too low") is True
    assert batch_finalization_service._is_retryable_chain_error("replacement transaction underpriced") is True
    assert batch_finalization_service._is_retryable_chain_error("fatal execution reverted") is False


def test_anchor_on_chain_retries_and_refreshes_nonce(monkeypatch) -> None:
    old_web3 = bfs_module.Web3
    old_attempts = settings.CHAIN_ANCHOR_MAX_ATTEMPTS
    old_delay_base = settings.CHAIN_ANCHOR_RETRY_BASE_DELAY_MS
    old_delay_max = settings.CHAIN_ANCHOR_RETRY_MAX_DELAY_MS
    old_timeout = settings.CHAIN_RECEIPT_TIMEOUT_SECONDS
    old_rpc = settings.CHAIN_RPC_URL
    old_priv = settings.CHAIN_PRIVATE_KEY
    old_addr = settings.CHAIN_CONTRACT_ADDRESS
    old_prev = settings.CHAIN_PREVIOUS_CUSTODIAN
    old_chain = settings.CHAIN_CHAIN_ID
    try:
        bfs_module.Web3 = _FakeWeb3
        _FakeWeb3.scenario = ["nonce_low", "ok"]
        settings.CHAIN_ANCHOR_MAX_ATTEMPTS = 3
        settings.CHAIN_ANCHOR_RETRY_BASE_DELAY_MS = 1
        settings.CHAIN_ANCHOR_RETRY_MAX_DELAY_MS = 1
        settings.CHAIN_RECEIPT_TIMEOUT_SECONDS = 1
        settings.CHAIN_RPC_URL = "http://fake-rpc"
        settings.CHAIN_PRIVATE_KEY = "0x" + ("1" * 64)
        settings.CHAIN_CONTRACT_ADDRESS = "0x0000000000000000000000000000000000000001"
        settings.CHAIN_PREVIOUS_CUSTODIAN = "0x0000000000000000000000000000000000000000"
        settings.CHAIN_CHAIN_ID = 80002

        monkeypatch.setattr(batch_finalization_service, "_load_chain_abi", lambda: [])
        monkeypatch.setattr(bfs_module.time, "sleep", lambda _delay: None)

        tx_hash = batch_finalization_service._anchor_on_chain(
            shipment_id="s1",
            bundle_id="b1",
            bundle_hash="h1",
            ipfs_cid="cid1",
        )
        assert tx_hash == "0xtesthash"
    finally:
        bfs_module.Web3 = old_web3
        settings.CHAIN_ANCHOR_MAX_ATTEMPTS = old_attempts
        settings.CHAIN_ANCHOR_RETRY_BASE_DELAY_MS = old_delay_base
        settings.CHAIN_ANCHOR_RETRY_MAX_DELAY_MS = old_delay_max
        settings.CHAIN_RECEIPT_TIMEOUT_SECONDS = old_timeout
        settings.CHAIN_RPC_URL = old_rpc
        settings.CHAIN_PRIVATE_KEY = old_priv
        settings.CHAIN_CONTRACT_ADDRESS = old_addr
        settings.CHAIN_PREVIOUS_CUSTODIAN = old_prev
        settings.CHAIN_CHAIN_ID = old_chain
