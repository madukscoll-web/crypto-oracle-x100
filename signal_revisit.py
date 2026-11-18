"""Independent re-pricing of tracked paper signals. Research only; never trades.

Tracked pools used to receive a new price only when they happened to reappear
as fresh candidates. Tokens that collapsed dropped out of discovery and were
never measured again, so measured outcomes were biased upward and most signals
could never reach a 24h/7d/30d horizon. This module re-prices every tracked
signal on a bounded schedule, independent of discovery, and keeps an explicit
record of pools that vanish or lose their exit liquidity.

The summary refuses to draw a profitability conclusion from a small sample and
reports a conservative figure in which unrealizable exits count as total loss.
"""
import datetime as dt
import json
import math
import pathlib
import statistics

import signal_tracker
from oracle_http import ProviderRateLimited

API = "https://api.geckoterminal.com/api/v2"
STATE_FILE = pathlib.Path("signal_revisit_state.json")
BATCH_SIZE = 30                    # GeckoTerminal multi-pool endpoint limit
MAX_BATCHES_PER_RUN = 4            # bounded request budget per scan
MIN_GAP_MINUTES = 45               # do not re-price more often than this
MAX_AGE_HOURS = 744                # stop revisiting after 31 days
UNREALIZABLE_LIQUIDITY_USD = 5000  # a quote against a pool this thin is not an exit
MISSING_LIMIT = 3                  # consecutive absences before "vanished"
MIN_SAMPLE_FOR_CONCLUSION = 30
ASSUMED_ROUND_TRIP_COST_PERCENT = 3.0  # ASSUMPTION for display only, not measured
REPORT_HORIZONS = (24, 168, 720)


def _utc(value):
    return signal_tracker._utc(value)


def load_state(path=STATE_FILE):
    path = pathlib.Path(path)
    if not path.exists():
        return {"version": 1, "pools": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("pools"), dict):
        raise ValueError("Signal revisit state must contain a pools object")
    return data


def save_state(state, path=STATE_FILE):
    path = pathlib.Path(path)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _finite_positive(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _same_token(network, left, right):
    if network == "solana":
        return str(left) == str(right)
    return str(left).lower() == str(right).lower()


def _base_token_address(pool, network):
    token_id = ((((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id") or "")
    prefix = network + "_"
    return token_id[len(prefix):] if token_id.startswith(prefix) else None


def due(history, state, now, *, min_gap_minutes=MIN_GAP_MINUTES, max_age_hours=MAX_AGE_HOURS):
    """Tracked keys needing a price, most overdue first."""
    rows = []
    for key, observations in history.items():
        if not isinstance(observations, list) or not observations or ":" not in key:
            continue
        try:
            first = _utc(observations[0]["at"])
            last = _utc(observations[-1]["at"])
        except (KeyError, TypeError, ValueError):
            continue
        if (now - first).total_seconds() / 3600 > max_age_hours:
            continue
        info = state["pools"].get(key, {})
        if info.get("status") == "VANISHED":
            continue
        checked = last
        if info.get("last_checked"):
            try:
                checked = max(last, _utc(info["last_checked"]))
            except ValueError:
                pass
        if (now - checked).total_seconds() / 60 < min_gap_minutes:
            continue
        rows.append((checked, key))
    return [key for _, key in sorted(rows)]


def revisit(history, fetch, now, state, *, max_batches=MAX_BATCHES_PER_RUN):
    """Re-price due signals in batches. Never raises on provider failure."""
    report = {"due": 0, "attempted": 0, "priced": 0, "pool_not_returned": 0,
              "identity_mismatch": 0, "unrealizable": 0, "vanished": 0,
              "batches": 0, "stopped": None}
    keys = due(history, state, now)
    report["due"] = len(keys)
    by_network = {}
    for key in keys:
        by_network.setdefault(key.split(":", 1)[0], []).append(key)
    stamp = now.astimezone(dt.timezone.utc).isoformat()
    batches = []
    # Round-robin across networks so one busy chain cannot starve the others.
    queues = {network: list(items) for network, items in by_network.items()}
    while any(queues.values()):
        for network, items in queues.items():
            if items:
                batches.append((network, [items.pop(0) for _ in range(min(BATCH_SIZE, len(items)))]))
    for network, batch in batches[:max_batches]:
        addresses = [key.split(":", 1)[1] for key in batch]
        url = f"{API}/networks/{network}/pools/multi/{','.join(addresses)}"
        try:
            payload = fetch(url)
        except ProviderRateLimited:
            report["stopped"] = "RATE_LIMITED"
            break
        except (OSError, ValueError):
            report["stopped"] = "PROVIDER_ERROR"
            break
        report["batches"] += 1
        pools = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(pools, list):
            report["stopped"] = "MALFORMED_RESPONSE"
            break
        returned = {}
        for pool in pools:
            attrs = (pool or {}).get("attributes") or {}
            address = str(attrs.get("address") or "")
            returned[address if network == "solana" else address.lower()] = pool
        for key in batch:
            report["attempted"] += 1
            address = key.split(":", 1)[1]
            pool = returned.get(address if network == "solana" else address.lower())
            info = state["pools"].setdefault(key, {})
            info["last_checked"] = stamp
            if pool is None:
                info["missing"] = int(info.get("missing", 0)) + 1
                info["status"] = "VANISHED" if info["missing"] >= MISSING_LIMIT else "POOL_NOT_RETURNED"
                report["pool_not_returned"] += 1
                report["vanished"] += info["status"] == "VANISHED"
                continue
            attrs = pool.get("attributes") or {}
            expected = history[key][0].get("token_address", "")
            actual = _base_token_address(pool, network)
            if actual is None or not _same_token(network, actual, expected):
                info["status"] = "IDENTITY_MISMATCH"
                report["identity_mismatch"] += 1
                continue  # never splice a different token into this history
            info["missing"] = 0
            price = _finite_positive(attrs.get("base_token_price_usd"))
            liquidity = _finite_positive(attrs.get("reserve_in_usd"))
            info["last_liquidity_usd"] = liquidity
            if liquidity is None or liquidity < UNREALIZABLE_LIQUIDITY_USD:
                info["status"] = "UNREALIZABLE"
                report["unrealizable"] += 1
            else:
                info["status"] = "ACTIVE"
            if price is None:
                continue
            item = {"key": key, "network": network, "token_address": history[key][0]["token_address"],
                    "observed_at": stamp, "base_token_price_usd": price, "entry_pattern": "REVISIT"}
            if attrs.get("price_source") == "dexscreener":
                item["price_source"] = "DexScreener indicative pair price"
            if signal_tracker.record(history, item):
                report["priced"] += 1
    return report


def _quantiles(values):
    values = sorted(values)
    return {"n": len(values), "median_percent": round(statistics.median(values), 2),
            "mean_percent": round(statistics.fmean(values), 2),
            "positive": sum(v > 0 for v in values)}


def performance_summary(history, state, now, *, cost_percent=ASSUMED_ROUND_TRIP_COST_PERCENT):
    """Measured outcomes by horizon with a conservative no-exit variant."""
    horizons = {}
    for hours in REPORT_HORIZONS:
        measured, conservative = [], []
        for key, observations in history.items():
            if not isinstance(observations, list) or not observations:
                continue
            try:
                age = (now - _utc(observations[0]["at"])).total_seconds() / 3600
            except (KeyError, TypeError, ValueError):
                continue
            result = next((r for r in signal_tracker.outcomes(observations) if r["horizon_hours"] == hours), None)
            status = state["pools"].get(key, {}).get("status")
            if result and result["status"] == "OBSERVED":
                value = result["change_percent"]
                measured.append(value)
                # A quote against an unexitable pool is not realizable proceeds.
                conservative.append(-100.0 if status in ("UNREALIZABLE", "VANISHED") else value)
            elif age >= hours and status in ("UNREALIZABLE", "VANISHED"):
                conservative.append(-100.0)
        entry = {"horizon_hours": hours, "measured": None, "net_of_assumed_cost": None, "conservative": None}
        if measured:
            entry["measured"] = _quantiles(measured)
            entry["net_of_assumed_cost"] = _quantiles([v - cost_percent for v in measured])
        if conservative:
            entry["conservative"] = _quantiles(conservative)
        horizons[str(hours)] = entry
    largest = max((h["measured"]["n"] for h in horizons.values() if h["measured"]), default=0)
    statuses = [info.get("status") for info in state["pools"].values()]
    return {
        "horizons": horizons,
        "tracked": len(history),
        "vanished": statuses.count("VANISHED"),
        "unrealizable": statuses.count("UNREALIZABLE"),
        "assumed_round_trip_cost_percent": cost_percent,
        "cost_is_assumption": True,
        "conclusion": ("INSUFFICIENT SAMPLE: no profitability conclusion is supported"
                       if largest < MIN_SAMPLE_FOR_CONCLUSION else
                       "Sample large enough to inspect, but selection bias and indicative prices remain"),
        "minimum_sample": MIN_SAMPLE_FOR_CONCLUSION,
        "limitation": "Indicative pool prices at sampled times; no measured slippage, fees or depth. Not a trading recommendation.",
    }
