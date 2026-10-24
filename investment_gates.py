"""Source-aware, fail-closed research assessments; never authorizes an order."""
import datetime as dt
import math
import os

def _positive(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
        return x if math.isfinite(x) and x > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None

def _threshold(name, default):
    x = _positive(os.environ.get(name))
    return x if x is not None else default

def assess(item, now=None):
    """Missing independent evidence is UNKNOWN, not zero or PASS."""
    now = now or dt.datetime.now(dt.timezone.utc)
    blockers = []
    warnings = []
    risk = item.get("risk_category", "WAIT / VERIFY")
    review = item.get("evidence_review") or {}
    if any((review.get(key) or {}).get("status") == "HIGH CONCERN" for key in ("security", "provider_security")):
        risk = "AVOID / HIGH CONCERN"
    if risk == "AVOID / HIGH CONCERN":
        blockers.append("Critical provider security flag: independently investigate")
    if item.get("token_identity_status") != "Base token from GeckoTerminal pool relationship":
        blockers.append("Exact base-token identity unverified")
    if not str(item.get("security_source") or "").startswith("GoPlus token_security API"):
        blockers.append("Provider security assessment unavailable")
    # Provider observations are never substituted for independent verification.
    for field, name in (("sellability_verified", "independent sellability"),
                        ("liquidity_lock_verified", "LP withdrawal controls"),
                        ("holder_distribution_verified", "adjusted top holders"),
                        ("tokenomics_verified", "supply and vesting"),
                        ("executable_quote_verified", "executable quote"),
                        ("slippage_verified", "slippage"),
                        ("entry_risk_reviewed", "technical entry and downside")):
        # Caller booleans cannot establish independently sourced evidence.
        blockers.append(name + " not verified")
    # Explicitly preserve every source-bound field, including failures.
    evidence = item.get("fundamental_evidence") or {}
    for field in ("circulating_supply", "total_supply", "max_supply", "market_cap_usd",
                  "fdv_usd", "unlocks", "adjusted_top10_fraction", "adoption",
                  "lp_controls", "independent_security", "execution_quote"):
        record = evidence.get(field) or {}
        # No independently authenticated verification adapter is configured.
        blockers.append(field + ": " + ("CONFLICTING" if record.get("status") == "CONFLICTING" else "UNVERIFIED"))
    for field, reviewed in (review.get("supply") or {}).items():
        if reviewed.get("status") == "CONFLICTING":
            blockers.append("Independent " + field + " sources CONFLICTING")
    liquidity = _positive(item.get("liquidity"))
    volume = _positive(item.get("volume"))
    if liquidity and volume:
        ratio = volume / liquidity
        if ratio > _threshold("ORACLE_VOLUME_LIQUIDITY_WARNING", 10):
            warnings.append(f"24h volume/liquidity {ratio:.1f}x: authenticity requires investigation")
    else:
        blockers.append("Positive pool liquidity and volume unavailable")
    def observed(field):
        value = (evidence.get(field) or {}).get("value")
        return value if value is not None else item.get(field)
    cap = _positive(observed("market_cap_usd"))
    fdv = _positive(observed("fdv_usd"))
    if cap and fdv and fdv / cap > _threshold("ORACLE_DILUTION_WARNING", 5):
        warnings.append(f"FDV/circulating cap {fdv/cap:.1f}x: potential dilution")
    elif cap is None or fdv is None:
        blockers.append("Market capitalization or FDV unverified")
    circulating = _positive(observed("circulating_supply"))
    maximum = _positive(observed("max_supply"))
    if circulating is None or maximum is None:
        blockers.append("Circulating/maximum supply unverified")
    elif circulating > maximum:
        blockers.append("Conflicting supply: circulating exceeds maximum")
    holder_pct = item.get("adjusted_top10_fraction")
    if holder_pct is None or item.get("holder_exclusions_verified") is not True:
        blockers.append("Top-holder concentration excluding LP/CEX/burn unverified")
    else:
        try:
            if isinstance(holder_pct, bool):
                raise ValueError("Boolean is not concentration")
            h = float(holder_pct)
            if not 0 <= h <= 1:
                blockers.append("Invalid adjusted holder concentration")
            elif h > _threshold("ORACLE_TOP10_WARNING", .5):
                warnings.append(f"Adjusted top-ten holders control {h:.0%} (UNVERIFIED claim)")
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
            days = (t - now).total_seconds()/86400
            if 0 <= days <= _threshold("ORACLE_UNLOCK_WARNING_DAYS", 30):
                warnings.append(f"Upcoming token unlock in {days:.1f} days")
        except (ValueError, TypeError, OverflowError):
            blockers.append("Invalid unlock timestamp")
    # Any claimed external quote must be bound to the same observed asset and pool.
    quote = item.get("execution_evidence")
    if isinstance(quote, dict):
        for source_key, item_key in (("network", "network"), ("pool_address", "address"),
                                     ("token_address", "token_address")):
            a, b = quote.get(source_key), item.get(item_key)
            if not a or not b or str(a).lower() != str(b).lower():
                blockers.append(f"Execution evidence {source_key} mismatched or absent")
        observed = quote.get("observed_at")
        try:
            t = dt.datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
            if t.tzinfo is None:
                raise ValueError("Timezone required")
            age = (now - t).total_seconds()
            if age < 0 or age > _threshold("ORACLE_QUOTE_MAX_AGE_SECONDS", 120):
                blockers.append("Executable quote stale or future-dated")
        except (ValueError, TypeError, OverflowError):
            blockers.append("Executable quote timestamp missing or invalid")
        if not quote.get("source_url") or not quote.get("source"):
            blockers.append("Executable quote source provenance missing")
    if not isinstance(quote, dict):
        blockers.append("Exact-pool fresh executable quote unavailable")
    else:
        from fundamental_evidence import finite
        spread = finite(quote.get("spread_percent"))
        depth = _positive(quote.get("depth_usd"))
        if spread is None:
            blockers.append("Spread unverified or crossed")
        elif spread > _threshold("ORACLE_SPREAD_WARNING_PERCENT", 1):
            warnings.append(f"Wide bid/ask spread {spread:.2f}%")
        if depth is None:
            blockers.append("Executable depth unverified")
        elif depth < _threshold("ORACLE_MIN_DEPTH_USD", 1000):
            warnings.append(f"Thin executable depth ${depth:,.0f}")
    if item.get("unlock_amount") is not None:
        amount = _positive(item.get("unlock_amount"))
        if amount is None or circulating is None:
            blockers.append("Unlock amount/circulating supply UNVERIFIED")
        elif amount / circulating > _threshold("ORACLE_UNLOCK_FRACTION_WARNING", .1):
            warnings.append(f"Large claimed unlock: {amount/circulating:.1%} of circulating supply (UNVERIFIED)")
    if isinstance(quote, dict):
        blockers.append("Quote authenticity and exact route/sellability UNVERIFIED")
        bid, ask = _positive(quote.get("bid")), _positive(quote.get("ask"))
        if bid is None or ask is None or bid > ask:
            blockers.append("Bid/ask UNVERIFIED or crossed")
        from fundamental_evidence import finite
        slip = finite(quote.get("slippage_percent"))
        if slip is None:
            blockers.append("Slippage UNVERIFIED")
        elif slip > _threshold("ORACLE_SLIPPAGE_WARNING_PERCENT", 2):
            warnings.append(f"High claimed slippage {slip:.2f}% (UNVERIFIED)")
    reviewed_unlock = review.get("unlocks") or {}
    if reviewed_unlock.get("large_unlock"):
        warnings.append("Large upcoming corroborated unlock: " + str(reviewed_unlock.get("fraction")) + " of circulating supply; enforceability UNVERIFIED")
    reviewed_holders = review.get("holders") or {}
    if reviewed_holders.get("excessive"):
        warnings.append("Excessive adjusted holder concentration: " + str(reviewed_holders.get("adjusted_top10_fraction")) + "; snapshot authenticity UNVERIFIED")
    for flag in (review.get("execution") or {}).get("flags", []):
        warnings.append("Quote observation: " + flag)
    return {
        "source_review": review,
        "decision": "AVOID / HIGH CONCERN" if risk == "AVOID / HIGH CONCERN" else "WAIT / VERIFY",
        "evidence": evidence,
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
    from fundamental_evidence import scenario_summary
    lines = ["DECISION: " + result["decision"],
             "EVIDENCE GATES: Activity is NOT safety.",
             "Security: " + result["security"],
             "Fundamentals/dilution: " + result["fundamentals"],
             "Trade readiness: NOT VERIFIED — no automatic BUY",
             "BLOCKERS: " + "; ".join(result["blockers"][:5])]
    if len(result["blockers"]) > 5:
        lines.append(f"Plus {len(result['blockers'])-5} further evidence gaps")
    if result["warnings"]:
        lines.append("WARNINGS: " + "; ".join(result["warnings"][:3]))
    lines.append("Supply / unlocks / adjusted holders / adoption / LP controls / execution: UNVERIFIED")
    lines.append("Pool source: " + str(item.get("source", "UNVERIFIED")) + "; observed: " + str(item.get("observed_at", "UNVERIFIED")))
    provider = item.get("security_provider_evidence") or {}
    lines.append("Security: GoPlus provider data, NOT audit; observed: " + str(provider.get("retrieved_utc", "UNVERIFIED")))
    records = result["evidence"]
    if records:
        r = records.get("circulating_supply") or {}
        lines.append("Fundamentals: " + str(r.get("provider", "UNVERIFIED")) + "; retrieved: " + str(r.get("observed_at", "UNVERIFIED")))
        lines.append("Reported circulating / max supply: " + str(r.get("value", "UNVERIFIED")) + " / " + str((records.get("max_supply") or {}).get("value", "UNVERIFIED")) + " (UNVERIFIED)")
    lines.append("Offline source review: " + str(item.get("research_record_status", "UNVERIFIED")))
    lines.append(scenario_summary())
    return "\n".join(lines)

