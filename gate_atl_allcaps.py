"""Read-only all-cap Gate ATL screening. Provider lows are NOT verified lifetime lows.

This module does not issue Telegram messages or authorize BUY. Exact identity
mapping must be supplied by the independent verification pipeline.
"""
from decimal import Decimal
from atl_monitor_core import positive

MAX_DISTANCE_PERCENT = Decimal("20")


def market_cap_bucket(value):
    cap = positive(value)
    if cap is None:
        return "UNVERIFIED"
    if cap < 10_000_000:
        return "MICRO_CAP"
    if cap < 200_000_000:
        return "LOW_CAP"
    if cap <= 1_000_000_000:
        return "MID_CAP"
    return "HIGH_CAP"


def screen(pairs, tickers, provider_assets, identity_matches):
    """Screen active ordinary Gate USDT Spot pairs against provider-reported ATL.

    identity_matches: mapping of Gate base symbol -> *unique* provider ID, built
    from exact contract/chain checks elsewhere; never infer identity by ticker.
    Every result remains UNVERIFIED until independently corroborated.
    """
    if not all(isinstance(x, list) for x in (pairs, tickers, provider_assets)):
        raise ValueError("Expected provider lists")
    if not isinstance(identity_matches, dict):
        raise ValueError("Exact identity mapping required")
    quotes = {t.get("currency_pair"): t for t in tickers if isinstance(t, dict)}
    assets = {a.get("id"): a for a in provider_assets if isinstance(a, dict) and isinstance(a.get("id"), str)}
    results = []
    counts = {"pairs_checked": 0, "identity_unresolved": 0, "history_unverified": 0,
              "outside_threshold": 0, "near_atl_unverified": 0}
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        if (pair.get("quote") != "USDT" or pair.get("type") != "normal"
                or pair.get("trade_status") != "tradable" or pair.get("st_tag") is True
                or pair.get("delisting_time") not in (None, 0)):
            continue
        counts["pairs_checked"] += 1
        symbol, pair_id = pair.get("base"), pair.get("id")
        if pair_id != str(symbol) + "_USDT":
            counts["identity_unresolved"] += 1
            continue
        provider_id = identity_matches.get(symbol)
        if not isinstance(provider_id, str) or provider_id not in assets:
            counts["identity_unresolved"] += 1
            continue
        market = assets[provider_id]
        quote = quotes.get(pair_id, {})
        price, low = positive(quote.get("last")), positive(market.get("atl"))
        if price is None or low is None or not market.get("atl_date"):
            counts["history_unverified"] += 1
            continue
        distance = (price / low - 1) * 100
        if distance < 0:
            counts["history_unverified"] += 1
            continue
        if distance > MAX_DISTANCE_PERCENT:
            counts["outside_threshold"] += 1
            continue
        cap = positive(market.get("market_cap"))
        results.append({"gate_pair": pair_id, "provider_id": provider_id,
                        "price_usdt": str(price), "provider_atl_usd": str(low),
                        "provider_atl_date": market["atl_date"],
                        "distance_percent": str(distance),
                        "market_cap_usd": str(cap) if cap else None,
                        "cap_category": market_cap_bucket(cap),
                        "status": "PROVIDER_ATL_UNVERIFIED",
                        "lifetime_verified": False, "telegram_eligible": False,
                        "buy_authorized": False})
        counts["near_atl_unverified"] += 1
    results.sort(key=lambda x: (Decimal(x["distance_percent"]), x["gate_pair"]))
    return {"schema_version": 1, "threshold_percent": 20,
            "scope": "GATE_ACTIVE_NORMAL_USDT_SPOT",
            "coverage_complete": False, "global_atl_verified": False,
            "orders_allowed": False, "buy_authorized": False,
            "counts": counts, "candidates": results}
