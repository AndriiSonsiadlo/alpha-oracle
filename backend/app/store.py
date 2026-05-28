from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models import (
    AgentDecision,
    EquityPoint,
    Market,
    MarketAnalysis,
    PortfolioSummary,
    Position,
    StrategyConfig,
    StrategyDiff,
    StrategyVersion,
    StrategyVersionStatus,
)

logger = logging.getLogger(__name__)


class Store:
    """In-memory store with optional Supabase sync.

    For the hackathon MVP, this works standalone (in-memory).
    When Supabase creds are provided, it persists to the DB.
    """

    def __init__(self, supabase_client=None):
        self.sb = supabase_client
        self._sb_warned = False
        # In-memory state
        self._markets: dict[str, Market] = {}
        self._analyses: dict[str, MarketAnalysis] = {}
        self._decisions: list[AgentDecision] = []
        self._positions: dict[str, Position] = {}
        self._strategy_versions: list[StrategyVersion] = []
        self._initial_bankroll: float = 1000.0
        self._cash_balance: float = 1000.0
        self._equity_curve: list[EquityPoint] = []

        self.load_markets_from_db()
        self.load_analyses_from_db()
        self.load_decisions_from_db()
        self.load_positions_from_db()
        self.load_strategy_versions_from_db()
        self.reset_equity_curve()

    def _sb_error(self, op: str, exc: Exception) -> None:
        """Handle a Supabase failure. On a network/DNS error, disable persistence
        for the rest of the session (in-memory only) and warn exactly once instead
        of spamming a warning on every save."""
        msg = str(exc)
        network = any(
            s in msg
            for s in (
                "Name or service not known",
                "Temporary failure in name resolution",
                "getaddrinfo",
                "Failed to establish",
                "Max retries",
                "Connection",
            )
        )
        if network:
            self.sb = None
            if not self._sb_warned:
                logger.warning(
                    "Supabase unreachable (%s) — disabling DB persistence, "
                    "running in-memory only for this session.",
                    exc,
                )
                self._sb_warned = True
        else:
            logger.warning("Supabase %s failed: %s", op, exc)

    # ------------------------------------------------------------------
    # Markets
    # ------------------------------------------------------------------

    async def save_markets(self, markets: list[Market]) -> None:
        for m in markets:
            self._markets[m.id] = m
        if self.sb:
            try:
                rows = [m.model_dump(mode="json") for m in markets]
                self.sb.table("markets").upsert(rows, on_conflict="id").execute()
            except Exception as exc:
                self._sb_error("save_markets", exc)
    
    def load_markets_from_db(self) -> None:
        if not self.sb:
            return
        try:
            resp = self.sb.table("markets").select("*").execute()
            for row in resp.data:
                self._markets[row["id"]] = Market(**row)
        except Exception as exc:
            self._sb_error("get_markets", exc)

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
        if self.sb:
            try:
                rows = [a.model_dump(mode="json") for a in analyses]
                self.sb.table("analyses").upsert(rows, on_conflict="market_id").execute()
            except Exception as exc:
                self._sb_error("save_analyses", exc)

    def load_analyses_from_db(self) -> None:
        if not self.sb:
            return
        try:
            resp = self.sb.table("analyses").select("*").execute()
            for row in resp.data:
                analysis = MarketAnalysis(**row)
                self._analyses[analysis.market_id] = analysis
        except Exception as exc:
            self._sb_error("load_analyses", exc)

    async def get_analysis(self, market_id: str) -> Optional[MarketAnalysis]:
        return self._analyses.get(market_id)

    async def get_all_analyses(self) -> list[MarketAnalysis]:
        return list(self._analyses.values())

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    async def save_decisions(self, decisions: list[AgentDecision]) -> None:
        self._decisions.extend(decisions)
        if self.sb:
            try:
                rows = [d.model_dump(mode="json") for d in decisions]
                self.sb.table("decisions").insert(rows).execute()
            except Exception as exc:
                self._sb_error("save_decisions", exc)

    def load_decisions_from_db(self) -> None:
        if not self.sb:
            return
        try:
            resp = self.sb.table("decisions").select("*").order("created_at").execute()
            for row in resp.data:
                try:
                    decision = AgentDecision(**row)
                    self._decisions.append(decision)
                except Exception as e:
                    logger.warning("Failed to parse decision row: %s", e)
        except Exception as exc:
            self._sb_error("load_decisions", exc)

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
        if self.sb:
            try:
                self.sb.table("positions").upsert(
                    position.model_dump(mode="json"), on_conflict="id"
                ).execute()
            except Exception as exc:
                self._sb_error("save_position", exc)
    
    def load_positions_from_db(self) -> None:
        if not self.sb:
            return
        try:
            resp = self.sb.table("positions").select("*").execute()
            for row in resp.data:
                try:
                    position = Position(**row)
                    self._positions[position.id] = position
                except Exception as e:
                    logger.warning("Failed to parse position row: %s", e)
        except Exception as exc:
            self._sb_error("load_positions", exc)

    async def get_position_by_market(self, market_id: str) -> Optional[Position]:
        """Get the open position for a given market, if any."""
        for p in self._positions.values():
            if p.market_id == market_id and p.status == "open":
                return p
        return None

    async def get_positions(self, status: str = "open") -> list[Position]:
        return [p for p in self._positions.values() if p.status == status]

    async def get_portfolio_summary(self) -> PortfolioSummary:
        open_positions = await self.get_positions("open")
        closed_positions = await self.get_positions("closed")

        # Open positions valued at current mark-to-market
        positions_value = sum(p.shares * p.current_price for p in open_positions)
        # Total P&L = realized (closed) + unrealized (open)
        realized_pnl = sum(p.unrealized_pnl for p in closed_positions)
        unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
        total_pnl = realized_pnl + unrealized_pnl

        # Count buy/sell trades (not hold/skip)
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

    # ------------------------------------------------------------------
    # Equity curve (real portfolio-value snapshots over time)
    # ------------------------------------------------------------------

    async def record_equity_snapshot(self) -> EquityPoint:
        """Capture the current portfolio value as a point on the equity curve.
        Called every agent tick and whenever the bankroll changes (reset/connect/
        sync) so the chart plots real history instead of interpolation."""
        summary = await self.get_portfolio_summary()
        point = EquityPoint(
            timestamp=datetime.now(timezone.utc),
            total_value=summary.total_value,
            cash_balance=summary.cash_balance,
            positions_value=summary.positions_value,
            total_pnl=summary.total_pnl,
        )
        self._equity_curve.append(point)
        # Keep memory bounded — last 500 snapshots is plenty for the chart.
        if len(self._equity_curve) > 500:
            self._equity_curve = self._equity_curve[-500:]
        return point

    def reset_equity_curve(self) -> None:
        """Clear the curve and seed a single baseline point at the current bankroll."""
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

    def _default_strategy(self) -> StrategyVersion:
        return StrategyVersion(
            version_label="v1.0",
            config=StrategyConfig(),
            status=StrategyVersionStatus.ACTIVE,
            description="Initial default strategy",
        )

    async def get_active_strategy(self) -> StrategyVersion:
        for sv in reversed(self._strategy_versions):
            if sv.status == StrategyVersionStatus.ACTIVE:
                return sv
        if self._strategy_versions:
            return self._strategy_versions[-1]
        # Fallback — shouldn't normally reach here
        default = self._default_strategy()
        self._strategy_versions.append(default)
        return default

    async def get_strategy_versions(self) -> list[StrategyVersion]:
        return list(self._strategy_versions)

    async def get_strategy_version(self, version_id: str) -> Optional[StrategyVersion]:
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
        """Create a new strategy version (like a git commit)."""
        # Deactivate current active
        for sv in self._strategy_versions:
            if sv.status == StrategyVersionStatus.ACTIVE:
                sv.status = StrategyVersionStatus.ARCHIVED
                # Snapshot performance at switch time
                portfolio = await self.get_portfolio_summary()
                sv.performance_snapshot = portfolio.model_dump()
                if self.sb:
                    try:
                        self.sb.table("strategy_versions").update(
                            {"status": "archived", "performance_snapshot": sv.performance_snapshot}
                        ).eq("id", sv.id).execute()
                    except Exception as exc:
                        logger.warning("Supabase archive strategy failed: %s", exc)

        version_num = len(self._strategy_versions) + 1
        new_version = StrategyVersion(
            version_label=label or f"v{version_num}.0",
            parent_id=parent_id or (self._strategy_versions[-1].id if self._strategy_versions else None),
            config=config,
            status=StrategyVersionStatus.ACTIVE,
            description=description,
        )
        self._strategy_versions.append(new_version)

        if self.sb:
            try:
                self.sb.table("strategy_versions").insert(
                    new_version.model_dump(mode="json")
                ).execute()
            except Exception as exc:
                logger.warning("Supabase create_strategy_version failed: %s", exc)

        return new_version
    
    def load_strategy_versions_from_db(self) -> None:
        """Load strategy versions from Supabase, replacing any in-memory defaults.

        Fix: previously this appended DB rows to an already-populated list,
        causing duplicates. Now it replaces the list when DB has data.
        """
        if not self.sb:
            # No DB — ensure we have at least the default strategy
            if not self._strategy_versions:
                self._strategy_versions.append(self._default_strategy())
            return
        try:
            resp = (
                self.sb.table("strategy_versions")
                .select("*")
                .order("created_at", desc=False)
                .execute()
            )
            db_versions: list[StrategyVersion] = []
            for row in resp.data:
                try:
                    sv = StrategyVersion(**row)
                    db_versions.append(sv)
                except Exception as e:
                    logger.warning("Skipping malformed strategy_versions row: %s", e)

            if db_versions:
                # Replace in-memory list with DB data (no duplicates)
                self._strategy_versions = db_versions
                logger.info("Loaded %d strategy versions from Supabase", len(db_versions))
            else:
                # DB is empty — seed with default and save it
                if not self._strategy_versions:
                    default = self._default_strategy()
                    self._strategy_versions.append(default)
                    try:
                        self.sb.table("strategy_versions").insert(
                            default.model_dump(mode="json")
                        ).execute()
                        logger.info("Seeded default strategy version to Supabase")
                    except Exception as exc:
                        logger.warning("Could not seed default strategy: %s", exc)

        except Exception as exc:
            self._sb_error("load_strategy_versions", exc)
            if not self._strategy_versions:
                self._strategy_versions.append(self._default_strategy())

    async def rollback_strategy(self, version_id: str) -> Optional[StrategyVersion]:
        """Rollback to a previous strategy version (like git checkout)."""
        target = await self.get_strategy_version(version_id)
        if not target:
            return None

        # Deactivate current
        for sv in self._strategy_versions:
            if sv.status == StrategyVersionStatus.ACTIVE:
                sv.status = StrategyVersionStatus.ARCHIVED
                if self.sb:
                    try:
                        self.sb.table("strategy_versions").update(
                            {"status": "archived"}
                        ).eq("id", sv.id).execute()
                    except Exception:
                        pass

        # Create new version based on target's config
        rolled_back = StrategyVersion(
            version_label=f"{target.version_label}-rollback",
            parent_id=target.id,
            config=target.config.model_copy(),
            status=StrategyVersionStatus.ACTIVE,
            description=f"Rolled back to {target.version_label}",
        )
        self._strategy_versions.append(rolled_back)

        if self.sb:
            try:
                self.sb.table("strategy_versions").insert(
                    rolled_back.model_dump(mode="json")
                ).execute()
            except Exception as exc:
                logger.warning("Supabase rollback save failed: %s", exc)

        return rolled_back

    async def diff_strategies(self, version_a_id: str, version_b_id: str) -> StrategyDiff:
        """Compare two strategy versions (like git diff)."""
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

        return StrategyDiff(
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            changes=changes,
        )
