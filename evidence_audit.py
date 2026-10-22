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
    # Boolean flags alone are not independently verifiable evidence.
    # Reserve PASS for future source-bound adapter results, not caller assertions.
    checks["sellability"] = "UNKNOWN"
    checks["liquidity_lock"] = "UNKNOWN"
    checks["holder_distribution"] = "UNKNOWN"
    checks["tokenomics_unlocks"] = "UNKNOWN"
    checks["execution_quote"] = "UNKNOWN"
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
    # Adapter diagnostics can veto a candidate, but LIMITED never becomes PASS.
    for key, record in item.get("verification", {}).items():
        if isinstance(record, dict):
            checks["independent_" + key] = ("FAIL" if record.get("status") == "CONFLICTING" else record.get("status", "UNKNOWN") if record.get("status") in ("FAIL", "LIMITED", "UNKNOWN", "WAIT") else "UNKNOWN")
    failures = [k for k, v in checks.items() if v == "FAIL"]
    unknown = [k for k, v in checks.items() if v == "UNKNOWN"]
    return {
        "checks": checks,
        "failures": failures,
        "unknown": unknown,
        "research_status": "REJECT" if failures else "INVESTIGATE",
        "trade_ready": False,
        "reason": "Mandatory independent evidence is incomplete; limited observations and disclosures cannot authorize a verified BUY",
    }


def summary(report):
    return ("EVIDENCE AUDIT: " +
            "; ".join(f"{key}={value}" for key, value in report["checks"].items()) +
            "\nTRADE READY: NO — " + report["reason"])
