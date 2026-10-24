"""Conservative arithmetic for hypothetical 10x/100x valuation scenarios.

Unknown or unverified future supply cannot be estimated.
"""
import math


def scenario(market_cap_usd, circulating_supply, future_supply, multiple):
    try:
        cap, now, future, x = map(float, (market_cap_usd, circulating_supply, future_supply, multiple))
    except (TypeError, ValueError, OverflowError):
        return {"status": "UNKNOWN", "reason": "Missing numeric supply or valuation"}
    if not all(math.isfinite(v) and v > 0 for v in (cap, now, future, x)):
        return {"status": "UNKNOWN", "reason": "Invalid or nonpositive inputs"}
    current_price = cap / now
    target_price = current_price * x
    required_cap = target_price * future
    return {"status": "SCENARIO ONLY", "target_multiple": x,
            "required_future_market_cap_usd": required_cap,
            "assumed_future_circulating_supply": future,
            "dilution_ratio": future / now,
            "target_price_usd": target_price,
            "probability": "NOT STATISTICALLY ESTABLISHED"}
