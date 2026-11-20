"""Token-identity statuses the alert gates accept. One list, used by every gate.

Both entries mean the same thing: the exact requested pool, on the exact chain,
returned an explicit base-token address from that provider. DexScreener was added
(owner decision) because GeckoTerminal rate limits left candidates UNVERIFIED.
This list governs identity only; every other gate (security, LP, holders,
sellability, freshness, BUY admission) is unchanged.
"""
VERIFIED_IDENTITY_STATUSES = frozenset({
    "Base token from GeckoTerminal pool relationship",
    "Base token from DexScreener pool relationship",
})


def identity_verified(item):
    return (item or {}).get("token_identity_status") in VERIFIED_IDENTITY_STATUSES
