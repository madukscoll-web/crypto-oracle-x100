"""Conservative evidence audit for research leads.

No missing field can become a pass. This is deliberately not a contract audit,
execution simulator, or authorization to buy.
"""
import math


def audit(item):
    checks = {}
    checks["token_identity"] = "PASS" if (
        item.get("token_identity_status") ==
        "Base token from GeckoTerminal pool relationship" and
        item.get("token_address") not in (None, "", "UNVERIFIED")
    ) else "UNKNOWN"
    checks["provider_risk"] = (
        "FAIL" if item.get("risk_category") == "AVOID / HIGH CONCERN"
        else "LIMITED" if item.get("risk_category") ==
        "RESEARCH CANDIDATE — LIMITED CHECKS" else "UNKNOWN"
    )
    checks["sellability"] = "PASS" if item.get("sellability_verified") is True else "UNKNOWN"
    checks["liquidity_lock"] = "PASS" if item.get("liquidity_lock_verified") is True else "UNKNOWN"
    checks["holder_distribution"] = "PASS" if item.get("holder_distribution_verified") is True else "UNKNOWN"
    checks["tokenomics_unlocks"] = "PASS" if item.get("tokenomics_verified") is True else "UNKNOWN"
    checks["execution_quote"] = "PASS" if (
        item.get("executable_quote_verified") is True and
        item.get("slippage_verified") is True
    ) else "UNKNOWN"
    try:
        liquidity = float(item.get("liquidity", 0))
        volume = float(item.get("volume", 0))
    except (TypeError, ValueError):
        liquidity, volume = 0, 0
    checks["market_depth"] = (
        "PASS" if math.isfinite(liquidity) and math.isfinite(volume)
        and liquidity >= 250000 and volume >= 300000 else "FAIL"
    )
    checks["entry_pattern"] = (
        "LIMITED" if item.get("entry_pattern") in ("MOMENTUM WATCH", "PULLBACK WATCH")
        else "UNKNOWN"
    )
    failures = [k for k, v in checks.items() if v == "FAIL"]
    unknown = [k for k, v in checks.items() if v == "UNKNOWN"]
    return {
        "checks": checks,
        "failures": failures,
        "unknown": unknown,
        "research_status": "REJECT" if failures else "INVESTIGATE",
        "trade_ready": False,
        "reason": "Independent sellability, liquidity, holder, tokenomics and executable quotes not integrated",
    }


def summary(report):
    return ("EVIDENCE AUDIT: " +
            "; ".join(f"{key}={value}" for key, value in report["checks"].items()) +
            "\nTRADE READY: NO — " + report["reason"])
