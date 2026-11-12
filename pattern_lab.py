"""Unbiased feature/outcome study of newly seen pools. Research only; never trades.

Why this exists: the outcome tracker follows only pools that matched the bot's own
entry patterns, so it cannot say which *features* separate pools that went up from
pools that collapsed. This module records the features of EVERY candidate once, at
first sight, then re-prices each pool later and measures outcomes net of an assumed
cost, counting unexitable pools as total loss (no survivorship bias).

It reports a pattern only if it survives: a time-ordered train/test split, a minimum
sample, a confidence-interval test against the base rate and a multiple-comparison
correction. Below the minimum sample it says INSUFFICIENT SAMPLE and shows no score.
A validated pattern is a statistical observation about past pools, not a forecast,
and it never relaxes any safety gate.
"""
import datetime as dt
import json
import math
import pathlib
import statistics

from oracle_http import ProviderRateLimited

API = "https://api.geckoterminal.com/api/v2"
DATASET_FILE = pathlib.Path("pattern_dataset.json")
MAX_ROWS = 4000
MAX_NEW_PER_RUN = 80
BATCH_SIZE = 30
MAX_BATCHES_PER_RUN = 2
MIN_GAP_MINUTES = 45
HORIZON_HOURS = 24
HORIZONS = (24, 72, 168)
MAX_AGE_HOURS = 260
WINDOW_FACTOR = 1.5               # a price taken later than 1.5x the horizon is not that horizon's outcome
UNEXITABLE_LIQUIDITY_USD = 5000
ASSUMED_COST_PERCENT = 3.0
MIN_TOTAL_LABELED = 200
MIN_BUCKET = 30
MIN_LIFT = 1.25
Z95 = 1.96
NUMERIC_FEATURES = ("liquidity", "volume", "volume_to_liquidity", "trades", "buy_share",
                    "change_h1", "change_h24", "age_hours", "score")
CATEGORICAL_FEATURES = ("network", "goplus", "owner_control")


def _utc(value):
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.astimezone(dt.timezone.utc)


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def load(path=DATASET_FILE):
    path = pathlib.Path(path)
    if not path.exists():
        return {"version": 1, "rows": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rows"), dict):
        raise ValueError("Pattern dataset must contain a rows object")
    return data


def save(dataset, path=DATASET_FILE):
    path = pathlib.Path(path)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(dataset, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(path)


def _status(item, name):
    record = (item.get("verification") or {}).get(name)
    status = record.get("status") if isinstance(record, dict) else None
    return str(status) if status else "NONE"


def features(item):
    """Features known at first sight. Missing values stay None, never zero."""
    liquidity, volume = _num(item.get("liquidity")), _num(item.get("volume"))
    ratio = volume / liquidity if liquidity and volume is not None and liquidity > 0 else None
    return {"liquidity": liquidity, "volume": volume, "volume_to_liquidity": ratio,
            "trades": _num(item.get("trades")), "buy_share": _num(item.get("buy_share")),
            "change_h1": _num(item.get("change_h1")), "change_h24": _num(item.get("change_h24")),
            "age_hours": _num(item.get("age_hours")), "score": _num(item.get("score")),
            "network": str(item.get("network") or "unknown"),
            "goplus": _status(item, "contract_security"), "owner_control": _status(item, "owner_control")}


def capture(dataset, item, now, *, limit=MAX_NEW_PER_RUN, added=None):
    """Record a pool once, at first sight. Existing rows are never rewritten."""
    key = str(item.get("key") or "")
    price = _num(item.get("base_token_price_usd"))
    token = str(item.get("token_address") or "")
    if not key or ":" not in key or not token or token == "UNVERIFIED" or price is None or price <= 0:
        return False
    rows = dataset["rows"]
    if key in rows or len(rows) >= MAX_ROWS:
        return False
    if added is not None:
        if added[0] >= limit:
            return False
        added[0] += 1
    rows[key] = {"t0": now.astimezone(dt.timezone.utc).isoformat(), "price0": price,
                 "token_address": token, "features": features(item), "obs": []}
    return True


def _pending(row, age):
    """Horizons reached, still inside their measurement window, not yet measured."""
    measured = {o.get("horizon") for o in row["obs"]}
    return [h for h in HORIZONS if age >= h and age <= h * WINDOW_FACTOR and h not in measured]


def due(dataset, now):
    """Rows needing a price: those that have reached a horizon not yet measured."""
    queue = []
    for key, row in dataset["rows"].items():
        try:
            age = (now - _utc(row["t0"])).total_seconds() / 3600
            last = _utc(row["obs"][-1]["at"]) if row["obs"] else _utc(row["t0"])
        except (KeyError, TypeError, ValueError):
            continue
        if age > MAX_AGE_HOURS or row.get("status") == "VANISHED":
            continue
        pending = _pending(row, age)
        if not pending or (now - last).total_seconds() / 60 < MIN_GAP_MINUTES:
            continue
        queue.append((age - min(pending), key))
    return [key for _, key in sorted(queue, reverse=True)]


def reprice(dataset, fetch, now, *, max_batches=MAX_BATCHES_PER_RUN):
    """Price due rows in batches. Provider failure stops quietly; never raises."""
    report = {"due": 0, "attempted": 0, "priced": 0, "pool_not_returned": 0, "identity_mismatch": 0, "stopped": None}
    keys = due(dataset, now)
    report["due"] = len(keys)
    by_network = {}
    for key in keys:
        by_network.setdefault(key.split(":", 1)[0], []).append(key)
    batches = []
    queues = {n: list(v) for n, v in by_network.items()}
    while any(queues.values()):
        for network, items in queues.items():
            if items:
                batches.append((network, [items.pop(0) for _ in range(min(BATCH_SIZE, len(items)))]))
    stamp = now.astimezone(dt.timezone.utc).isoformat()
    for network, batch in batches[:max_batches]:
        url = f"{API}/networks/{network}/pools/multi/{','.join(k.split(':', 1)[1] for k in batch)}"
        try:
            payload = fetch(url)
        except ProviderRateLimited:
            report["stopped"] = "RATE_LIMITED"
            break
        except (OSError, ValueError):
            report["stopped"] = "PROVIDER_ERROR"
            break
        pools = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(pools, list):
            report["stopped"] = "MALFORMED_RESPONSE"
            break
        returned = {}
        for pool in pools:
            address = str(((pool or {}).get("attributes") or {}).get("address") or "")
            returned[address if network == "solana" else address.lower()] = pool
        for key in batch:
            report["attempted"] += 1
            row = dataset["rows"][key]
            address = key.split(":", 1)[1]
            pool = returned.get(address if network == "solana" else address.lower())
            age = (now - _utc(row["t0"])).total_seconds() / 3600
            pending = _pending(row, age)
            horizon = min(pending) if pending else None
            if pool is None:
                row["missing"] = int(row.get("missing", 0)) + 1
                row["status"] = "VANISHED" if row["missing"] >= 3 else "POOL_NOT_RETURNED"
                report["pool_not_returned"] += 1
                continue
            attrs = pool.get("attributes") or {}
            token_id = ((((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id") or "")
            actual = token_id[len(network) + 1:] if token_id.startswith(network + "_") else None
            same = actual == row["token_address"] if network == "solana" else (actual or "").lower() == row["token_address"].lower()
            if not same:
                row["status"] = "IDENTITY_MISMATCH"
                report["identity_mismatch"] += 1
                continue
            row["missing"] = 0
            row["status"] = "ACTIVE"
            price, liquidity = _num(attrs.get("base_token_price_usd")), _num(attrs.get("reserve_in_usd"))
            if price is None or price <= 0 or horizon is None:
                continue
            row["obs"].append({"at": stamp, "price": price, "liquidity": liquidity, "horizon": horizon,
                               "age_hours": round(age, 2)})
            report["priced"] += 1
    return report


def outcome(row, horizon=HORIZON_HOURS, cost=ASSUMED_COST_PERCENT):
    """Net return % at a horizon, or None if not yet measurable. Unexitable = -100."""
    try:
        t0 = _utc(row["t0"])
    except (KeyError, ValueError):
        return None
    for obs in row.get("obs", []):
        if obs.get("horizon") != horizon:
            continue
        liquidity = _num(obs.get("liquidity"))
        if liquidity is None or liquidity < UNEXITABLE_LIQUIDITY_USD:
            return -100.0
        return (obs["price"] / row["price0"] - 1) * 100 - cost
    if row.get("status") == "VANISHED" and (dt.datetime.now(dt.timezone.utc) - t0).total_seconds() / 3600 >= horizon:
        return -100.0
    return None


def wilson(wins, n, z=Z95):
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _labeled(dataset, horizon):
    rows = []
    for row in dataset["rows"].values():
        value = outcome(row, horizon)
        if value is not None:
            rows.append((row["t0"], row["features"], value))
    return sorted(rows, key=lambda r: r[0])


def _terciles(values):
    clean = sorted(v for v in values if v is not None)
    if len(clean) < 3 * MIN_BUCKET:
        return None
    return clean[len(clean) // 3], clean[2 * len(clean) // 3]


def _bucket(value, cuts):
    if value is None:
        return "missing"
    return "low" if value <= cuts[0] else "high" if value > cuts[1] else "mid"


def study(dataset, horizon=HORIZON_HOURS):
    """Look for features that separate winners, with out-of-sample validation."""
    labeled = _labeled(dataset, horizon)
    report = {"horizon_hours": horizon, "labeled": len(labeled), "minimum_total": MIN_TOTAL_LABELED,
              "tracked": len(dataset["rows"]), "patterns": [], "assumed_cost_percent": ASSUMED_COST_PERCENT,
              "definition": "win = net return above 0 after the assumed cost; unexitable pools count as -100%"}
    if labeled:
        returns = [v for _, _, v in labeled]
        report["base_win_rate"] = round(sum(v > 0 for v in returns) / len(returns), 3)
        report["median_net_return_percent"] = round(statistics.median(returns), 2)
    if len(labeled) < MIN_TOTAL_LABELED:
        report["conclusion"] = ("INSUFFICIENT SAMPLE: %d of %d outcomes measured; no pattern is reported"
                                % (len(labeled), MIN_TOTAL_LABELED))
        return report
    split = int(len(labeled) * 0.7)
    train, test = labeled[:split], labeled[split:]
    candidates = []
    for name in NUMERIC_FEATURES:
        cuts = _terciles([f[name] for _, f, _ in train])
        if cuts:
            for level in ("low", "mid", "high"):
                candidates.append((name, level, cuts))
    for name in CATEGORICAL_FEATURES:
        for level in sorted({f[name] for _, f, _ in train}):
            candidates.append((name, level, None))
    alpha_z = Z95 + 0.5 * math.log(max(len(candidates), 1))  # conservative multiple-comparison correction
    base_train = sum(v > 0 for _, _, v in train) / len(train)
    base_test = sum(v > 0 for _, _, v in test) / len(test)
    for name, level, cuts in candidates:
        def match(f):
            return (_bucket(f[name], cuts) if cuts else f[name]) == level
        in_train = [v for _, f, v in train if match(f)]
        in_test = [v for _, f, v in test if match(f)]
        if len(in_train) < MIN_BUCKET or len(in_test) < MIN_BUCKET:
            continue
        wins_train, wins_test = sum(v > 0 for v in in_train), sum(v > 0 for v in in_test)
        low_train, _ = wilson(wins_train, len(in_train), alpha_z)
        low_test, _ = wilson(wins_test, len(in_test), Z95)
        lift = (wins_test / len(in_test)) / base_test if base_test else 0
        if low_train > base_train and low_test > base_test and lift >= MIN_LIFT:
            report["patterns"].append({
                "feature": name, "level": level, "train_n": len(in_train), "test_n": len(in_test),
                "train_win_rate": round(wins_train / len(in_train), 3), "test_win_rate": round(wins_test / len(in_test), 3),
                "test_win_rate_lower_95": round(low_test, 3), "lift_vs_base": round(lift, 2),
                "test_median_net_return_percent": round(statistics.median(in_test), 2)})
    report["patterns"].sort(key=lambda p: -p["test_win_rate_lower_95"])
    report["conclusion"] = (
        "%d pattern(s) held on unseen later pools; still past correlation, not a forecast" % len(report["patterns"])
        if report["patterns"] else
        "No feature separated winners from losers on unseen later pools; do not infer a pattern")
    return report


def summary_line(report):
    line = "Pattern study (%dh): tracked %d, outcomes %d/%d. %s" % (
        report["horizon_hours"], report["tracked"], report["labeled"], report["minimum_total"], report["conclusion"])
    for pattern in report["patterns"][:3]:
        line += "; %s=%s test win %.0f%% (n=%d)" % (pattern["feature"], pattern["level"],
                                                    pattern["test_win_rate"] * 100, pattern["test_n"])
    return line
