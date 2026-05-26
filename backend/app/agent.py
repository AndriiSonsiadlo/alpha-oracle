"""Core agent — the autonomous decision loop that analyzes markets and acts."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.analysis_engine import analyze_markets_batch
from app.config import get_settings
from app.kelly import kelly_bet
from app.market_fetcher import fetch_markets
from app.models import (
    AgentAction,
    AgentDecision,
    Market,
    MarketAnalysis,
    MispricedMarket,
    Position,
    StrategyConfig,
)
from app.store import Store

logger = logging.getLogger(__name__)


class Agent:
    """Prediction-market trading agent."""

    def __init__(self, store: Store, config: Optional[StrategyConfig] = None):
        self.store = store
        settings = get_settings()
        self.config = config or StrategyConfig(kelly_fraction=settings.kelly_fraction)
        self.bankroll = settings.default_bankroll
        self.wallet_id = None
        self.wallet_address = None
        self._circle = None
        self.isAnalysing = False


    def _get_circle(self):
        if self._circle is None:
            from app.circle_client import get_circle_client
            self._circle = get_circle_client()
        return self._circle

    def set_wallet(self, wallet_id: str, wallet_address: str = "") -> None:
        self.wallet_id = wallet_id
        self.wallet_address = wallet_address
        logger.info("Agent wallet set: %s (%s)", wallet_id, wallet_address or "address unknown")

    async def sync_bankroll_from_wallet(self) -> Optional[float]:
        if not self.wallet_id:
            return None
        cc = self._get_circle()
        balance_info = await cc.get_wallet_balance(self.wallet_id)
        if not balance_info:
            return None
        usdc_balance = cc.get_usdc_amount(balance_info)
        self.store._cash_balance = usdc_balance
        logger.info("Synced bankroll from wallet %s: $%.2f USDC", self.wallet_id, usdc_balance)
        return usdc_balance

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def tick(self) -> list[AgentDecision]:
        """Run one full analysis-and-decide cycle."""
        if self.isAnalysing:
            return []
        self.isAnalysing = True
        logger.info("Agent tick started — config: %s", self.config.model_dump_json())

        # 1. Fetch markets
        markets = await fetch_markets(limit=10, active=True)
        if not markets:
            logger.warning("API fetch failed, falling back to cached markets")
            markets = await self.store.get_markets(limit=20)
        if not markets:
            logger.warning("No markets available, skipping tick")
            self.isAnalysing = False
            return []
        logger.info("Working with %d markets", len(markets))

        # Volume filter
        if self.config.min_volume > 0:
            markets = [m for m in markets if m.volume >= self.config.min_volume]
            if not markets:
                logger.warning("All markets filtered by min_volume, skipping tick")
                self.isAnalysing = False
                return []

        # Category filter
        wanted = {c.strip().lower() for c in self.config.categories if c.strip()}
        if wanted:
            filtered = [
                m for m in markets
                if m.category and any(w in m.category.lower() for w in wanted)
            ]
            if filtered:
                markets = filtered

        # 2. Analyze with LLM
        fresh_analyses: list[MarketAnalysis] = []
        try:
            fresh_analyses = await analyze_markets_batch(
                markets, model=self.config.model_name, provider=self.config.provider,
                max_concurrent=1,
            )
        except Exception as exc:
            logger.warning("LLM analysis failed (%s), using cached analyses", exc)

        good_fresh = [a for a in fresh_analyses if a.confidence > 0]
        cached = await self.store.get_all_analyses()
        cached_map = {a.market_id: a for a in cached}
        fresh_map = {a.market_id: a for a in good_fresh}

        analyses: list[MarketAnalysis] = []
        for m in markets:
            if m.market_id in fresh_map:
                analyses.append(fresh_map[m.id])
            elif m.id in cached_map:
                analyses.append(cached_map[m.id])

        analysis_map = {a.market_id: a for a in analyses}

        # 3. Review existing positions
        market_map = {m.id: m for m in markets}
        position_decisions = await self._review_positions(market_map, analysis_map)
        decisions.extend(position_decisions)

        # 4. Find new mispriced opportunities
        mispriced = self._find_mispriced(markets, analyses)
        decisions: list[AgentDecision] = []
        for mp in mispriced:
            existing = await self.store.get_position_by_market(mp.market.id)
            if existing:
                continue
            decision = await self._make_buy_decision(mp)
            decisions.append(decision)

        # 4. Save
        await self.store.save_markets(markets)
        if good_fresh:
            await self.store.save_analyses(good_fresh)
        await self.store.save_decisions(decisions)

        await self.store.record_equity_snapshot()
        self.isAnalysing = False
        return decisions

    # ------------------------------------------------------------------
    # Decision builders
    # ------------------------------------------------------------------

    async def _make_buy_decision(self, mp: MispricedMarket) -> AgentDecision:
        action = AgentAction.BUY_YES if mp.suggested_action == AgentAction.BUY_YES else AgentAction.BUY_NO
        side = "yes" if action == AgentAction.BUY_YES else "no"
        entry_price = mp.market.yes_price if side == "yes" else (1 - mp.market.yes_price)
        amount = min(mp.suggested_amount, self.store._cash_balance * 0.95)

        if amount < 0.50:
            return AgentDecision(
                market_id=mp.market.id, market_question=mp.market.question,
                action=AgentAction.SKIP, reasoning_trace="Insufficient cash",
                ai_probability=mp.analysis.ai_probability,
                market_probability=mp.market.yes_price,
                edge=mp.analysis.edge, confidence=mp.analysis.confidence,
                created_at=datetime.utcnow(),
            )

        shares = amount / entry_price if entry_price > 0 else 0
        position = Position(
            market_id=mp.market.id, market_question=mp.market.question,
            side=side, entry_price=entry_price, current_price=entry_price,
            amount_usdc=amount, shares=round(shares, 4),
            unrealized_pnl=0, status="open", opened_at=datetime.utcnow(),
        )
        await self.store.save_position(position)
        self.store._cash_balance -= amount

        return AgentDecision(
            market_id=mp.market.id, market_question=mp.market.question,
            action=action, amount_usdc=round(amount, 2),
            kelly_fraction=mp.kelly_bet_fraction,
            reasoning_trace=self._build_buy_trace(mp),
            ai_probability=mp.analysis.ai_probability,
            market_probability=mp.market.yes_price,
            edge=mp.analysis.edge, confidence=mp.analysis.confidence,
            created_at=datetime.utcnow(),
        )


    # ------------------------------------------------------------------
    # Position review — SELL / HOLD
    # ------------------------------------------------------------------

    async def _review_positions(
        self,
        market_map: dict,
        analysis_map: dict,
    ) -> list[AgentDecision]:
        open_positions = await self.store.get_positions("open")
        decisions: list[AgentDecision] = []
        for pos in open_positions:
            market = market_map.get(pos.market_id)
            analysis = analysis_map.get(pos.market_id)
            if not market or not analysis:
                decisions.append(self._hold_decision(pos, "Market not in current feed"))
                continue

            current_price = market.yes_price if pos.side == "yes" else (1 - market.yes_price)
            pos.current_price = current_price
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.shares

            edge_for_side = analysis.edge if pos.side == "yes" else -analysis.edge
            profit_pct = pos.unrealized_pnl / max(pos.amount_usdc, 0.01)

            should_sell = False
            reason = ""
            if edge_for_side < 0:
                should_sell = True
                reason = f"Edge reversed (edge={edge_for_side:+.1%})"
            elif analysis.confidence < self.config.min_confidence * 0.8:
                should_sell = True
                reason = f"Confidence dropped to {analysis.confidence:.0%}"
            elif profit_pct > 0.20:
                should_sell = True
                reason = f"Taking profit: {profit_pct:.0%} return"
            elif profit_pct < -0.30:
                should_sell = True
                reason = f"Stop loss: {profit_pct:.0%} loss"

            if should_sell:
                decision = await self._make_sell_decision(pos, market, analysis, reason)
                decisions.append(decision)
            else:
                hold_reason = (
                    f"Edge still favorable ({edge_for_side:+.1%}), "
                    f"confidence {analysis.confidence:.0%}, P&L {profit_pct:+.0%}"
                )
                decisions.append(self._hold_decision(pos, hold_reason))

            await self.store.save_position(pos)
        return decisions

    async def _make_sell_decision(self, pos, market, analysis, reason: str) -> AgentDecision:
        current_price = pos.current_price
        proceeds = pos.shares * current_price
        pnl = proceeds - pos.amount_usdc
        pos.status = "closed"
        pos.closed_at = datetime.utcnow()
        pos.unrealized_pnl = pnl
        await self.store.save_position(pos)
        self.store._cash_balance += proceeds
        return AgentDecision(
            market_id=pos.market_id, market_question=pos.market_question,
            action=AgentAction.SELL, amount_usdc=round(proceeds, 2),
            reasoning_trace=(
                f"## SELL: '{pos.market_question}'\n\n"
                f"**Trigger:** {reason}\n"
                f"**Entry:** ${pos.entry_price:.4f} | **Exit:** ${current_price:.4f}\n"
                f"**P&L:** ${pnl:+.2f}"
            ),
            ai_probability=analysis.ai_probability,
            market_probability=market.yes_price,
            edge=analysis.edge, confidence=analysis.confidence,
            created_at=datetime.utcnow(),
        )

    def _hold_decision(self, pos, reason: str) -> AgentDecision:
        return AgentDecision(
            market_id=pos.market_id, market_question=pos.market_question,
            action=AgentAction.HOLD, amount_usdc=pos.amount_usdc,
            reasoning_trace=(
                f"## HOLD: '{pos.market_question}'\n\n"
                f"**Position:** {pos.side.upper()} | Entry: ${pos.entry_price:.4f}\n"
                f"**Reason:** {reason}"
            ),
            ai_probability=0, market_probability=pos.current_price,
            edge=0, confidence=0, created_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Opportunity finding
    # ------------------------------------------------------------------

    def _find_mispriced(self, markets: list[Market], analyses: list[MarketAnalysis]) -> list[MispricedMarket]:
        analysis_map = {a.market_id: a for a in analyses}
        results: list[MispricedMarket] = []
        for market in markets:
            analysis = analysis_map.get(market.id)
            if not analysis:
                continue
            if analysis.confidence < self.config.min_confidence:
                continue
            if abs(analysis.edge) < self.config.min_edge:
                continue
            bet = kelly_bet(
                ai_probability=analysis.ai_probability,
                market_price=market.yes_price,
                bankroll=self.store._cash_balance,
                kelly_fraction=self.config.kelly_fraction,
                max_bet_pct=self.config.max_bet_pct,
            )
            if bet["side"] == "skip" or bet["amount"] < 0.50:
                continue
            action = AgentAction.BUY_YES if bet["side"] == "yes" else AgentAction.BUY_NO
            results.append(MispricedMarket(
                market=market, analysis=analysis,
                suggested_action=action, suggested_amount=bet["amount"],
                kelly_bet_fraction=bet["fraction"],
            ))
        results.sort(key=lambda m: abs(m.analysis.edge) * m.analysis.confidence, reverse=True)
        return results

    def _build_buy_trace(self, mp: MispricedMarket) -> str:
        side = "YES" if mp.suggested_action == AgentAction.BUY_YES else "NO"
        return (
            f"## BUY {side}: '{mp.market.question}'\n\n"
            f"**Market price (YES):** ${mp.market.yes_price:.2f}\n"
            f"**AI probability:** {mp.analysis.ai_probability:.0%} "
            f"(confidence: {mp.analysis.confidence:.0%})\n"
            f"**Edge:** {mp.analysis.edge:+.1%}\n"
            f"**Bet:** ${mp.suggested_amount:.2f} USDC "
            f"({mp.kelly_bet_fraction:.2%} of bankroll)\n\n"
            f"### Reasoning\n{mp.analysis.reasoning}"
        )

    def update_config(self, config: StrategyConfig) -> None:
        self.config = config
        logger.info("Agent config updated: %s", config.model_dump_json())
