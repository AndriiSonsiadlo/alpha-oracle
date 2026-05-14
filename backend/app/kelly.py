"""Kelly Criterion position sizing for prediction market bets."""

from __future__ import annotations


def kelly_bet(
    ai_probability: float,
    market_price: float,
    bankroll: float,
    kelly_fraction: float = 0.25,
    max_bet_pct: float = 0.10,
) -> dict:
    """Calculate optimal bet size using fractional Kelly Criterion.

    For a binary prediction market:
    - Buying YES at price p pays 1/p if YES wins (you get $1 per share, paid $p).
    - Edge = (ai_prob * payout) - 1

    Kelly formula for binary bets:
        f* = (b * p - q) / b
    where:
        b = net odds = (1 / market_price) - 1
        p = estimated true probability
        q = 1 - p

    We use fractional Kelly (kelly_fraction < 1) for safety.

    Returns:
        dict with 'side', 'fraction', 'amount', 'edge', 'expected_value'
    """
    if market_price <= 0.01 or market_price >= 0.99:
        return {"side": "skip", "fraction": 0.0, "amount": 0.0, "edge": 0.0, "expected_value": 0.0}

    yes_edge = ai_probability - market_price
    no_edge = (1 - ai_probability) - (1 - market_price)

    if abs(yes_edge) < 0.01:
        return {"side": "skip", "fraction": 0.0, "amount": 0.0, "edge": 0.0, "expected_value": 0.0}

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
    f_adjusted = min(f_adjusted, max_bet_pct)

    amount = bankroll * f_adjusted
    amount = round(amount, 2)

    ev = (p * (1.0 / price)) - 1.0

    return {
        "side": side,
        "fraction": round(f_adjusted, 4),
        "amount": amount,
        "edge": round(abs(yes_edge), 4),
        "expected_value": round(ev, 4),
    }
