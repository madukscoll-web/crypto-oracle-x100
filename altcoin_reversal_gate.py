"""Read-only Gate Spot OHLCV adapter for altcoin reversal research.

Gate API v4 candlestick array format: [timestamp, quote_volume, close,
high, low, open, base_volume, ...]. A closed candle must end before now.
"""
import datetime as dt
import math
from altcoin_reversal_research import analyze, eligible_symbol


def gate_candles(raw, *, interval_seconds, now=None):
    if not isinstance(raw, list) or len(raw) < 55:
        raise ValueError("Insufficient Gate OHLCV history")
    if interval_seconds not in (86400, 604800):
        raise ValueError("Only daily/weekly intervals supported")
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).timestamp()
    output = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ValueError("Malformed Gate candle")
        try:
            timestamp = int(row[0])
            volume, close, high, low, open_ = [float(row[i]) for i in (1, 2, 3, 4, 5)]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Invalid Gate candle values") from exc
        if not all(math.isfinite(v) for v in (volume, close, high, low, open_)):
            raise ValueError("Non-finite Gate candle values")
        if timestamp <= 0 or timestamp + interval_seconds > now:
            # Do not evaluate incomplete candles.
            continue
        output.append(dict(timestamp=timestamp, volume=volume, close=close,
                           high=high, low=low, open=open_, closed=True))
    output.sort(key=lambda c: c["timestamp"])
    if len({x["timestamp"] for x in output}) != len(output):
        raise ValueError("Duplicate Gate candle timestamps")
    return output


def research_gate_pair(gate, pair_id, *, interval="1d", now=None):
    """PublicGate.get only; does not query account endpoints or place orders."""
    if not isinstance(pair_id, str) or not pair_id.endswith("_USDT"):
        raise ValueError("USDT spot pair required")
    symbol = pair_id[:-5]
    if not eligible_symbol(symbol):
        raise ValueError("Excluded instrument")
    if interval not in ("1d", "1w"):
        raise ValueError("Unsupported interval")
    raw = gate.get("/spot/candlesticks", dict(currency_pair=pair_id,
                                              interval=interval, limit=120))
    candles = gate_candles(raw, interval_seconds=86400 if interval == "1d" else 604800,
                           now=now)
    observed = dt.datetime.now(dt.timezone.utc).isoformat()
    return analyze(symbol + "/USDT", candles,
                   source="Gate public Spot API v4 /spot/candlesticks",
                   observed_at=observed, interval=interval)
