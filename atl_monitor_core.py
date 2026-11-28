"""Fail-closed ATL observation primitives. No network access, alerts or BUY admission."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

LOW_CAP_FLOOR = Decimal("5000000")    # owner definition: low cap is $5M-$200M
MID_CAP_FLOOR = Decimal("200000000")
ATL_UNIVERSE_FLOOR = LOW_CAP_FLOOR
HIGH_CAP_FLOOR = Decimal("1000000000")
NEAR_PERCENT = Decimal("5")

def positive(value):
    if isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None

def cap_class(market_cap, *, verified=False, fresh=False, conflicting=False):
    cap = positive(market_cap)
    if not verified or not fresh or conflicting or cap is None:
        return "UNVERIFIED"
    if cap < LOW_CAP_FLOOR:
        return "EXCLUDED"
    if cap < MID_CAP_FLOOR:
        return "LOW_CAP"
    return "MID_CAP" if cap <= HIGH_CAP_FLOOR else "HIGH_CAP"

def classify_low(current, previous_low, *, lifetime_complete=False,
                 comparable=False, corroborated=False, source_precision=0):
    """Previous minimum must be independently validated and never overwritten here.

    An observed-history baseline cannot be promoted to a lifetime minimum.
    A lower print without corroboration is an anomaly, not a new validated ATL.
    """
    price, baseline = positive(current), positive(previous_low)
    if price is None or baseline is None or not comparable:
        return {"status": "UNAVAILABLE", "percent_above": None}
    try:
        tolerance = Decimal(str(source_precision))
    except (InvalidOperation, TypeError, ValueError):
        return {"status": "UNAVAILABLE", "percent_above": None}
    if not tolerance.is_finite() or tolerance < 0 or tolerance >= 1:
        return {"status": "UNAVAILABLE", "percent_above": None}
    pct = (price / baseline - 1) * 100
    if price < baseline * (1 - tolerance):
        if not corroborated:
            return {"status": "UNVALIDATED_LOW", "percent_above": pct}
        return {"status": "ALL-TIME LOW" if lifetime_complete else "LOWEST OBSERVED PRICE",
                "percent_above": pct}
    if pct >= 0 and pct <= NEAR_PERCENT:
        return {"status": "NEAR ALL-TIME LOW" if lifetime_complete else "NEAR OBSERVED LOW",
                "percent_above": pct}
    return {"status": "NO_EVENT", "percent_above": pct}

LABELS = frozenset({
    "NEW TOKEN | RESEARCH WATCH", "ALL-TIME LOW | WATCH",
    "NEAR ALL-TIME LOW | WATCH", "LOWEST OBSERVED PRICE | WATCH",
    "NEAR OBSERVED LOW | WATCH", "ATL RECOVERY | TECHNICAL WATCH",
    "OBSERVED-LOW RECOVERY | TECHNICAL WATCH",
    "BULLISH REVERSAL | TECHNICAL WATCH",
    "BREAKOUT / RETEST | TECHNICAL WATCH",
    "INVALIDATION / EXIT WATCH", "BOT HEALTH | OPERATIONAL",
})

def labeled_message(label, body):
    if label not in LABELS:
        raise ValueError("Unknown Telegram classification")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Missing message body")
    return label + "\n" + body.strip()


