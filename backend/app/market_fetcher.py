"""Fetch live prediction markets from Polymarket's public Gamma API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import get_settings
from app.models import Market

logger = logging.getLogger(__name__)

GAMMA_MARKETS = "/markets"


async def fetch_markets(
    limit: int = 50,
    active: bool = True,
    category: Optional[str] = None,
    offset: int = 0,
) -> list[Market]:
    """Fetch active prediction markets from Polymarket Gamma API.

    The Gamma API is public, no auth required.
    """
    settings = get_settings()
    params: dict = {
        "limit": limit,
        "offset": offset,
        "closed": "false" if active else "true",
        "order": "volume",
        "ascending": "false",
    }
    if category:
        params["tag"] = category

    markets: list[Market] = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{settings.polymarket_api_url}{GAMMA_MARKETS}",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        for raw in data:
            try:
                outcome_prices = _parse_prices(raw.get("outcomePrices", ""))
                yes_price = outcome_prices[0] if len(outcome_prices) > 0 else 0.0
                no_price = outcome_prices[1] if len(outcome_prices) > 1 else 1.0 - yes_price

                markets.append(
                    Market(
                        id=str(raw.get("id", raw.get("condition_id", ""))),
                        question=raw.get("question", ""),
                        description=raw.get("description", ""),
                        category=raw.get("groupItemTitle", raw.get("category", "")),
                        end_date=raw.get("endDate"),
                        yes_price=yes_price,
                        no_price=no_price,
                        volume=float(raw.get("volume", 0) or 0),
                        liquidity=float(raw.get("liquidity", 0) or 0),
                        source="polymarket",
                        fetched_at=datetime.utcnow(),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping market %s: %s", raw.get("id"), exc)

    except httpx.HTTPError as exc:
        logger.error("Polymarket API error: %s", exc)

    return markets


def _parse_prices(raw_prices) -> list[float]:
    """Parse outcomePrices which can be a JSON string like '["0.55","0.45"]'."""
    import json

    if not raw_prices:
        return []
    if isinstance(raw_prices, list):
        return [float(p) for p in raw_prices]
    if isinstance(raw_prices, str):
        try:
            parsed = json.loads(raw_prices)
            return [float(p) for p in parsed]
        except (json.JSONDecodeError, TypeError):
            return []
    return []
