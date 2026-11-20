"""Fail-closed, pure screening of asymmetric-upside research candidates.

No market data is fetched, no BUY is authorized, and score is not a probability.
Input observations must be independently collected and dated upstream.
"""
import math
from datetime import datetime, timezone

WEIGHTS = {"fundamentals": 25, "tokenomics": 20, "liquidity_security": 20,
           "adoption_catalysts": 20, "early_momentum": 15}
REQUIRED = ("chain", "contract", "source_url", "observed_at", "market_cap_usd",
            "fdv_usd", "volume_24h_usd", "liquidity_usd")


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def evaluate(record, now=None):
    """Return a research-only disposition with explicit blockers."""
    if not isinstance(record, dict):
        raise TypeError("record must be dict")
    now = now or datetime.now(timezone.utc)
    blockers = [f"missing:{k}" for k in REQUIRED if record.get(k) in (None, "")]
    for key in ("market_cap_usd", "fdv_usd", "volume_24h_usd", "liquidity_usd"):
        if not _positive(record.get(key)):
            blockers.append(f"invalid:{key}")
    if record.get("source_url") and not str(record["source_url"]).startswith("https://"):
        blockers.append("invalid:source_url")
    try:
        observed = datetime.fromisoformat(str(record.get("observed_at", "")).replace("Z", "+00:00"))
        if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 86400:
            blockers.append("stale_or_future_observation")
    except ValueError:
        blockers.append("invalid:observed_at")
    cap = record.get("market_cap_usd")
    if _positive(cap) and not 5_000_000 <= cap <= 500_000_000:
        blockers.append("outside_market_cap_range")
    if _positive(cap) and _positive(record.get("fdv_usd")) and record["fdv_usd"] / cap > 5:
        blockers.append("high_dilution")
    if _positive(cap) and _positive(record.get("liquidity_usd")) and record["liquidity_usd"] / cap < .01:
        blockers.append("thin_liquidity")
    if record.get("security_verified") is not True:
        blockers.append("security_unverified")
    if record.get("supply_verified") is not True:
        blockers.append("supply_unverified")
    if record.get("identity_verified") is not True:
        blockers.append("identity_unverified")
    scores = record.get("scores", {})
    valid_scores = isinstance(scores, dict) and all(
        isinstance(scores.get(k), (int, float)) and not isinstance(scores.get(k), bool)
        and math.isfinite(scores[k]) and 0 <= scores[k] <= maximum
        for k, maximum in WEIGHTS.items())
    if not valid_scores:
        blockers.append("scores_unverified")
    total = sum(scores[k] for k in WEIGHTS) if valid_scores else None
    return {"classification": "RESEARCH WATCH", "eligible_for_rank": not blockers,
            "score_out_of_100": total, "blockers": sorted(set(blockers)),
            "scenario_market_caps_usd": {str(mult)+"x": cap * mult for mult in (10, 50, 100)}
            if _positive(cap) else {}, "buy_authorized": False,
            "probability_of_100x": None}
