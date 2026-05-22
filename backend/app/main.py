"""AlphaOracle — FastAPI backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.agent import Agent
from app.config import get_settings
from app.models import (
    AgentDecision,
    DashboardStats,
    Market,
    MarketAnalysis,
    MispricedMarket,
    Position,
    PortfolioSummary,
    StrategyConfig,
    StrategyVersion,
)
from app.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

store: Store
agent: Agent
scheduler: AsyncIOScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, agent, scheduler
    settings = get_settings()
    store = Store()

    active_strategy = None
    try:
        active_strategy = await store.get_active_strategy()
    except Exception:
        pass
    agent = Agent(store=store, config=active_strategy.config if active_strategy else None)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_agent_tick, "interval",
        minutes=settings.agent_interval_minutes,
        id="agent_tick", max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started — agent ticks every %d min", settings.agent_interval_minutes)
    yield
    scheduler.shutdown()


async def _run_agent_tick():
    try:
        decisions = await agent.tick()
        logger.info("Agent tick completed — %d decisions", len(decisions))
    except Exception as exc:
        logger.error("Agent tick failed: %s", exc)


app = FastAPI(
    title="AlphaOracle",
    description="AI-powered prediction market intelligence agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/dashboard", response_model=DashboardStats)
async def get_dashboard():
    portfolio = await store.get_portfolio_summary()
    markets = await store.get_markets()
    analyses = await store.get_all_analyses()
    decisions_today = await store.get_decisions_today()
    current_strategy = await store.get_active_strategy()
    mispriced_count = sum(
        1 for a in analyses
        if abs(a.edge) >= agent.config.min_edge and a.confidence >= agent.config.min_confidence
    )
    return DashboardStats(
        portfolio=portfolio, active_markets_count=len(markets),
        mispriced_count=mispriced_count, decisions_today=len(decisions_today),
        current_strategy=current_strategy,
    )


@app.get("/api/markets", response_model=list[Market])
async def list_markets(limit: int = Query(50, le=100)):
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
        raise HTTPException(404, "Analysis not found")
    return a


@app.get("/api/mispriced", response_model=list[MispricedMarket])
async def list_mispriced(limit: int = Query(20, le=50)):
    from app.kelly import kelly_bet
    from app.models import AgentAction

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
            ai_probability=analysis.ai_probability, market_price=market.yes_price,
            bankroll=store._cash_balance, kelly_fraction=agent.config.kelly_fraction,
            max_bet_pct=agent.config.max_bet_pct,
        )
        if bet["side"] == "skip":
            continue
        action = AgentAction.BUY_YES if bet["side"] == "yes" else AgentAction.BUY_NO
        results.append(MispricedMarket(
            market=market, analysis=analysis, suggested_action=action,
            suggested_amount=bet["amount"], kelly_bet_fraction=bet["fraction"],
        ))
    results.sort(key=lambda m: abs(m.analysis.edge) * m.analysis.confidence, reverse=True)
    return results[:limit]


@app.get("/api/decisions", response_model=list[AgentDecision])
async def list_decisions(limit: int = Query(50, le=200)):
    return await store.get_decisions(limit=limit)


@app.post("/api/agent/tick")
async def trigger_tick():
    decisions = await agent.tick()
    return {"decisions": len(decisions), "detail": [d.model_dump() for d in decisions]}


@app.get("/api/portfolio", response_model=PortfolioSummary)
async def get_portfolio():
    return await store.get_portfolio_summary()


@app.get("/api/positions", response_model=list[Position])
async def list_positions(status: str = Query("open")):
    return await store.get_positions(status=status)


@app.get("/api/health")
async def health():
    return {"status": "ok", "agent_config": agent.config.model_dump(), "bankroll": store._cash_balance}


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
    new_version = await store.create_strategy_version(
        config=config, description=description, label=label,
    )
    agent.update_config(config)
    return new_version


@app.post("/api/strategies/{version_id}/rollback", response_model=StrategyVersion)
async def rollback_strategy(version_id: str):
    rolled_back = await store.rollback_strategy(version_id)
    if not rolled_back:
        raise HTTPException(404, "Strategy version not found")
    agent.update_config(rolled_back.config)
    return rolled_back


@app.get("/api/strategies/diff")
async def diff_strategies(a: str, b: str):
    return await store.diff_strategies(a, b)


# ---------------------------------------------------------------------------
# Circle / Arc wallet endpoints
# ---------------------------------------------------------------------------

@app.post("/api/wallet/setup")
async def setup_wallet():
    from app.circle_client import get_circle_client
    cc = get_circle_client()
    ws = await cc.create_wallet_set("AlphaOracle Agent")
    if not ws:
        raise HTTPException(500, "Failed to create wallet set")
    wallets = await cc.create_wallet(ws["id"])
    if not wallets:
        raise HTTPException(500, "Failed to create wallet")
    wallet_id = wallets[0].get("id", "")
    wallet_address = wallets[0].get("address", "")
    if wallet_id:
        agent.set_wallet(wallet_id, wallet_address)
        await agent.sync_bankroll_from_wallet()
    return {"wallet_set": ws, "wallets": wallets, "circle_enabled": cc.enabled}


@app.post("/api/wallet/connect")
async def connect_wallet(wallet_id: str):
    from app.circle_client import get_circle_client
    cc = get_circle_client()
    if not cc.enabled:
        raise HTTPException(400, "Circle API key not configured")
    wallet_info = await cc.get_wallet_info(wallet_id)
    if not wallet_info:
        raise HTTPException(404, f"Wallet '{wallet_id}' not found")
    balance_info = await cc.get_wallet_balance(wallet_id)
    usdc_balance = cc.get_usdc_amount(balance_info) if balance_info else 0.0
    agent.set_wallet(wallet_id, wallet_info.get("address", ""))
    store._cash_balance = usdc_balance
    store._initial_bankroll = usdc_balance
    store.reset_equity_curve()
    return {
        "wallet_id": wallet_id, "address": wallet_info.get("address", ""),
        "blockchain": wallet_info.get("blockchain", "ARC-TESTNET"),
        "balance_usdc": usdc_balance, "circle_enabled": cc.enabled,
    }


@app.post("/api/wallet/sync-balance")
async def sync_wallet_balance():
    from app.circle_client import get_circle_client
    cc = get_circle_client()
    if not agent.wallet_id:
        raise HTTPException(400, "No wallet connected")
    balance_info = await cc.get_wallet_balance(agent.wallet_id)
    if not balance_info:
        raise HTTPException(500, "Failed to fetch balance")
    usdc_balance = cc.get_usdc_amount(balance_info)
    store._cash_balance = usdc_balance
    if usdc_balance > 0:
        store._initial_bankroll = usdc_balance
    await store.record_equity_snapshot()
    return {"wallet_id": agent.wallet_id, "balance_usdc": usdc_balance, "bankroll_updated": True}


@app.get("/api/wallet/status")
async def wallet_status():
    from app.circle_client import get_circle_client
    cc = get_circle_client()
    if not agent.wallet_id:
        return {"connected": False, "wallet_id": None, "balance_usdc": None,
                "bankroll": store._cash_balance, "circle_enabled": cc.enabled}
    balance_info = await cc.get_wallet_balance(agent.wallet_id)
    usdc_balance = cc.get_usdc_amount(balance_info) if balance_info else None
    return {"connected": True, "wallet_id": agent.wallet_id, "address": agent.wallet_address,
            "balance_usdc": usdc_balance, "bankroll": store._cash_balance, "circle_enabled": cc.enabled}


@app.get("/api/portfolio/history")
async def get_portfolio_history(limit: int = Query(500, le=500)):
    return await store.get_equity_curve(limit=limit)


# ---------------------------------------------------------------------------
# Session / mode management
# ---------------------------------------------------------------------------

@app.post("/api/session/reset")
async def reset_session(mode: str = "demo"):
    settings = get_settings()
    store._markets.clear()
    store._analyses.clear()
    store._decisions.clear()
    store._positions.clear()
    if mode == "demo":
        store._cash_balance = settings.default_bankroll
        store._initial_bankroll = settings.default_bankroll
        agent.wallet_id = None
        agent.wallet_address = None
    else:
        store._cash_balance = 0.0
        store._initial_bankroll = 0.0
    store.reset_equity_curve()
    return {"mode": mode, "bankroll": store._cash_balance, "status": "reset"}


# Update health to include wallet info
@app.get("/api/health")
async def health_full():
    from app.circle_client import get_circle_client
    cc = get_circle_client()
    return {
        "status": "ok", "agent_config": agent.config.model_dump(),
        "circle_enabled": cc.enabled, "wallet_connected": agent.wallet_id is not None,
        "wallet_id": agent.wallet_id, "bankroll": store._cash_balance,
    }
