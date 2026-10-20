"""Deterministic evidence-based Gate spot entry assessment.

Read-only analysis, not a buy signal, forecast, stop order, or trade authorization.
"""
import datetime as dt
import math

from gate_spot_research import finite_positive

MAX_SNAPSHOT_AGE_SECONDS = 120
MAX_SPREAD_PERCENT = 0.8
MIN_DEPTH_USDT = 5000
MAX_CHASE_PERCENT = 15
MAX_DOWNSIDE_PERCENT = 10


def _utc_time(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(dt.timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def assess_entry(proposal, independent_evidence=None, now=None):
    """Return actionable research gaps, never an executable recommendation.

    This function deliberately does not trust caller-supplied verification
    booleans as proof of authenticated security or executable order quotes.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware now required")
    now = now.astimezone(dt.timezone.utc)
    reasons = []
    if proposal.get("status") != "WATCHLIST_ONLY" or proposal.get("approval_enabled") is not False:
        reasons.append("Unexpected proposal state")
    observed = _utc_time(proposal.get("observed_at"))
    expires = _utc_time(proposal.get("expires_at"))
    if observed is None or expires is None or not (0 <= (now - observed).total_seconds() <= MAX_SNAPSHOT_AGE_SECONDS) or now >= expires:
        reasons.append("Market snapshot expired, missing or future-dated")
    ask = finite_positive(proposal.get("observed_best_ask_usdt"))
    bid = finite_positive(proposal.get("observed_best_bid_usdt"))
    spread = finite_positive(proposal.get("spread_pct"))
    depth = finite_positive(proposal.get("ask_depth_top5_usdt"))
    turnover = finite_positive(proposal.get("turnover_24h_usdt"))
    if not (ask > bid > 0 and 0 < spread <= MAX_SPREAD_PERCENT):
        reasons.append("Unacceptable or invalid bid-ask spread")
    if depth < MIN_DEPTH_USDT or turnover < 300000:
        reasons.append("Insufficient order-book depth or 24h turnover")
    try:
        change = float(proposal.get("change_24h_pct"))
        if not math.isfinite(change) or change > MAX_CHASE_PERCENT or change < -30:
            reasons.append("24h move outside conservative entry range")
    except (TypeError, ValueError, OverflowError):
        reasons.append("Invalid 24h price change")
    # An external adapter must independently authenticate these sources;
    # a user-controlled dict alone is never sufficient for live trade approval.
    evidence = independent_evidence if isinstance(independent_evidence, dict) else {}
    required = {
        "token_identity": "Verified token identity and correct exchange listing",
        "security": "Independent contract/custody security review",
        "tokenomics": "Token supply, unlock and holder risk review",
        "entry_thesis": "Price structure, invalidation and reward/risk analysis",
        "fx": "Verified NGN-to-USDT conversion and total exposure",
        "execution": "Fresh authenticated executable quote and fee/slippage checks",
    }
    missing = [label for key, label in required.items() if not isinstance(evidence.get(key), dict)
               or not evidence[key].get("source") or not evidence[key].get("observed_at")]
    # Even complete caller-provided metadata does not prove authentication.
    return {
        "decision": "RESEARCH PRIORITY" if not reasons else "WAIT / VERIFY",
        "buy_candidate": False,
        "trade_authorized": False,
        "order_amount_usdt": None,
        "pair": proposal.get("pair"),
        "market_objections": reasons,
        "missing_independent_checks": missing,
        "authenticated_provider_validation": "NOT IMPLEMENTED",
        "summary": ("Market snapshot passes preliminary entry filters; continue independent checks."
                    if not reasons else "Market snapshot fails one or more entry filters."),
    }


def format_assessment(assessment):
    parts = [
        f"ENTRY RESEARCH: {assessment['decision']}",
        f"Pair: {assessment['pair']}",
        f"Market objections: {'; '.join(assessment['market_objections']) or 'None in preliminary snapshot'}",
        f"Verification gaps: {'; '.join(assessment['missing_independent_checks']) or 'Metadata supplied; authentication still unavailable'}",
        "NO BUY SIGNAL. No live execution or Telegram approval is enabled.",
    ]
    return "\n".join(parts)
