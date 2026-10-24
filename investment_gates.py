"""Source-aware, fail-closed research assessments; never authorizes an order."""
import datetime as dt
import math
import os

def _positive(value):
    try:
        x = float(value)
        return x if math.isfinite(x) and x > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None

def _threshold(name, default):
    x = _positive(os.environ.get(name))
    return x if x is not None else default

def assess(item):
    """Missing independent evidence is UNKNOWN, not zero or PASS."""
    blockers = []
    warnings = []
    risk = item.get("risk_category", "WAIT / VERIFY")
    if risk == "AVOID / HIGH CONCERN":
        blockers.append("Critical provider security flag: independently investigate")
    if item.get("token_identity_status") != "Base token from GeckoTerminal pool relationship":
        blockers.append("Exact base-token identity unverified")
    if item.get("security_source", "").startswith("GoPlus") is False:
        blockers.append("Provider security assessment unavailable")
    # Provider observations are never substituted for independent verification.
    for field, name in (("sellability_verified", "independent sellability"),
                        ("liquidity_lock_verified", "LP withdrawal controls"),
                        ("holder_distribution_verified", "adjusted top holders"),
                        ("tokenomics_verified", "supply and vesting"),
                        ("executable_quote_verified", "executable quote"),
                        ("slippage_verified", "slippage"),
                        ("entry_risk_reviewed", "technical entry and downside")):
        if item.get(field) is not True:
            blockers.append(name + " not verified")
    liquidity = _positive(item.get("liquidity"))
    volume = _positive(item.get("volume"))
    if liquidity and volume:
        ratio = volume / liquidity
        if ratio > _threshold("ORACLE_VOLUME_LIQUIDITY_WARNING", 10):
            warnings.append(f"24h volume/liquidity {ratio:.1f}x: authenticity requires investigation")
    else:
        blockers.append("Positive pool liquidity and volume unavailable")
    cap = _positive(item.get("market_cap_usd"))
    fdv = _positive(item.get("fdv_usd"))
    if cap and fdv and fdv / cap > _threshold("ORACLE_DILUTION_WARNING", 5):
        warnings.append(f"FDV/circulating cap {fdv/cap:.1f}x: potential dilution")
    elif cap is None or fdv is None:
        blockers.append("Market capitalization or FDV unverified")
    circulating = _positive(item.get("circulating_supply"))
    maximum = _positive(item.get("max_supply"))
    if circulating is None or maximum is None:
        blockers.append("Circulating/maximum supply unverified")
    elif circulating > maximum:
        blockers.append("Conflicting supply: circulating exceeds maximum")
    holder_pct = item.get("adjusted_top10_fraction")
    if holder_pct is None or item.get("holder_exclusions_verified") is not True:
        blockers.append("Top-holder concentration excluding LP/CEX/burn unverified")
    else:
        try:
            h = float(holder_pct)
            if not 0 <= h <= 1:
                blockers.append("Invalid adjusted holder concentration")
            elif h > _threshold("ORACLE_TOP10_WARNING", .5):
                warnings.append(f"Adjusted top-ten holders control {h:.0%}")
        except (ValueError, TypeError):
            blockers.append("Invalid adjusted holder concentration")
    unlock = item.get("next_unlock_utc")
    if not unlock or item.get("unlock_source_verified") is not True:
        blockers.append("Next unlock/vesting schedule unverified")
    else:
        try:
            t = dt.datetime.fromisoformat(str(unlock).replace("Z", "+00:00"))
            if t.tzinfo is None:
                raise ValueError("Timezone required")
            days = (t - dt.datetime.now(dt.timezone.utc)).total_seconds()/86400
            if 0 <= days <= _threshold("ORACLE_UNLOCK_WARNING_DAYS", 30):
                warnings.append(f"Upcoming token unlock in {days:.1f} days")
        except (ValueError, TypeError, OverflowError):
            blockers.append("Invalid unlock timestamp")
    quote = item.get("execution_evidence")
    if not isinstance(quote, dict):
        blockers.append("Exact-pool fresh executable quote unavailable")
    else:
        spread = _positive(quote.get("spread_percent"))
        depth = _positive(quote.get("depth_usd"))
        if spread is None:
            blockers.append("Spread unverified or crossed")
        elif spread > _threshold("ORACLE_SPREAD_WARNING_PERCENT", 1):
            warnings.append(f"Wide bid/ask spread {spread:.2f}%")
        if depth is None:
            blockers.append("Executable depth unverified")
        elif depth < _threshold("ORACLE_MIN_DEPTH_USD", 1000):
            warnings.append(f"Thin executable depth ${depth:,.0f}")
    return {
        "activity": {"score": item.get("score"), "meaning": "Observed pool activity ONLY; not safety"},
        "security": "HIGH CONCERN" if risk == "AVOID / HIGH CONCERN" else "INCOMPLETE",
        "fundamentals": "INCOMPLETE" if any("supply" in x or "FDV" in x or "unlock" in x for x in blockers) else "REVIEW",
        "trade_readiness": "NOT VERIFIED",
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": warnings,
        "buy_eligible": False,
        "provenance": {"provider": item.get("source", "UNKNOWN"), "network": item.get("network"),
                       "pool": item.get("address"), "token": item.get("token_address"),
                       "observed_utc": item.get("observed_at")},
    }

def telegram_summary(item):
    result = assess(item)
    lines = ["EVIDENCE GATES: Activity is NOT safety.",
             "Security: " + result["security"],
             "Fundamentals/dilution: " + result["fundamentals"],
             "Trade readiness: NOT VERIFIED — no automatic BUY",
             "BLOCKERS: " + "; ".join(result["blockers"][:5])]
    if len(result["blockers"]) > 5:
        lines.append(f"Plus {len(result['blockers'])-5} further evidence gaps")
    if result["warnings"]:
        lines.append("WARNINGS: " + "; ".join(result["warnings"][:3]))
    return "\n".join(lines)
