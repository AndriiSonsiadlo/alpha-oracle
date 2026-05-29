"""AlphaOracle — FastAPI backend serving the agent, markets, and dashboard APIs."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

from app.agent import Agent
from app.config import get_settings
from app.models import (
    AgentDecision,
    DashboardStats,
    EquityPoint,
    Market,
    MarketAnalysis,
    MispricedMarket,
    Position,
    PortfolioSummary,
    StrategyConfig,
    StrategyDiff,
    StrategyVersion,
)
from app.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Globals (initialized in lifespan)
# ---------------------------------------------------------------------------
store: Store
agent: Agent
scheduler: AsyncIOScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, agent, scheduler

    settings = get_settings()

    # Init Supabase client (optional — works without it)
    sb_client = None
    if settings.supabase_url and settings.supabase_key:
        try:
            from supabase import create_client

            sb_client = create_client(settings.supabase_url, settings.supabase_key)
            logger.info("Supabase connected")
        except Exception as exc:
            logger.warning("Supabase unavailable, using in-memory store: %s", exc)

    store = Store(supabase_client=sb_client)

    # Load active strategy from DB and initialize agent with it
    active_strategy = None
    try:
        active_strategy = await store.get_active_strategy()
        logger.info("Loaded active strategy: %s (%s)", active_strategy.version_label, active_strategy.config.model_name)
    except Exception:
        pass
    agent = Agent(store=store, config=active_strategy.config if active_strategy else None)

    # Restore wallet from env if configured (persists across restarts)
    if settings.agent_wallet_id:
        from app.circle_client import get_circle_client
        cc = get_circle_client()
        wallet_info = await cc.get_wallet_info(settings.agent_wallet_id)
        address = wallet_info.get("address", "") if wallet_info else ""
        agent.set_wallet(settings.agent_wallet_id, address)
        # Sync bankroll — always reflects real wallet state (including $0)
        usdc_balance = await agent.sync_bankroll_from_wallet()
        if usdc_balance is not None:
            logger.info("Bankroll initialized from wallet: $%.2f USDC", usdc_balance)
        else:
            logger.info("Could not fetch wallet balance from Circle — is Circle offline?")

    # Schedule agent ticks
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_agent_tick,
        "interval",
        minutes=settings.agent_interval_minutes,
        id="agent_tick",
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started — agent ticks every %d min", settings.agent_interval_minutes)

    yield

    scheduler.shutdown()
    logger.info("Shutdown complete")


async def _run_agent_tick():
    try:
        decisions = await agent.tick()
        logger.info("Agent tick completed — %d decisions", len(decisions))
    except Exception as exc:
        logger.error("Agent tick failed: %s", exc)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AlphaOracle",
    description="AI-powered prediction market intelligence agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard", response_model=DashboardStats)
async def get_dashboard():
    """Main dashboard stats."""
    portfolio = await store.get_portfolio_summary()
    markets = await store.get_markets()
    analyses = await store.get_all_analyses()
    decisions_today = await store.get_decisions_today()
    current_strategy = await store.get_active_strategy()

    mispriced_count = sum(
        1 for a in analyses if abs(a.edge) >= agent.config.min_edge and a.confidence >= agent.config.min_confidence
    )

    return DashboardStats(
        portfolio=portfolio,
        active_markets_count=len(markets),
        mispriced_count=mispriced_count,
        decisions_today=len(decisions_today),
        current_strategy=current_strategy,
    )


# ---------------------------------------------------------------------------
# Markets
# ---------------------------------------------------------------------------

@app.get("/api/markets", response_model=list[Market])
async def list_markets(limit: int = Query(50, le=100)):
    """List cached markets (sorted by volume)."""
    return await store.get_markets(limit=limit)


@app.get("/api/markets/{market_id}", response_model=Market)
async def get_market(market_id: str):
    m = await store.get_market(market_id)
    if not m:
        raise HTTPException(404, "Market not found")
    return m


@app.get("/api/markets/{market_id}/analysis", response_model=MarketAnalysis)
async def get_market_analysis(market_id: str):
    a = await store.get_analysis(market_id)
    if not a:
        raise HTTPException(404, "Analysis not found for this market")
    return a


@app.get("/api/mispriced", response_model=list[MispricedMarket])
async def list_mispriced(limit: int = Query(20, le=50)):
    """Get markets where AI sees an edge (pre-computed from last tick)."""
    from app.kelly import kelly_bet

    markets = await store.get_markets()
    analyses = await store.get_all_analyses()
    analysis_map = {a.market_id: a for a in analyses}

    results: list[MispricedMarket] = []
    for market in markets:
        analysis = analysis_map.get(market.id)
        if not analysis:
            continue
        if analysis.confidence < agent.config.min_confidence:
            continue
        if abs(analysis.edge) < agent.config.min_edge:
            continue

        bet = kelly_bet(
            ai_probability=analysis.ai_probability,
            market_price=market.yes_price,
            bankroll=store._cash_balance,
            kelly_fraction=agent.config.kelly_fraction,
            max_bet_pct=agent.config.max_bet_pct,
        )
        if bet["side"] == "skip":
            continue

        from app.models import AgentAction

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

    results.sort(key=lambda m: abs(m.analysis.edge) * m.analysis.confidence, reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Agent decisions
# ---------------------------------------------------------------------------

@app.get("/api/decisions", response_model=list[AgentDecision])
async def list_decisions(limit: int = Query(50, le=200)):
    return await store.get_decisions(limit=limit)


@app.post("/api/agent/tick")
async def trigger_tick():
    """Manually trigger an agent tick (for testing)."""
    decisions = await agent.tick()
    return {"decisions": len(decisions), "detail": [d.model_dump() for d in decisions]}


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@app.get("/api/portfolio", response_model=PortfolioSummary)
async def get_portfolio():
    return await store.get_portfolio_summary()


@app.get("/api/portfolio/history", response_model=list[EquityPoint])
async def get_portfolio_history(limit: int = Query(500, le=500)):
    """Real equity-curve snapshots captured each tick / on bankroll changes."""
    return await store.get_equity_curve(limit=limit)


@app.get("/api/positions", response_model=list[Position])
async def list_positions(status: str = Query("open")):
    return await store.get_positions(status=status)


# ---------------------------------------------------------------------------
# Strategy versioning
# ---------------------------------------------------------------------------

@app.get("/api/strategies", response_model=list[StrategyVersion])
async def list_strategies():
    return await store.get_strategy_versions()


@app.get("/api/strategies/active", response_model=StrategyVersion)
async def get_active_strategy():
    return await store.get_active_strategy()


@app.post("/api/strategies", response_model=StrategyVersion)
async def create_strategy(
    config: StrategyConfig,
    description: str = "",
    label: Optional[str] = None,
):
    """Create a new strategy version (like git commit)."""
    logger.info(description)
    new_version = await store.create_strategy_version(
        config=config,
        description=description,
        label=label,
    )
    # Hot-update the agent
    agent.update_config(config)
    return new_version


@app.post("/api/strategies/{version_id}/rollback", response_model=StrategyVersion)
async def rollback_strategy(version_id: str):
    """Rollback to a previous strategy version."""
    rolled_back = await store.rollback_strategy(version_id)
    if not rolled_back:
        raise HTTPException(404, "Strategy version not found")
    agent.update_config(rolled_back.config)
    return rolled_back


@app.get("/api/strategies/diff")
async def diff_strategies(a: str, b: str):
    """Diff two strategy versions."""
    diff = await store.diff_strategies(a, b)
    return diff


# ---------------------------------------------------------------------------
# Circle / Arc wallet endpoints
# ---------------------------------------------------------------------------

@app.post("/api/wallet/setup")
async def setup_wallet():
    """Create a wallet set + agent wallet on Arc testnet."""
    from app.circle_client import get_circle_client

    cc = get_circle_client()
    ws = await cc.create_wallet_set("AlphaOracle Agent")
    if not ws:
        raise HTTPException(500, "Failed to create wallet set")

    wallets = await cc.create_wallet(ws["id"])
    if not wallets:
        raise HTTPException(500, "Failed to create wallet")

    # Set wallet on agent
    wallet_id = wallets[0].get("id", "")
    wallet_address = wallets[0].get("address", "")
    if wallet_id:
        agent.set_wallet(wallet_id, wallet_address)
        # Sync bankroll (likely 0 on fresh wallet — user needs to fund it)
        await agent.sync_bankroll_from_wallet()

    return {
        "wallet_set": ws,
        "wallets": wallets,
        "circle_enabled": cc.enabled,
        "note": "Fund your wallet with testnet USDC, then call POST /api/wallet/sync-balance",
    }


@app.post("/api/wallet/connect")
async def connect_wallet(wallet_id: str):
    """Connect an existing Circle wallet to the agent and sync bankroll from real balance.

    Use this when you already have a wallet (e.g. created via Circle console or a previous session).
    After connecting, the agent will use the wallet's USDC balance as its bankroll.
    """
    from app.circle_client import get_circle_client

    cc = get_circle_client()
    if not cc.enabled:
        raise HTTPException(
            400,
            "Circle API key not configured. Set CIRCLE_API_KEY in backend/.env to connect a real wallet."
        )

    # Fetch wallet info (address, state, blockchain)
    wallet_info = await cc.get_wallet_info(wallet_id)
    if not wallet_info:
        raise HTTPException(404, f"Wallet '{wallet_id}' not found. Check the wallet ID.")

    # Fetch balance
    balance_info = await cc.get_wallet_balance(wallet_id)
    usdc_balance = cc.get_usdc_amount(balance_info) if balance_info else 0.0

    # Register wallet with agent and sync bankroll (always reflect real balance, even $0)
    agent.set_wallet(wallet_id, wallet_info.get("address", ""))
    store._cash_balance = usdc_balance
    # Initial bankroll == starting capital at connect time. For an unfunded ($0)
    # wallet this stays 0 so P&L reads 0% (not a bogus -100%); once funded, the
    # next /api/wallet/sync-balance promotes the funded amount to the new baseline.
    store._initial_bankroll = usdc_balance

    logger.info("Wallet connected: %s | USDC balance: $%.2f", wallet_id, usdc_balance)

    # Re-baseline the equity curve to the connected wallet's real balance.
    store.reset_equity_curve()

    return {
        "wallet_id": wallet_id,
        "address": wallet_info.get("address", ""),
        "blockchain": wallet_info.get("blockchain", "ARC-TESTNET"),
        "state": wallet_info.get("state", "LIVE"),
        "balance_usdc": usdc_balance,
        "circle_enabled": cc.enabled,
    }


@app.post("/api/wallet/sync-balance")
async def sync_wallet_balance():
    """Re-fetch USDC balance from Circle and update agent bankroll.

    Call this after funding your wallet with testnet USDC.
    """
    from app.circle_client import get_circle_client

    cc = get_circle_client()
    if not agent.wallet_id:
        raise HTTPException(400, "No wallet connected. Call POST /api/wallet/setup or /api/wallet/connect first.")

    balance_info = await cc.get_wallet_balance(agent.wallet_id)
    if not balance_info:
        raise HTTPException(500, "Failed to fetch balance from Circle")

    usdc_balance = cc.get_usdc_amount(balance_info)
    # Always update cash balance to reflect real wallet state
    store._cash_balance = usdc_balance
    if usdc_balance > 0:
        store._initial_bankroll = usdc_balance

    # Record the funded balance as a fresh equity-curve point.
    await store.record_equity_snapshot()

    return {
        "wallet_id": agent.wallet_id,
        "balance_usdc": usdc_balance,
        "bankroll_updated": True,
        "balance_info": balance_info,
    }


@app.get("/api/wallet/status")
async def wallet_status():
    """Get current agent wallet connection status and USDC balance."""
    from app.circle_client import get_circle_client

    cc = get_circle_client()

    if not agent.wallet_id:
        return {
            "connected": False,
            "wallet_id": None,
            "address": None,
            "balance_usdc": None,
            "bankroll": store._cash_balance,
            "circle_enabled": cc.enabled,
        }

    balance_info = await cc.get_wallet_balance(agent.wallet_id)
    usdc_balance = cc.get_usdc_amount(balance_info) if balance_info else None

    return {
        "connected": True,
        "wallet_id": agent.wallet_id,
        "address": agent.wallet_address,
        "balance_usdc": usdc_balance,
        "bankroll": store._cash_balance,
        "circle_enabled": cc.enabled,
    }


@app.get("/api/wallet/{wallet_id}/balance")
async def get_balance(wallet_id: str):
    from app.circle_client import get_circle_client

    cc = get_circle_client()
    balance = await cc.get_wallet_balance(wallet_id)
    if not balance:
        raise HTTPException(404, "Could not fetch balance")
    return balance


@app.post("/api/wallet/transfer")
async def transfer(from_wallet_id: str, to_address: str, amount: str):
    from app.circle_client import get_circle_client

    cc = get_circle_client()
    tx = await cc.transfer_usdc(from_wallet_id, to_address, amount)
    if not tx:
        raise HTTPException(500, "Transfer failed")
    return tx


# ---------------------------------------------------------------------------
# Session / mode management
# ---------------------------------------------------------------------------

@app.post("/api/session/reset")
async def reset_session(mode: str = "demo"):
    """Reset in-memory state when user switches between demo/live modes.

    In demo mode: restores $1,000 paper bankroll and clears in-memory positions/decisions.
    In live mode: clears in-memory state; balance will come from real Circle wallet.
    """
    from app.circle_client import get_circle_client
    from app.config import get_settings

    settings = get_settings()

    # Clear in-memory state
    store._markets.clear()
    store._analyses.clear()
    store._decisions.clear()
    store._positions.clear()

    if mode == "demo":
        # Paper money — restore default bankroll
        store._cash_balance = settings.default_bankroll
        store._initial_bankroll = settings.default_bankroll
        agent.wallet_id = None
        agent.wallet_address = None
        logger.info("Session reset to demo mode — bankroll: $%.2f", settings.default_bankroll)
    else:
        # Live mode — balance will come from real wallet
        store._cash_balance = 0.0
        store._initial_bankroll = 0.0
        logger.info("Session reset to live mode — awaiting wallet connection")

    # Reset the equity curve to a single baseline point at the new bankroll.
    store.reset_equity_curve()

    return {"mode": mode, "bankroll": store._cash_balance, "status": "reset"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    from app.circle_client import get_circle_client

    cc = get_circle_client()
    return {
        "status": "ok",
        "agent_config": agent.config.model_dump(),
        "circle_enabled": cc.enabled,
        "wallet_connected": agent.wallet_id is not None,
        "wallet_id": agent.wallet_id,
        "bankroll": store._cash_balance,
    }
