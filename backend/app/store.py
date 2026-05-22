from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models import (
    AgentDecision,
    EquityPoint,
    Market,
    MarketAnalysis,
    Position,
    PortfolioSummary,
    StrategyConfig,
    StrategyDiff,
    StrategyVersion,
    StrategyVersionStatus,
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
        self._equity_curve: list[EquityPoint] = []
        self.reset_equity_curve()

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


# Add missing imports at top handled below via python


    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    async def record_equity_snapshot(self) -> EquityPoint:
        summary = await self.get_portfolio_summary()
        point = EquityPoint(
            timestamp=datetime.now(timezone.utc),
            total_value=summary.total_value,
            cash_balance=summary.cash_balance,
            positions_value=summary.positions_value,
            total_pnl=summary.total_pnl,
        )
        self._equity_curve.append(point)
        if len(self._equity_curve) > 500:
            self._equity_curve = self._equity_curve[-500:]
        return point

    def reset_equity_curve(self) -> None:
        self._equity_curve = [
            EquityPoint(
                timestamp=datetime.now(timezone.utc),
                total_value=round(self._cash_balance, 2),
                cash_balance=round(self._cash_balance, 2),
                positions_value=0.0,
                total_pnl=0.0,
            )
        ]

    async def get_equity_curve(self, limit: int = 500) -> list[EquityPoint]:
        return self._equity_curve[-limit:]

    # ------------------------------------------------------------------
    # Strategy versioning ("git for agents")
    # ------------------------------------------------------------------

    def __init_strategies(self):
        if not hasattr(self, '_strategy_versions'):
            self._strategy_versions: list[StrategyVersion] = []
            default = StrategyVersion(
                version_label="v1.0",
                config=StrategyConfig(),
                status=StrategyVersionStatus.ACTIVE,
                description="Initial default strategy",
            )
            self._strategy_versions.append(default)

    async def get_active_strategy(self) -> StrategyVersion:
        self.__init_strategies()
        for sv in reversed(self._strategy_versions):
            if sv.status == StrategyVersionStatus.ACTIVE:
                return sv
        return self._strategy_versions[-1]

    async def get_strategy_versions(self) -> list[StrategyVersion]:
        self.__init_strategies()
        return list(self._strategy_versions)

    async def get_strategy_version(self, version_id: str) -> Optional[StrategyVersion]:
        self.__init_strategies()
        for sv in self._strategy_versions:
            if sv.id == version_id:
                return sv
        return None

    async def create_strategy_version(
        self,
        config: StrategyConfig,
        description: str = "",
        parent_id: Optional[str] = None,
        label: Optional[str] = None,
    ) -> StrategyVersion:
        self.__init_strategies()
        for sv in self._strategy_versions:
            if sv.status == StrategyVersionStatus.ACTIVE:
                sv.status = StrategyVersionStatus.ARCHIVED

        version_num = len(self._strategy_versions) + 1
        new_version = StrategyVersion(
            version_label=label or f"v{version_num}.0",
            parent_id=parent_id or (self._strategy_versions[-1].id if self._strategy_versions else None),
            config=config,
            status=StrategyVersionStatus.ACTIVE,
            description=description,
        )
        self._strategy_versions.append(new_version)
        return new_version

    async def rollback_strategy(self, version_id: str) -> Optional[StrategyVersion]:
        self.__init_strategies()
        target = await self.get_strategy_version(version_id)
        if not target:
            return None
        for sv in self._strategy_versions:
            if sv.status == StrategyVersionStatus.ACTIVE:
                sv.status = StrategyVersionStatus.ARCHIVED
        rolled_back = StrategyVersion(
            version_label=f"{target.version_label}-rollback",
            parent_id=target.id,
            config=target.config.model_copy(),
            status=StrategyVersionStatus.ACTIVE,
            description=f"Rolled back to {target.version_label}",
        )
        self._strategy_versions.append(rolled_back)
        return rolled_back

    async def diff_strategies(self, version_a_id: str, version_b_id: str) -> StrategyDiff:
        a = await self.get_strategy_version(version_a_id)
        b = await self.get_strategy_version(version_b_id)
        changes: list[dict] = []
        if a and b:
            a_dict = a.config.model_dump()
            b_dict = b.config.model_dump()
            for key in set(list(a_dict.keys()) + list(b_dict.keys())):
                val_a = a_dict.get(key)
                val_b = b_dict.get(key)
                if val_a != val_b:
                    changes.append({"field": key, "old": val_a, "new": val_b})
        return StrategyDiff(version_a_id=version_a_id, version_b_id=version_b_id, changes=changes)
