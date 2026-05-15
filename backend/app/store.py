from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models import (
    AgentDecision,
    Market,
    MarketAnalysis,
    Position,
    PortfolioSummary,
)

logger = logging.getLogger(__name__)


class Store:
    """In-memory store for markets, analyses, decisions, and positions."""

    def __init__(self):
        self._markets: dict[str, Market] = {}
        self._analyses: dict[str, MarketAnalysis] = {}
        self._decisions: list[AgentDecision] = []
        self._positions: dict[str, Position] = {}
        self._initial_bankroll: float = 1000.0
        self._cash_balance: float = 1000.0

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
        return sorted(self._decisions, key=lambda d: d.created_at.astimezone(timezone.utc), reverse=True)[:limit]

    async def get_decisions_today(self) -> list[AgentDecision]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        return [d for d in self._decisions if d.created_at.astimezone(timezone.utc) >= cutoff]

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def save_position(self, position: Position) -> None:
        self._positions[position.id] = position

    async def get_position_by_market(self, market_id: str) -> Optional[Position]:
        for p in self._positions.values():
            if p.market_id == market_id and p.status == "open":
                return p
        return None

    async def get_positions(self, status: str = "open") -> list[Position]:
        return [p for p in self._positions.values() if p.status == status]

    async def get_portfolio_summary(self) -> PortfolioSummary:
        open_positions = await self.get_positions("open")
        closed_positions = await self.get_positions("closed")

        positions_value = sum(p.shares * p.current_price for p in open_positions)
        realized_pnl = sum(p.unrealized_pnl for p in closed_positions)
        unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
        total_pnl = realized_pnl + unrealized_pnl

        trade_actions = {"buy_yes", "buy_no", "sell"}
        total_trades = sum(1 for d in self._decisions if d.action.value in trade_actions)
        wins = sum(1 for p in closed_positions if p.unrealized_pnl > 0)
        win_rate = wins / max(len(closed_positions), 1)

        total_value = self._cash_balance + positions_value
        initial = self._initial_bankroll
        pnl_pct = ((total_value - initial) / initial) * 100 if initial else 0

        return PortfolioSummary(
            total_value=round(total_value, 2),
            cash_balance=round(self._cash_balance, 2),
            positions_value=round(positions_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(pnl_pct, 2),
            open_positions=len(open_positions),
            total_trades=total_trades,
            win_rate=round(win_rate, 4),
        )
