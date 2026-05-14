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
