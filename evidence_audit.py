"""Conservative evidence audit for research leads.

No missing field can become a pass. This is deliberately not a contract audit,
execution simulator, or authorization to buy.
"""
import identity_sources
import math
import adverse_evidence


def audit(item):
    import authenticated_admission
    admission = authenticated_admission.evaluate(item)
    checks = {}
    checks["token_identity"] = "PASS" if (
        identity_sources.identity_verified(item) and
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
        if any(isinstance(item.get(key), bool) for key in ('liquidity', 'volume')):
            raise ValueError('Boolean market measurement')
        liquidity = float(item.get("liquidity"))
        volume = float(item.get("volume"))
    except (TypeError, ValueError, OverflowError):
        liquidity, volume = float('nan'), float('nan')
    checks["market_depth"] = (
        "PASS" if math.isfinite(liquidity) and math.isfinite(volume)
        and liquidity >= 250000 and volume >= 300000 else
        "FAIL" if math.isfinite(liquidity) and math.isfinite(volume)
        and liquidity >= 0 and volume >= 0 else "UNKNOWN"
    )
    # An explicit independent supply conflict is adverse, never merely unknown.
    report = item.get('verification')
    report = report if isinstance(report, dict) else {}
    supply = report.get('supply_comparison')
    supply = supply if isinstance(supply, dict) else {}
    checks["independent_supply_comparison"] = (
        "FAIL" if supply.get("status") in ("FAIL", "CONFLICTING", "HIGH CONCERN")
        else "UNKNOWN"
    )
    checks["entry_pattern"] = (
        "LIMITED" if item.get("entry_pattern") in ("MOMENTUM WATCH", "PULLBACK WATCH")
        else "UNKNOWN"
    )
    adverse = adverse_evidence.findings(item)
    aliases = {'sellability': 'sellability', 'honeypot': 'sellability',
               'liquidity': 'liquidity_lock', 'holders': 'holder_distribution',
               'tokenomics': 'tokenomics_unlocks', 'unlocks': 'tokenomics_unlocks',
               'execution': 'execution_quote', 'execution_checks': 'execution_quote',
               'kyber': 'execution_quote', 'kyber_execution': 'execution_quote'}
    for name in adverse:
        checks[aliases.get(name, name)] = 'FAIL'
    if admission['safety_verified']:
        checks['token_identity'] = checks['provider_risk'] = checks['market_depth'] = 'PASS'
        for name in ('sellability', 'liquidity_lock', 'holder_distribution',
                     'tokenomics_unlocks', 'execution_quote', 'independent_supply_comparison'):
            checks[name] = 'PASS'
        checks['contract_security'] = 'PASS'
    failures = [k for k, v in checks.items() if v == "FAIL"]
    unknown = [k for k, v in checks.items() if v == "UNKNOWN"]
    return {
        "checks": checks,
        "failures": failures,
        "unknown": unknown,
        "adverse_evidence": adverse,
        "research_status": "REJECT" if failures else "INVESTIGATE",
        "trade_ready": admission['admitted'],
        "admission": admission,
        "reason": "Independent signed evidence and execution invariants passed; manual review required" if admission['admitted'] else "Signed safety verified; entry monitoring required" if admission['safety_verified'] else "; ".join(admission['blockers']),
    }


def summary(report):
    return ("EVIDENCE AUDIT: " +
            "; ".join(f"{key}={value}" for key, value in report["checks"].items()) +
            "\nTRADE READY: " + ("YES — MANUAL REVIEW — " if report['trade_ready'] else "NO — ") + report["reason"])

