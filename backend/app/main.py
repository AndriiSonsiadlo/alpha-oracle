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
