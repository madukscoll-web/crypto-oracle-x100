"""Conservative launchpad provenance for multichain research observations.

Only source-labelled, contract-bound records are accepted. Pool appearance on
GeckoTerminal is not evidence that a token launched on a particular platform.
This module does not fetch feeds, trade, or authorize a BUY.
"""
SUPPORTED = {
    "pump.fun": "solana",
    "stonk": "solana",
    "letsbonk.fun": "solana",
    "four.meme": "bsc",
}


def attribute_launchpad(record):
    if not isinstance(record, dict):
        return {"platform": "UNKNOWN", "status": "UNVERIFIED"}
    platform = str(record.get("platform", "")).strip().lower()
    chain = str(record.get("network", "")).strip().lower()
    contract = str(record.get("contract", "")).strip()
    origin = str(record.get("origin_url", "")).strip()
    if (platform not in SUPPORTED or SUPPORTED[platform] != chain
            or not contract or not origin.startswith("https://")):
        return {"platform": "UNKNOWN", "status": "UNVERIFIED"}
    # Source URLs are self-asserted, not independently authenticated.
    return {"platform": platform, "status": "CLAIMED — INDEPENDENT VERIFICATION REQUIRED",
            "network": chain, "contract": contract, "origin_url": origin}
