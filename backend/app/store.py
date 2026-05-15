from __future__ import annotations

import logging
from typing import Optional

from app.models import (
    AgentDecision,
    Market,
    MarketAnalysis,
)

logger = logging.getLogger(__name__)


class Store:
    """In-memory store for markets and analyses."""

    def __init__(self):
        self._markets: dict[str, Market] = {}
        self._analyses: dict[str, MarketAnalysis] = {}
        self._decisions: list[AgentDecision] = []

    # ------------------------------------------------------------------
    # Markets
    # ------------------------------------------------------------------

    async def save_markets(self, markets: list[Market]) -> None:
        for m in markets:
            self._markets[m.id] = m

    async def get_markets(self, limit: int = 50) -> list[Market]:
        markets = sorted(self._markets.values(), key=lambda m: m.volume, reverse=True)
        return markets[:limit]

    async def get_market(self, market_id: str) -> Optional[Market]:
        return self._markets.get(market_id)

    # ------------------------------------------------------------------
    # Analyses
    # ------------------------------------------------------------------

    async def save_analyses(self, analyses: list[MarketAnalysis]) -> None:
        for a in analyses:
            self._analyses[a.market_id] = a

    async def get_analysis(self, market_id: str) -> Optional[MarketAnalysis]:
        return self._analyses.get(market_id)

    async def get_all_analyses(self) -> list[MarketAnalysis]:
        return list(self._analyses.values())

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    async def save_decisions(self, decisions: list[AgentDecision]) -> None:
        self._decisions.extend(decisions)

    async def get_decisions(self, limit: int = 50) -> list[AgentDecision]:
        return sorted(self._decisions, key=lambda d: d.created_at, reverse=True)[:limit]
