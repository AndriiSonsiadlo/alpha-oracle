"""Kelly Criterion position sizing for prediction market bets."""

from __future__ import annotations


def kelly_bet(
    ai_probability: float,
    market_price: float,
    bankroll: float,
    kelly_fraction: float = 0.25,
) -> dict:
    """Calculate optimal bet size using the fractional Kelly Criterion.

    Returns:
        dict with 'side', 'fraction', 'amount', 'edge'
    """
    if market_price <= 0.01 or market_price >= 0.99:
        return {"side": "skip", "fraction": 0.0, "amount": 0.0, "edge": 0.0}

    yes_edge = ai_probability - market_price

    if abs(yes_edge) < 0.01:
        return {"side": "skip", "fraction": 0.0, "amount": 0.0, "edge": 0.0}

    if yes_edge > 0:
        side = "yes"
        p = ai_probability
        price = market_price
    else:
        side = "no"
        p = 1 - ai_probability
        price = 1 - market_price

    b = (1.0 / price) - 1.0
    q = 1.0 - p

    f_star = (b * p - q) / b if b > 0 else 0.0
    f_star = max(0.0, f_star)

    f_adjusted = f_star * kelly_fraction
    amount = bankroll * f_adjusted

    return {
        "side": side,
        "fraction": round(f_adjusted, 4),
        "amount": round(amount, 2),
        "edge": round(abs(yes_edge), 4),
    }
