"""Conservative closed-candle ATL recovery assessment.

Research-only: never issues BUY admission, orders, or numerical price targets.
Candle input must be from one validated venue, pair, timeframe and quote basis.
"""
from datetime import datetime, timezone
from atl_monitor_core import positive

MIN_CANDLES = 30

def assess_recovery(candles, *, comparable=False, venue_verified=False,
                    max_age_seconds=7200, now=None):
    """Requires 30 consecutive, chronological, closed hourly candles.

    Rule: recent five-candle low above preceding five-candle low; last close
    above prior 20-close maximum; last volume > 1.5x prior 20-volume mean.
    A positive result is a technical watch, never an investment approval.
    """
    fail = lambda reason: {"status": "INSUFFICIENT EVIDENCE", "reason": reason,
                           "buy_approved": False}
    if not comparable or not venue_verified:
        return fail("UNVERIFIED_VENUE_OR_PRICE_BASIS")
    if not isinstance(candles, list) or len(candles) < MIN_CANDLES:
        return fail("INSUFFICIENT_CLOSED_CANDLES")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return fail("NAIVE_CLOCK")
    parsed = []
    for c in candles:
        if not isinstance(c, dict) or c.get("closed") is not True:
            return fail("UNVERIFIED_CANDLE_CLOSURE")
        try:
            ts = datetime.fromisoformat(c["at"].replace("Z", "+00:00"))
        except (ValueError, TypeError, KeyError, AttributeError):
            return fail("INVALID_TIMESTAMP")
        if ts.tzinfo is None:
            return fail("NAIVE_CANDLE_TIMESTAMP")
        low, high, close, volume = (positive(c.get(k)) for k in ("low", "high", "close", "volume"))
        if None in (low, high, close, volume) or not low <= close <= high:
            return fail("INVALID_OHLCV")
        parsed.append((ts.astimezone(timezone.utc), low, high, close, volume))
    parsed.sort(key=lambda x: x[0])
    if len(set(x[0] for x in parsed)) != len(parsed):
        return fail("DUPLICATE_CANDLES")
    if any((b[0]-a[0]).total_seconds() != 3600 for a,b in zip(parsed,parsed[1:])):
        return fail("CANDLE_GAP_OR_WRONG_TIMEFRAME")
    age = (now.astimezone(timezone.utc)-parsed[-1][0]).total_seconds()
    if age < 0 or age > max_age_seconds:
        return fail("STALE_OR_FUTURE_CANDLE")
    prior = parsed[-21:-1]
    higher_low = min(x[1] for x in parsed[-5:]) > min(x[1] for x in parsed[-10:-5])
    breakout = parsed[-1][3] > max(x[3] for x in prior)
    volume_confirmed = parsed[-1][4] > sum(x[4] for x in prior) / len(prior) * 3 / 2
    status = "TECHNICAL WATCH" if all((higher_low, breakout, volume_confirmed)) else "NO_TRIGGER"
    return {"status": status, "higher_low": higher_low, "breakout": breakout,
            "volume_confirmed": volume_confirmed, "buy_approved": False,
            "rule_version": 1, "candles_assessed": len(parsed)}
