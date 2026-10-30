"""Solana evidence gap triage, without altering production BUY authorization.

Consumes solana_evidence.collect observations. Do not treat largest token accounts
as unique holders, a mint authority check as a security audit, or gross supply
as circulating supply.
"""
from multichain_rollout_policy import eligible_for_buy

SOLANA_GATES = ("onchain", "contract_security", "holders", "supply_comparison",
                "sellability", "liquidity", "execution")

def triage(report):
    if not isinstance(report, dict):
        raise ValueError("Solana evidence report must be a dictionary")
    gates = {}
    for name in SOLANA_GATES:
        entry = report.get(name)
        status = entry.get("status", "UNKNOWN") if isinstance(entry, dict) else "NOT_CHECKED"
        reason = entry.get("reason", "Collector did not provide evidence") if isinstance(entry, dict) else "Collector did not provide evidence"
        gates[name] = {"status": status, "reason": reason}
    checks = ((report.get("onchain") or {}).get("checks") or {})
    authority = {name: (checks.get(name) or {}).get("status", "NOT_CHECKED")
                 for name in ("legacy_spl_mint_identity", "mint_authority_revoked",
                              "freeze_authority_revoked")}
    blockers = []
    if any(value == "FAILED" for value in authority.values()):
        blockers.append("Active or adverse mint/freeze authority: reject under conservative policy")
    if gates["onchain"]["status"] == "UNSUPPORTED":
        blockers.append("Unsupported mint program, including unreviewed Token-2022 extensions")
    for name in SOLANA_GATES:
        if gates[name]["status"] != "VERIFIED":
            blockers.append(name + ": " + gates[name]["status"])
    prerequisites = eligible_for_buy("solana", {})
    return {"network": "solana", "status": "REJECT" if any(v == "FAILED" for v in authority.values()) else "RESEARCH_ONLY",
            "authority_checks": authority, "gates": gates, "blockers": blockers,
            "missing_chain_prerequisites": prerequisites["missing"],
            "buy_authorized": False, "orders_allowed": False}
