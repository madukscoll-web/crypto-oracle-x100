"""Deterministic, read-only candidate rotation across supported networks.

Discovery priority is NOT a safety score or BUY approval. Rotation prevents
high-volume chains from consuming every research slot. Planned chains stay
disabled until a reviewed production adapter exists.
"""
from collections import defaultdict
from multichain_rollout_policy import plan

def rotate(candidates, per_run=12, cursor=0, enabled=("solana", "eth", "base", "bsc")):
    if type(per_run) is not int or not 1 <= per_run <= 100:
        raise ValueError("per_run must be between 1 and 100")
    if type(cursor) is not int or cursor < 0:
        raise ValueError("cursor must be a nonnegative integer")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    groups = defaultdict(list)
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        network, address = candidate.get("network"), candidate.get("token_address")
        chain = plan(network)
        if chain is None or chain.stage == "planned" or network not in enabled:
            continue
        if not isinstance(address, str) or not address:
            continue
        # This is only a research queue; downstream collectors must canonicalize
        # and verify exact token identity before accepting evidence.
        identity = (network, address)
        if identity in seen:
            continue
        seen.add(identity)
        groups[network].append(candidate)
    order = sorted(groups, key=lambda n: plan(n).priority)
    if not order:
        return {"selected": [], "next_cursor": cursor, "deferred": 0,
                "buy_authorized": False}
    # Shift the starting chain each run while retaining chain priority ordering.
    offset = cursor % len(order)
    order = order[offset:] + order[:offset]
    selected = []
    positions = {network: 0 for network in order}
    while len(selected) < per_run:
        progressed = False
        for network in order:
            index = positions[network]
            if index < len(groups[network]) and len(selected) < per_run:
                selected.append(groups[network][index])
                positions[network] += 1
                progressed = True
        if not progressed:
            break
    return {"selected": selected, "next_cursor": cursor + 1,
            "deferred": sum(map(len, groups.values())) - len(selected),
            "buy_authorized": False}
