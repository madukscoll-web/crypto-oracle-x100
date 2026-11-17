"""Paper-only signal performance tracking. No trading or investment recommendations.

Each observation is a contemporaneous indicative pool price. Outcomes use the
first later observation at or beyond the horizon, and disclose delay. Missing
observations are never interpolated or presented as measured returns.
"""
import datetime as dt
import json
import math
import pathlib

HORIZONS_HOURS = (24, 168, 720, 2160, 8760)
# Admission limits stop growth without deleting or rewriting historical signals.
MAX_OBSERVATIONS = 12000
MAX_TOKENS = 400
HISTORY_FILE = pathlib.Path("signal_history.json")


def _utc(value):
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.astimezone(dt.timezone.utc)


def record(history, item):
    """Append a valid observation; deduplicate same timestamp and pool."""
    price = item.get("base_token_price_usd")
    if isinstance(price, bool):
        return False
    try:
        price = float(price)
        stamp = _utc(item["observed_at"])
    except (TypeError, ValueError, OverflowError, KeyError):
        return False
    if not math.isfinite(price) or price <= 0:
        return False
    key = str(item.get("key") or "")
    if not key or not item.get("token_address") or item["token_address"] == "UNVERIFIED":
        return False
    # A paper signal starts only with a qualifying observed entry pattern.
    # Existing tracked signals continue receiving subsequent observations.
    if key not in history and item.get("entry_pattern") not in ("MOMENTUM WATCH", "PULLBACK WATCH"):
        return False
    if key not in history and len(history) >= MAX_TOKENS:
        return False
    observations = history.setdefault(key, [])
    if not isinstance(observations, list):
        return False
    iso = stamp.isoformat()
    network = str(item.get("network") or key.split(":", 1)[0])
    token = str(item["token_address"])
    same_token = (lambda value: str(value) == token) if network == "solana" else (lambda value: str(value).lower() == token.lower())
    if observations and not same_token(observations[0].get("token_address", "")):
        return False  # Pool identity changed; never splice two token histories.
    if observations and stamp <= _utc(observations[-1]["at"]):
        return False  # No backdated insertion or replacement of the signal anchor.
    if len(observations) >= MAX_OBSERVATIONS:
        return False
    observations.append({
        "at": iso, "price_usd": price,
        "entry_pattern": str(item.get("entry_pattern", "UNCLASSIFIED")),
        "market_setup": str(item.get("market_setup", "UNCLASSIFIED")),
        "token_address": str(item["token_address"]),
        "source": str(item.get("price_source") or "GeckoTerminal indicative pool price"),
    })
    return True


def outcomes(observations, horizons=HORIZONS_HOURS):
    """Return measured paper outcomes, not backtested execution returns."""
    if not observations:
        return []
    first = observations[0]
    start = _utc(first["at"])
    entry = float(first["price_usd"])
    result = []
    for hours in horizons:
        target = start + dt.timedelta(hours=hours)
        eligible = [x for x in observations[1:] if _utc(x["at"]) >= target]
        if not eligible:
            result.append({"horizon_hours": hours, "status": "PENDING"})
            continue
        match = eligible[0]
        observed = _utc(match["at"])
        delay_hours = (observed - target).total_seconds() / 3600
        # Late measurements are not equivalent to the requested horizon.
        if delay_hours > max(6, hours * 0.1):
            result.append({"horizon_hours": hours, "status": "NO_TIMELY_SAMPLE",
                           "delay_hours": round(delay_hours, 2)})
            continue
        pct = (float(match["price_usd"]) / entry - 1) * 100
        result.append({"horizon_hours": hours, "status": "OBSERVED",
                       "change_percent": round(pct, 2),
                       "observed_at": match["at"],
                       "delay_hours": round(delay_hours, 2)})
    return result


def load(path=HISTORY_FILE):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Signal history must be a JSON object")
    return data


def save(history, path=HISTORY_FILE):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def sampled_risk(observations):
    """Excursions across retained samples only; never infer intrahour extremes."""
    if not observations:
        return {"status": "INSUFFICIENT EVIDENCE"}
    prices = [float(row["price_usd"]) for row in observations]
    if any(not math.isfinite(price) or price <= 0 for price in prices):
        return {"status": "INSUFFICIENT EVIDENCE"}
    entry, peak, drawdown = prices[0], prices[0], 0.0
    for price in prices:
        peak = max(peak, price)
        drawdown = min(drawdown, price / peak - 1)
    return {"status": "OBSERVED_INDICATIVE_SAMPLES", "sample_count": len(prices),
            "entry_at": observations[0]["at"], "last_at": observations[-1]["at"],
            "maximum_favorable_excursion_percent": round((max(prices) / entry - 1) * 100, 2),
            "maximum_adverse_excursion_percent": round((min(prices) / entry - 1) * 100, 2),
            "maximum_drawdown_percent": round(drawdown * 100, 2),
            "execution_adjusted_returns": None,
            "limitation": "Sampled indicative prices; gaps, slippage, fees and liquidity unmeasured"}
