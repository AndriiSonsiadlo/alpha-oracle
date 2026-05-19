"""Circle / Arc integration — wallet management and USDC settlement."""

from __future__ import annotations
import json
import logging
import uuid
from typing import Optional

import httpx

from app.config import get_settings
from circle.web3 import utils, developer_controlled_wallets

logger = logging.getLogger(__name__)

CIRCLE_API_BASE = "https://api.circle.com/v1/w3s"


class CircleClient:
    """Thin async wrapper around Circle's Web3 Services API."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.circle_api_key
        self._enabled = bool(self.api_key and self.api_key != "")
        self._entity_secret = settings.circle_entity_secret
        self._client = None
        if self._enabled:
            self._client = utils.init_developer_controlled_wallets_client(
                api_key=self.api_key,
                entity_secret=self._entity_secret,
            )
            logger.info("CircleClient initialized")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_usdc_amount(self, balance_info: Optional[dict]) -> float:
        if not balance_info:
            return 0.0
        for b in balance_info.get("balances", []):
            token = b.get("token", {})
            symbol = token.get("symbol", "") if isinstance(token, dict) else str(token)
            if "USDC" in symbol.upper():
                try:
                    return float(b.get("amount", 0))
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    async def create_wallet_set(self, name: str = "AlphaOracle Agent") -> Optional[dict]:
        if not self._enabled:
            return {"id": f"mock-ws-{uuid.uuid4().hex[:8]}", "name": name}
        try:
            wallet_sets_api = developer_controlled_wallets.WalletSetsApi(self._client)
            wallet_set = wallet_sets_api.create_wallet_set(
                developer_controlled_wallets.CreateWalletSetRequest.from_dict({"name": name})
            )
            return json.loads(wallet_set.model_dump_json())["data"]["wallet_set"]
        except Exception as exc:
            logger.error("Failed to create wallet set: %s", exc)
            return None

    async def create_wallet(
        self, wallet_set_id: str, blockchain: str = "ARC-TESTNET", count: int = 1,
    ) -> Optional[list[dict]]:
        if not self._enabled:
            return [{"id": f"mock-wallet-{uuid.uuid4().hex[:8]}",
                     "address": f"0x{uuid.uuid4().hex[:40]}",
                     "blockchain": blockchain, "state": "LIVE"}]
        try:
            wallets_api = developer_controlled_wallets.WalletsApi(self._client)
            wallet = wallets_api.create_wallet(
                developer_controlled_wallets.CreateWalletRequest.from_dict({
                    "walletSetId": wallet_set_id,
                    "blockchains": ["ARC-TESTNET"],
                    "count": count,
                    "accountType": "EOA",
                })
            )
            d = json.loads(wallet.model_dump_json())["data"]["wallets"]
            logger.info("Created %d wallet(s)", len(d))
            return d
        except Exception as exc:
            logger.error("Failed to create wallet: %s", exc)
            return None

    async def get_wallet_balance(self, wallet_id: str) -> Optional[dict]:
        if not self._enabled:
            return {"wallet_id": wallet_id, "balances": [], "mock": True}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{CIRCLE_API_BASE}/wallets/{wallet_id}/balances",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "wallet_id": wallet_id,
                    "balances": data.get("data", {}).get("tokenBalances", []),
                }
        except Exception as exc:
            logger.error("Failed to get balance for %s: %s", wallet_id, exc)
            return None


    async def get_wallet_info(self, wallet_id: str) -> Optional[dict]:
        """Get wallet details (address, state, blockchain) for a given wallet ID."""
        if not self._enabled:
            return None
        try:
            wallets_api = developer_controlled_wallets.WalletsApi(self._client)
            response = wallets_api.get_wallet(id=wallet_id)
            data = json.loads(response.model_dump_json())
            return data.get("data", {}).get("wallet")
        except Exception as exc:
            logger.error("Failed to get wallet info %s: %s", wallet_id, exc)
            return None

    async def transfer_usdc(
        self,
        from_wallet_id: str,
        to_address: str,
        amount: str,
        blockchain: str = "ARC-TESTNET",
    ) -> Optional[dict]:
        """Transfer USDC from agent wallet to a destination address."""
        if not self._enabled:
            tx_hash = f"0x{uuid.uuid4().hex}"
            logger.info("Mock USDC transfer: %s USDC → %s (tx: %s)", amount, to_address, tx_hash)
            return {"id": str(uuid.uuid4()), "state": "COMPLETE", "txHash": tx_hash, "amount": amount}

        import time
        try:
            transactions_api = developer_controlled_wallets.TransactionsApi(self._client)
            ARC_TESTNET_USDC = "0x3600000000000000000000000000000000000000"
            request = developer_controlled_wallets.CreateTransferTransactionForDeveloperRequest.from_dict({
                "walletId": from_wallet_id,
                "blockchain": blockchain,
                "destinationAddress": to_address,
                "tokenAddress": ARC_TESTNET_USDC,
                "amounts": [amount],
                "feeLevel": "MEDIUM",
            })
            transfer_response = transactions_api.create_developer_transaction_transfer(request)
            transfer_data = transfer_response.data.to_dict()
            transaction_id = transfer_data["id"]
            current_state = transfer_data["state"]
            terminal_states = {"COMPLETE", "FAILED", "CANCELLED", "DENIED"}
            while current_state not in terminal_states:
                time.sleep(3)
                poll_response = transactions_api.get_transaction(id=transaction_id)
                current_state = poll_response.data.to_dict()["transaction"]["state"]
            if current_state != "COMPLETE":
                raise RuntimeError(f"Transaction ended in state: {current_state}")
            return transfer_data
        except Exception as exc:
            logger.error("Transfer failed: %s", exc)
            return None

    def _usdc_token_id(self, blockchain: str) -> str:
        token_map = {
            "ARC-TESTNET": "arc-testnet-usdc-token-id",
            "ETH-SEPOLIA": "36b6931a-873a-56a8-8a27-b706b17104ee",
        }
        return token_map.get(blockchain, "arc-testnet-usdc-token-id")


_circle_client: Optional[CircleClient] = None


def get_circle_client() -> CircleClient:
    global _circle_client
    if _circle_client is None:
        _circle_client = CircleClient()
    return _circle_client
