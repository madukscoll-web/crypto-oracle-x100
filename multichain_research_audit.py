"""Conservative reporting of live discovery coverage; never issues investment signals."""
from collections import Counter

def audit(report):
    if not isinstance(report, dict) or report.get("mode") != "READ_ONLY_RESEARCH":
        raise ValueError("Expected read-only research report")
    selected = report.get("selected")
    if not isinstance(selected, list):
        raise ValueError("Missing selected candidates")
    counts = Counter()
    for row in selected:
        if not isinstance(row, dict) or not isinstance(row.get("network"), str):
            raise ValueError("Invalid selected candidate")
        counts[row["network"]] += 1
    failures = report.get("failures", [])
    if not isinstance(failures, list):
        raise ValueError("Invalid failure ledger")
    return {"scope": "DISCOVERY_ONLY",
            "selected_by_chain": dict(sorted(counts.items())),
            "selected_total": len(selected),
            "discovery_sources": report.get("discovery_sources", {}),
            "launchpad_direct_feeds_active": report.get("launchpad_direct_feeds_active", []),
            "launchpad_origin_verified_count": 0,
            "discovery_failure_count": len(failures),
            "unassessed_count": report.get("deferred", 0),
            "verified_buy_count": 0,
            "buy_authorized": False,
            "missing_verification": [
                "independent_security_review",
                "beneficial_owner_concentration",
                "circulating_supply_and_unlocks",
                "pool_control_and_executable_sellability",
                "fresh_funded_execution_evidence",
                "human_reviewed_entry_and_risk_limits"
            ],
            "telegram_eligible": False}
