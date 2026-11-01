"""Read-only quality-altcoin reversal research. No orders or BUY authorization.

Consumes independently sourced, chronological OHLCV candles; no network calls.
A WATCH is a technical observation, not an investment recommendation.
"""
from __future__ import annotations

import math
from statistics import mean


STABLE_BASES = frozenset({
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDD", "USDE", "USDS",
    "PYUSD", "FRAX", "LUSD", "GUSD", "EURC", "RLUSD", "USD1", "USTC",
})


def eligible_symbol(symbol: str) -> bool:
    """Conservative exclusion; exchange metadata must additionally verify the asset."""
    if not isinstance(symbol, str) or not symbol.strip():
        return False
    base = symbol.upper().strip().split("/")[0].split("_")[0].split("-")[0]
    if base in STABLE_BASES or base.endswith(("3L", "3S", "5L", "5S", "UP", "DOWN")):
        return False
    return base.isascii() and base.isalnum() and 2 <= len(base) <= 16


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and value >= 0 else None


def analyze(symbol: str, candles: list[dict], *, source: str,
            observed_at: str, interval: str = "1d") -> dict:
    """Assess closed chronological candles only. Latest candle must be confirmed closed.

    Each candle: timestamp, open, high, low, close, volume, closed=True.
    Never returns executable orders, a verified BUY, or an inferred win probability.
    """
    result = dict(symbol=symbol, classification="INSUFFICIENT EVIDENCE",
                  buy_authorized=False, orders_allowed=False,
                  telegram_eligible=False, source=source,
                  observed_at=observed_at, interval=interval,
                  entry_trigger=None, invalidation=None, targets=[])
    if not eligible_symbol(symbol) or not source or not observed_at or interval not in ("1d", "1w"):
        result["reason"] = "Excluded instrument or missing provenance"
        return result
    if not isinstance(candles, list) or len(candles) < 55:
        result["reason"] = "At least 55 closed candles required"
        return result
    recent = candles[-55:]
    timestamps, closes, highs, lows, volumes = [], [], [], [], []
    for c in recent:
        if not isinstance(c, dict) or c.get("closed") is not True:
            result["reason"] = "Unclosed or malformed candle"
            return result
        t = c.get("timestamp")
        o, h, l, p, v = (_number(c.get(k)) for k in ("open", "high", "low", "close", "volume"))
        if not isinstance(t, (str, int)) or any(x is None for x in (o, h, l, p, v)):
            result["reason"] = "Missing or invalid candle observation"
            return result
        if min(o, h, l, p) <= 0 or l > min(o, p) or h < max(o, p):
            result["reason"] = "Inconsistent OHLC candle"
            return result
        timestamps.append(str(t))
        closes.append(p)
        highs.append(h)
        lows.append(l)
        volumes.append(v)
    if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
        result["reason"] = "Candles not strictly chronological"
        return result
    close = closes[-1]
    ma20 = mean(closes[-20:])
    ma50 = mean(closes[-50:])
    prior_high = max(highs[-21:-1])
    prior_low = min(lows[-21:-1])
    volume_mean = mean(volumes[-21:-1])
    if volume_mean <= 0:
        result["reason"] = "No credible baseline volume"
        return result
    volume_ratio = volumes[-1] / volume_mean
    higher_low = min(lows[-10:]) > min(lows[-30:-10])
    recovering = close > ma20 and ma20 > mean(closes[-25:-5])
    breakout = close > prior_high and volume_ratio >= 1.5
    result.update(metrics=dict(close=close, ma20=ma20, ma50=ma50,
                               prior_high=prior_high, prior_low=prior_low,
                               volume_ratio=round(volume_ratio, 3),
                               higher_low=higher_low, recovering=recovering,
                               breakout=breakout))
    if breakout and recovering and higher_low:
        result.update(classification="TECHNICAL REVERSAL WATCH",
                      entry_trigger=prior_high, invalidation=prior_low,
                      reason="Closed-candle breakout with volume and improving structure; independent fundamentals, liquidity, execution and risk review still required")
    elif recovering and higher_low:
        result.update(classification="EARLY REVERSAL WATCH",
                      entry_trigger=prior_high, invalidation=prior_low,
                      reason="Improving price structure without confirmed volume breakout")
    else:
        result["reason"] = "Reversal criteria not met"
    return result
