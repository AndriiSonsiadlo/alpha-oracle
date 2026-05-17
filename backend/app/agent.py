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
        self.isAnalysing = False

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

        # 3. Find new mispriced opportunities
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
