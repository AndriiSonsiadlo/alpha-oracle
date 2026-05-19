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


_circle_client: Optional[CircleClient] = None


def get_circle_client() -> CircleClient:
    global _circle_client
    if _circle_client is None:
        _circle_client = CircleClient()
    return _circle_client
