"""Read-only reversal WATCH notification policy.

Never promotes a technical observation to an investment authorization.
Only explicit, validated research classifications may be notified.
"""
import math

WATCHES = frozenset(("EARLY REVERSAL WATCH", "TECHNICAL REVERSAL WATCH"))

def select_watches(report):
    if not isinstance(report, dict) or report.get("buy_authorized") is not False or report.get("orders_allowed") is not False:
        raise ValueError("Untrusted research report")
    rows = report.get("results")
    if not isinstance(rows, list):
        raise ValueError("Missing research results")
    selected = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "RESEARCH_ONLY":
            continue
        research = row.get("research")
        if not isinstance(research, dict):
            continue
        if research.get("classification") not in WATCHES:
            continue
        if research.get("buy_authorized") is not False or research.get("orders_allowed") is not False:
            continue
        if row.get("buy_authorized") is not False or row.get("orders_allowed") is not False:
            continue
        pair = row.get("pair")
        metrics = research.get("metrics")
        if not isinstance(pair, str) or not pair.endswith("_USDT") or not isinstance(metrics, dict):
            continue
        price, trigger, invalidation = (metrics.get("close"), research.get("entry_trigger"), research.get("invalidation"))
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in (price, trigger, invalidation)):
            continue
        if invalidation >= price:
            continue
        selected.append(row)
    return selected

def format_watch(row):
    research = row["research"]
    metrics = research["metrics"]
    return (
        "CRYPTO-ORACLE X100 | " + research["classification"] + "\n"
        "Gate Spot pair: " + row["pair"] + "\n"
        "Observed UTC: " + str(research["observed_at"]) + "\n"
        "Timeframe: " + str(research["interval"]) + "\n"
        "Indicative last closed price (USDT): " + str(metrics["close"]) + "\n"
        "Breakout trigger reference: " + str(research["entry_trigger"]) + "\n"
        "Technical invalidation reference: " + str(research["invalidation"]) + "\n"
        "Volume/baseline ratio: " + str(metrics["volume_ratio"]) + "\n"
        "Source: " + str(research["source"]) + "\n"
        "Identity, fundamentals, unlocks, holder concentration, fees and executable liquidity NOT VERIFIED.\n"
        "NOT APPROVED FOR PURCHASE. No order or guaranteed execution."
    )
