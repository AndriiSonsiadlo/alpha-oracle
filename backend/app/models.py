from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MarketStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"


class AgentAction(str, Enum):
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    SELL = "sell"
    HOLD = "hold"
    SKIP = "skip"


class Market(BaseModel):
    id: str
    question: str
    description: str = ""
    category: str = ""
    end_date: Optional[str] = None
    yes_price: float = 0.0
    no_price: float = 0.0
    volume: float = 0.0
    liquidity: float = 0.0
    source: str = "polymarket"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class MarketAnalysis(BaseModel):
    market_id: str
    ai_probability: float
    confidence: float
    edge: float = 0.0
    reasoning: str = ""
    news_summary: str = ""
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class AgentDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    market_id: str
    market_question: str = ""
    action: AgentAction
    amount_usdc: float = 0.0
    kelly_fraction: float = 0.0
    reasoning_trace: str = ""
    ai_probability: float = 0.0
    market_probability: float = 0.0
    edge: float = 0.0
    confidence: float = 0.0
    strategy_version_id: Optional[str] = None
    tx_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    market_id: str
    market_question: str = ""
    side: str = "yes"  # "yes" or "no"
    entry_price: float = 0.0
    current_price: float = 0.0
    amount_usdc: float = 0.0
    shares: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "open"  # "open" or "closed"
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None


class PortfolioSummary(BaseModel):
    total_value: float = 0.0
    cash_balance: float = 0.0
    positions_value: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    open_positions: int = 0
    total_trades: int = 0
    win_rate: float = 0.0


class MispricedMarket(BaseModel):
    market: Market
    analysis: MarketAnalysis
    suggested_action: AgentAction
    suggested_amount: float = 0.0
    kelly_bet_fraction: float = 0.0


# ---------------------------------------------------------------------------
# Strategy versioning ("git for agents")
# ---------------------------------------------------------------------------

class StrategyVersionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPERIMENTAL = "experimental"


class StrategyConfig(BaseModel):
    kelly_fraction: float = 0.25
    max_bet_pct: float = 0.10
    min_edge: float = 0.05
    min_confidence: float = 0.6
    categories: list[str] = Field(default_factory=list)
    model_name: str = "llama-3.1-8b-instant"
    provider: str = "auto"
    prompt_template: str = "default"


class StrategyVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version_label: str = ""
    parent_id: Optional[str] = None
    config: StrategyConfig = Field(default_factory=StrategyConfig)
    status: StrategyVersionStatus = StrategyVersionStatus.ACTIVE
    description: str = ""
    performance_snapshot: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StrategyDiff(BaseModel):
    version_a_id: str
    version_b_id: str
    changes: list[dict] = Field(default_factory=list)


class DashboardStats(BaseModel):
    portfolio: PortfolioSummary
    active_markets_count: int = 0
    mispriced_count: int = 0
    decisions_today: int = 0
    current_strategy: Optional[StrategyVersion] = None


class EquityPoint(BaseModel):
    """One snapshot of total portfolio value at a point in time."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_value: float = 0.0
    cash_balance: float = 0.0
    positions_value: float = 0.0
    total_pnl: float = 0.0
