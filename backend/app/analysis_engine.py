"""LLM-powered market analysis — estimates true probabilities for prediction markets."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.llm_clients import get_client_for_model
from app.models import Market, MarketAnalysis
from app.news_fetcher import fetch_news, format_news_block

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """\
You are a prediction market analyst AI. Given a prediction market question, \
its current market probability, description, and any available context, \
you must estimate the TRUE probability of the event occurring.

Rules:
1. Be calibrated — if you say 70%, events like this should happen ~70% of the time.
2. Consider base rates, recent news, historical precedent, and logical reasoning.
3. Explain your reasoning step-by-step before giving a final probability.
4. Also rate your CONFIDENCE in your estimate (0.0-1.0).
5. Summarize the key news/data points that influenced your analysis.

Respond in JSON format:
{
  "estimated_probability": 0.65,
  "confidence": 0.7,
  "reasoning": "Step by step reasoning...",
  "news_summary": "Key factors: ..."
}
"""

USER_PROMPT_TEMPLATE = """\
Market Question: {question}
Market Description: {description}
Current Market Price (YES): ${yes_price:.2f} (implies {market_prob:.0%} probability)
Category: {category}
End Date: {end_date}
Volume: ${volume:,.0f}

Recent News Headlines:
{news}

Analyze this market. What is the TRUE probability of YES? Respond in JSON."""


async def analyze_market(
    market: Market,
    model: str = DEFAULT_MODEL,
    provider: Optional[str] = None,
) -> MarketAnalysis:
    """Use an LLM to estimate the true probability for a single market."""
    news_items = await fetch_news(market.question, limit=5)
    news_block = format_news_block(news_items)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        question=market.question,
        description=market.description[:500],
        yes_price=market.yes_price,
        market_prob=market.yes_price,
        category=market.category,
        end_date=market.end_date or "N/A",
        volume=market.volume,
        news=news_block,
    )

    try:
        client = get_client_for_model(model, provider)
        result = await client.complete_json(
            SYSTEM_PROMPT, user_prompt, model, temperature=0.3, max_tokens=1024
        )

        ai_prob = float(result.get("estimated_probability", market.yes_price))
        ai_prob = max(0.01, min(0.99, ai_prob))

        confidence = float(result.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        edge = ai_prob - market.yes_price

        return MarketAnalysis(
            market_id=market.id,
            ai_probability=ai_prob,
            confidence=confidence,
            edge=edge,
            reasoning=result.get("reasoning", ""),
            news_summary=result.get("news_summary") or news_block,
            analyzed_at=datetime.utcnow(),
        )

    except Exception as exc:
        logger.error("LLM analysis failed for market %s: %s", market.id, exc)
        return MarketAnalysis(
            market_id=market.id,
            ai_probability=market.yes_price,
            confidence=0.0,
            edge=0.0,
            reasoning=f"Analysis failed: {exc}",
            news_summary="",
            analyzed_at=datetime.utcnow(),
        )
