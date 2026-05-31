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
    """Prediction-market trading agent.

    Lifecycle per tick:
        1. Fetch live markets
        2. Analyze with LLM (estimate true probabilities)
        3. Review existing positions → decide SELL or HOLD
        4. Filter for new mispriced opportunities (edge > min_edge)
        5. Size positions with Kelly Criterion
        6. Execute decisions via Circle wallet on Arc testnet
        7. Update positions, cash balance, P&L
        8. Persist everything to Supabase
    """

    def __init__(self, store: Store, config: Optional[StrategyConfig] = None):
        self.store = store
        settings = get_settings()
        self.config = config or StrategyConfig(
            kelly_fraction=settings.kelly_fraction,
        )
        self.bankroll = settings.default_bankroll
        self.wallet_id: Optional[str] = None
        self.wallet_address: Optional[str] = None
        self._circle = None

        self.isAnalysing = False

    def _get_circle(self):
        if self._circle is None:
            from app.circle_client import get_circle_client
            self._circle = get_circle_client()
        return self._circle

    # ------------------------------------------------------------------
    # Wallet management
    # ------------------------------------------------------------------

    def set_wallet(self, wallet_id: str, wallet_address: str = "") -> None:
        """Set the agent's Circle wallet ID (and optionally address)."""
        self.wallet_id = wallet_id
        self.wallet_address = wallet_address
        logger.info("Agent wallet set: %s (%s)", wallet_id, wallet_address or "address unknown")

    async def sync_bankroll_from_wallet(self) -> Optional[float]:
        """Fetch real USDC balance from Circle wallet and sync store bankroll.

        Returns the USDC balance, or None if wallet not set / Circle disabled.
        """
        if not self.wallet_id:
            return None
        cc = self._get_circle()
        balance_info = await cc.get_wallet_balance(self.wallet_id)
        if not balance_info:
            return None
        usdc_balance = cc.get_usdc_amount(balance_info)
        # Always sync, even when balance is $0 — this ensures portfolio
        # reflects the real wallet state, not the $1000 mock default.
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

        # 1. Fetch markets (fall back to cached if API fails)
        settings = get_settings()
        markets = await fetch_markets(limit=settings.llm_markets_limit, active=True)
        if not markets:
            logger.warning("API fetch failed, falling back to cached markets")
            markets = await self.store.get_markets(limit=settings.llm_cache_fallback_limit)
        if not markets:
            logger.warning("No markets available (API + cache empty), skipping tick")
            return []
        logger.info("Working with %d markets", len(markets))

        # Optional category filter (risk param: "categories to follow").
        # Matches case-insensitively as a substring so "politics" hits
        # "US-Politics", etc. Falls back to all markets if nothing matches.
        wanted = {c.strip().lower() for c in self.config.categories if c.strip()}
        if wanted:
            filtered = [
                m for m in markets
                if m.category and any(w in m.category.lower() for w in wanted)
            ]
            if filtered:
                markets = filtered
                logger.info("Category filter %s → %d markets", sorted(wanted), len(markets))
            else:
                logger.info("No markets matched categories %s — analyzing all", sorted(wanted))

        # 2. Analyze with LLM (fall back to cached analyses)
        fresh_analyses: list[MarketAnalysis] = []
        try:
            fresh_analyses = await analyze_markets_batch(
                markets,
                model=self.config.model_name,
                provider=self.config.provider,
            )
        except Exception as exc:
            logger.warning("LLM analysis failed (%s), will use cached analyses", exc)

        # Filter to only keep analyses with real signal (confidence > 0)
        good_fresh = [a for a in fresh_analyses if a.confidence > 0]

        # Merge: prefer fresh good analyses, fall back to cached for the rest
        cached = await self.store.get_all_analyses()
        cached_map = {a.market_id: a for a in cached}
        fresh_map = {a.market_id: a for a in good_fresh}

        analyses: list[MarketAnalysis] = []
        for m in markets:
            if m.id in fresh_map:
                analyses.append(fresh_map[m.id])
            elif m.id in cached_map:
                analyses.append(cached_map[m.id])
            # else: no analysis available, skip this market

        logger.info("Analyses: %d fresh, %d cached, %d total",
                     len(good_fresh), len(analyses) - len(good_fresh), len(analyses))
        analysis_map = {a.market_id: a for a in analyses}
        market_map = {m.id: m for m in markets}

        # 3. Review existing positions → SELL or HOLD
        decisions: list[AgentDecision] = []
        position_decisions = await self._review_positions(market_map, analysis_map)
        decisions.extend(position_decisions)

        # 4. Find new mispriced opportunities → BUY or SKIP
        mispriced = self._find_mispriced(markets, analyses)
        logger.info("Found %d mispriced markets", len(mispriced))

        for mp in mispriced:
            # Skip if we already have a position on this market
            existing = await self.store.get_position_by_market(mp.market.id)
            if existing:
                continue
            decision = await self._make_buy_decision(mp)
            decisions.append(decision)

        # 5. Log any markets we analyzed but skipped
        already_decided = {d.market_id for d in decisions}
        for market in markets:
            if market.id in already_decided:
                continue
            analysis = analysis_map.get(market.id)
            if not analysis:
                continue
            # Log a SKIP decision so the user sees what the agent considered
            skip = AgentDecision(
                market_id=market.id,
                market_question=market.question,
                action=AgentAction.SKIP,
                amount_usdc=0,
                kelly_fraction=0,
                reasoning_trace=self._build_skip_trace(market, analysis),
                ai_probability=analysis.ai_probability,
                market_probability=market.yes_price,
                edge=analysis.edge,
                confidence=analysis.confidence,
                strategy_version_id=await self._active_strategy_id(),
                created_at=datetime.utcnow(),
            )
            decisions.append(skip)

        # 6. Persist (only save good analyses to avoid overwriting with failed ones)
        await self.store.save_markets(markets)
        if good_fresh:
            await self.store.save_analyses(good_fresh)
        await self.store.save_decisions(decisions)

        # Snapshot the real portfolio value for the equity curve.
        await self.store.record_equity_snapshot()

        logger.info("Tick complete — %d decisions (%s)",
                     len(decisions),
                     ", ".join(f"{d.action.value}" for d in decisions))

        self.isAnalysing = False
        return decisions

    async def tick_v1(self) -> list[AgentDecision]:
        """Run one full analysis-and-decide cycle."""
        logger.info("Agent tick started — config: %s", self.config.model_dump_json())

        # 1. Fetch markets
        settings = get_settings()
        markets = await fetch_markets(limit=settings.llm_markets_limit, active=True)
        if not markets:
            logger.warning("No markets fetched, skipping tick")
            return []
        logger.info("Fetched %d markets", len(markets))

        # 2. Analyze with LLM
        analyses = await analyze_markets_batch(
            markets,
            model=self.config.model_name,
            provider=self.config.provider,
        )

        # 3. Find mispriced opportunities
        mispriced = self._find_mispriced(markets, analyses)
        logger.info("Found %d mispriced markets", len(mispriced))

        # 4+5. Decide and record
        decisions: list[AgentDecision] = []
        for mp in mispriced:
            decision = self._make_decision(mp)
            decisions.append(decision)
            logger.info(
                "Decision: %s %s on '%s' (edge=%.2f%%, amount=$%.2f)",
                decision.action.value,
                mp.market.id,
                mp.market.question[:60],
                decision.edge * 100,
                decision.amount_usdc,
            )

        # 6. Persist
        await self.store.save_markets(markets)
        await self.store.save_analyses(analyses)
        await self.store.save_decisions(decisions)

        return decisions


    # ------------------------------------------------------------------
    # Position review — SELL / HOLD
    # ------------------------------------------------------------------

    async def _review_positions(
        self,
        market_map: dict[str, Market],
        analysis_map: dict[str, MarketAnalysis],
    ) -> list[AgentDecision]:
        """Review open positions and decide SELL or HOLD for each."""
        open_positions = await self.store.get_positions("open")
        decisions: list[AgentDecision] = []

        for pos in open_positions:
            market = market_map.get(pos.market_id)
            analysis = analysis_map.get(pos.market_id)

            if not market or not analysis:
                # Market no longer in feed — hold
                decisions.append(self._hold_decision(pos, "Market not in current feed"))
                continue

            # Update current price on the position
            current_price = market.yes_price if pos.side == "yes" else (1 - market.yes_price)
            pos.current_price = current_price
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.shares

            # Sell conditions:
            # 1. Edge has disappeared or reversed
            # 2. AI confidence dropped below threshold
            # 3. We're sitting on a good profit (> 20% of bet)
            edge_for_side = analysis.edge if pos.side == "yes" else -analysis.edge
            profit_pct = pos.unrealized_pnl / max(pos.amount_usdc, 0.01)

            should_sell = False
            reason = ""

            if edge_for_side < 0:
                should_sell = True
                reason = f"Edge reversed: AI now favors {'NO' if pos.side == 'yes' else 'YES'} (edge={edge_for_side:+.1%})"
            elif analysis.confidence < self.config.min_confidence * 0.8:
                should_sell = True
                reason = f"Confidence dropped to {analysis.confidence:.0%} (below {self.config.min_confidence * 0.8:.0%} threshold)"
            elif profit_pct > 0.20:
                should_sell = True
                reason = f"Taking profit: {profit_pct:.0%} return on ${pos.amount_usdc:.2f} position"
            elif profit_pct < -0.30:
                should_sell = True
                reason = f"Stop loss: {profit_pct:.0%} loss on ${pos.amount_usdc:.2f} position"

            if should_sell:
                decision = await self._make_sell_decision(pos, market, analysis, reason)
                decisions.append(decision)
            else:
                hold_reason = (
                    f"Edge still favorable ({edge_for_side:+.1%}), "
                    f"confidence {analysis.confidence:.0%}, "
                    f"P&L {profit_pct:+.0%}"
                )
                decisions.append(self._hold_decision(pos, hold_reason))

            # Save updated position
            await self.store.save_position(pos)

        return decisions

    # ------------------------------------------------------------------
    # Decision builders
    # ------------------------------------------------------------------

    async def _make_buy_decision(self, mp: MispricedMarket) -> AgentDecision:
        """Execute a BUY and create the position."""
        action = AgentAction.BUY_YES if mp.suggested_action == AgentAction.BUY_YES else AgentAction.BUY_NO
        side = "yes" if action == AgentAction.BUY_YES else "no"
        entry_price = mp.market.yes_price if side == "yes" else (1 - mp.market.yes_price)
        amount = min(mp.suggested_amount, self.store._cash_balance * 0.95)

        if amount < 0.50:
            return AgentDecision(
                market_id=mp.market.id,
                market_question=mp.market.question,
                action=AgentAction.SKIP,
                reasoning_trace="Insufficient cash for this position",
                ai_probability=mp.analysis.ai_probability,
                market_probability=mp.market.yes_price,
                edge=mp.analysis.edge,
                confidence=mp.analysis.confidence,
                strategy_version_id=await self._active_strategy_id(),
                created_at=datetime.utcnow(),
            )

        # Execute Circle transfer
        tx_hash = await self._execute_trade(amount, side, mp.market.id)

        # Create position
        shares = amount / entry_price if entry_price > 0 else 0
        position = Position(
            market_id=mp.market.id,
            market_question=mp.market.question,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            amount_usdc=amount,
            shares=round(shares, 4),
            unrealized_pnl=0,
            status="open",
            opened_at=datetime.utcnow(),
        )
        await self.store.save_position(position)

        # Deduct cash
        self.store._cash_balance -= amount
        logger.info("Opened %s position on '%s': $%.2f at %.4f (%d shares)",
                     side, mp.market.question[:40], amount, entry_price, shares)

        return AgentDecision(
            market_id=mp.market.id,
            market_question=mp.market.question,
            action=action,
            amount_usdc=round(amount, 2),
            kelly_fraction=mp.kelly_bet_fraction,
            reasoning_trace=self._build_buy_trace(mp),
            ai_probability=mp.analysis.ai_probability,
            market_probability=mp.market.yes_price,
            edge=mp.analysis.edge,
            confidence=mp.analysis.confidence,
            strategy_version_id=await self._active_strategy_id(),
            tx_hash=tx_hash,
            created_at=datetime.utcnow(),
        )

    async def _make_sell_decision(
        self, pos: Position, market: Market, analysis: MarketAnalysis, reason: str
    ) -> AgentDecision:
        """Execute a SELL and close the position."""
        current_price = pos.current_price
        proceeds = pos.shares * current_price
        pnl = proceeds - pos.amount_usdc

        # Execute Circle transfer (receive USDC back)
        tx_hash = await self._execute_trade(proceeds, f"sell_{pos.side}", pos.market_id)

        # Close position
        pos.status = "closed"
        pos.closed_at = datetime.utcnow()
        pos.unrealized_pnl = pnl
        await self.store.save_position(pos)

        # Add proceeds back to cash
        self.store._cash_balance += proceeds
        logger.info("Closed %s position on '%s': proceeds=$%.2f, P&L=$%.2f",
                     pos.side, pos.market_question[:40], proceeds, pnl)

        return AgentDecision(
            market_id=pos.market_id,
            market_question=pos.market_question,
            action=AgentAction.SELL,
            amount_usdc=round(proceeds, 2),
            kelly_fraction=0,
            reasoning_trace=self._build_sell_trace(pos, market, analysis, reason, pnl),
            ai_probability=analysis.ai_probability,
            market_probability=market.yes_price,
            edge=analysis.edge,
            confidence=analysis.confidence,
            strategy_version_id=await self._active_strategy_id(),
            tx_hash=tx_hash,
            created_at=datetime.utcnow(),
        )

    def _hold_decision(self, pos: Position, reason: str) -> AgentDecision:
        """Create a HOLD decision (no trade, just logging)."""
        return AgentDecision(
            market_id=pos.market_id,
            market_question=pos.market_question,
            action=AgentAction.HOLD,
            amount_usdc=pos.amount_usdc,
            reasoning_trace=(
                f"## HOLD: '{pos.market_question}'\n\n"
                f"**Position:** {pos.side.upper()} | Entry: ${pos.entry_price:.4f} | "
                f"Current: ${pos.current_price:.4f}\n"
                f"**Shares:** {pos.shares} | Unrealized P&L: ${pos.unrealized_pnl:.2f}\n\n"
                f"**Reason:** {reason}"
            ),
            ai_probability=0,
            market_probability=pos.current_price,
            edge=0,
            confidence=0,
            created_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Circle trade execution
    # ------------------------------------------------------------------

    async def _execute_trade(self, amount: float, side: str, market_id: str) -> Optional[str]:
        """Execute a trade via Circle wallet on Arc testnet.

        Transfers USDC from the agent wallet to the configured arc_market_address.
        This represents buying into a position on Arc testnet.
        For sells, the transfer still goes to arc_market_address (settlement simulation).
        """
        cc = self._get_circle()
        settings = get_settings()

        if not self.wallet_id:
            # Auto-setup wallet on first trade if Circle is enabled
            if cc.enabled:
                ws = await cc.create_wallet_set("AlphaOracle Agent")
                if ws:
                    wallets = await cc.create_wallet(ws["id"])
                    if wallets and len(wallets) > 0:
                        self.wallet_id = wallets[0].get("id", "")
                        self.wallet_address = wallets[0].get("address", "")
                        logger.info("Auto-created agent wallet: %s (%s)",
                                    self.wallet_id, self.wallet_address)
            if not self.wallet_id:
                logger.warning("No wallet — trade recorded without on-chain execution")
                return None

        # Use the configured Arc testnet market address (not a hash-based random address)
        market_address = settings.arc_market_address
        if not market_address or market_address == "0x0000000000000000000000000000000000000001":
            # Fallback: derive a deterministic testnet address from market_id (safe for demo)
            market_address = f"0x{abs(hash(market_id)):040x}"[:42]

        tx = await cc.transfer_usdc(
            from_wallet_id=self.wallet_id,
            to_address=market_address,
            amount=f"{amount:.2f}",
        )
        if tx:
            logger.info("On-chain tx: %s USDC → %s | hash=%s",
                        amount, market_address, tx.get("txHash"))
        return tx.get("txHash") if tx else None

    # ------------------------------------------------------------------
    # Opportunity finding
    # ------------------------------------------------------------------

    def _find_mispriced(
        self, markets: list[Market], analyses: list[MarketAnalysis]
    ) -> list[MispricedMarket]:
        """Filter for markets where AI disagrees with the market price enough."""
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

            # Kelly sizing
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

            results.append(
                MispricedMarket(
                    market=market,
                    analysis=analysis,
                    suggested_action=action,
                    suggested_amount=bet["amount"],
                    kelly_bet_fraction=bet["fraction"],
                )
            )

        # Sort by edge * confidence (best opportunities first)
        results.sort(key=lambda m: abs(m.analysis.edge) * m.analysis.confidence, reverse=True)
        return results

    def _make_decision(self, mp: MispricedMarket) -> AgentDecision:
        """Create a formal agent decision from a mispriced market opportunity."""
        return AgentDecision(
            market_id=mp.market.id,
            market_question=mp.market.question,
            action=mp.suggested_action,
            amount_usdc=mp.suggested_amount,
            kelly_fraction=mp.kelly_bet_fraction,
            reasoning_trace=self._build_buy_trace(mp),
            ai_probability=mp.analysis.ai_probability,
            market_probability=mp.market.yes_price,
            edge=mp.analysis.edge,
            confidence=mp.analysis.confidence,
            created_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Reasoning traces
    # ------------------------------------------------------------------

    def _build_buy_trace(self, mp: MispricedMarket) -> str:
        side = "YES" if mp.suggested_action == AgentAction.BUY_YES else "NO"
        lines = [
            f"## BUY {side}: '{mp.market.question}'",
            "",
            f"**Market price (YES):** ${mp.market.yes_price:.2f} → implies {mp.market.yes_price:.0%} probability",
            f"**AI estimated probability:** {mp.analysis.ai_probability:.0%} (confidence: {mp.analysis.confidence:.0%})",
            f"**Edge:** {mp.analysis.edge:+.1%}",
            f"**Kelly bet fraction:** {mp.kelly_bet_fraction:.2%} of bankroll",
            f"**Bet amount:** ${mp.suggested_amount:.2f} USDC",
            "",
            "### AI Reasoning",
            mp.analysis.reasoning,
            "",
            "### Key News / Data",
            mp.analysis.news_summary,
            "",
            "### Kelly Criterion Calculation",
            f"- Cash available: ${self.store._cash_balance:,.2f}",
            f"- Fractional Kelly multiplier: {self.config.kelly_fraction}",
            f"- Max bet cap: {self.config.max_bet_pct:.0%} of bankroll",
        ]
        return "\n".join(lines)

    def _build_sell_trace(
        self, pos: Position, market: Market, analysis: MarketAnalysis,
        reason: str, pnl: float,
    ) -> str:
        lines = [
            f"## SELL: '{pos.market_question}'",
            "",
            f"**Trigger:** {reason}",
            "",
            f"**Entry:** ${pos.entry_price:.4f} | **Exit:** ${pos.current_price:.4f}",
            f"**Shares:** {pos.shares} | **P&L:** ${pnl:+.2f}",
            "",
            f"**Current AI probability:** {analysis.ai_probability:.0%} (confidence: {analysis.confidence:.0%})",
            f"**Current market price (YES):** ${market.yes_price:.2f}",
            "",
            "### AI Reasoning at sell time",
            analysis.reasoning,
        ]
        return "\n".join(lines)

    def _build_skip_trace(self, market: Market, analysis: MarketAnalysis) -> str:
        reasons = []
        if analysis.confidence < self.config.min_confidence:
            reasons.append(f"Low confidence ({analysis.confidence:.0%} < {self.config.min_confidence:.0%})")
        if abs(analysis.edge) < self.config.min_edge:
            reasons.append(f"Insufficient edge ({analysis.edge:+.1%}, need ±{self.config.min_edge:.0%})")
        if not reasons:
            reasons.append("Kelly sizing returned skip or amount too small")
        return (
            f"## SKIP: '{market.question}'\n\n"
            f"**Market price:** ${market.yes_price:.2f}\n"
            f"**AI probability:** {analysis.ai_probability:.0%}\n"
            f"**Reasons:** {'; '.join(reasons)}"
        )

    async def _active_strategy_id(self) -> Optional[str]:
        try:
            sv = await self.store.get_active_strategy()
            return sv.id
        except Exception:
            return None

    def update_config(self, config: StrategyConfig) -> None:
        """Hot-update the agent's strategy configuration."""
        self.config = config
        logger.info("Agent config updated: %s", config.model_dump_json())
