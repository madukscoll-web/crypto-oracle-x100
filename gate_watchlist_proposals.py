"""Evidence-labelled Gate spot research proposals, NOT executable orders.

Every proposal is informational. No approval callbacks, signed Gate requests,
API keys, or order submission exist here.
"""
import datetime as dt
import hashlib
import json
import math
import os
import urllib.parse
import urllib.request

from gate_spot_research import research, finite_positive
from gate_entry_assessment import assess_entry, format_assessment

MAX_POSITION_NGN = 50_000
TOTAL_BUDGET_NGN = 200_000
PROPOSAL_TTL_SECONDS = 120
MAX_SPREAD_PCT = 0.8


def make_proposal(candidate, now=None):
    """Prepare a traceable watchlist proposal from recent public orderbook evidence."""
    if candidate.get("decision") != "BUY WATCHLIST — RESEARCH ONLY":
        return None
    book = candidate.get("orderbook")
    if not isinstance(book, dict):
        return None
    ask = finite_positive(book.get("ask"))
    bid = finite_positive(book.get("bid"))
    spread = finite_positive(book.get("spread_pct"))
    depth = finite_positive(book.get("ask_depth_usdt"))
    turnover = finite_positive(candidate.get("turnover"))
    if not (ask > bid > 0 and 0 < spread <= MAX_SPREAD_PCT
            and depth >= 5_000 and turnover >= 300_000):
        return None
    pair = candidate.get("pair", "")
    if not isinstance(pair, str) or not pair.endswith("_USDT") or not pair.replace("_", "").isalnum():
        return None
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    now = now.astimezone(dt.timezone.utc)
    expiry = now + dt.timedelta(seconds=PROPOSAL_TTL_SECONDS)
    # This ID is for audit/dedup only. It is NOT an authorization token.
    key = f"{pair}|{ask:.12g}|{now.isoformat()}"
    proposal_id = hashlib.sha256(key.encode()).hexdigest()[:16]
    return {
        "proposal_id": proposal_id,
        "pair": pair,
        "side": "BUY",
        "status": "WATCHLIST_ONLY",
        "approval_enabled": False,
        "exchange": "Gate spot",
        "observed_best_bid_usdt": bid,
        "observed_best_ask_usdt": ask,
        "indicative_entry_ceiling_usdt": ask,
        "spread_pct": spread,
        "ask_depth_top5_usdt": depth,
        "turnover_24h_usdt": turnover,
        "change_24h_pct": candidate["change_24h"],
        "max_position_ngn": MAX_POSITION_NGN,
        "strategy_budget_ngn": TOTAL_BUDGET_NGN,
        "order_amount_usdt": None,
        "ngn_usdt_fx_status": "UNVERIFIED",
        "security_status": "UNVERIFIED",
        "entry_thesis_status": "NOT ASSESSED",
        "executable_quote_status": "UNVERIFIED",
        "stop_loss_status": "NOT CONFIGURED",
        "observed_at": now.isoformat(timespec="seconds"),
        "expires_at": expiry.isoformat(timespec="seconds"),
        "warning": "Public order book snapshot is NOT an executable quote. No purchase authorized.",
    }


def render_proposal(p):
    """Telegram-friendly research text. No fake approve button or order instruction."""
    return (
        "🔍 CRYPTO-ORACLE Z — GATE BUY WATCHLIST (RESEARCH ONLY)\n"
        f"Proposal: {p['proposal_id']}\n"
        f"Pair: {p['pair']} | Exchange: Gate spot\n"
        f"Observed bid/ask: {p['observed_best_bid_usdt']:.10g} / {p['observed_best_ask_usdt']:.10g} USDT\n"
        f"Spread: {p['spread_pct']:.3f}%\n"
        f"Top-five ask depth: {p['ask_depth_top5_usdt']:,.0f} USDT\n"
        f"24h quote turnover: {p['turnover_24h_usdt']:,.0f} USDT\n"
        f"24h change: {p['change_24h_pct']:+.2f}%\n"
        f"Indicative entry ceiling: {p['indicative_entry_ceiling_usdt']:.10g} USDT (NOT executable)\n"
        f"Maximum position: NGN {p['max_position_ngn']:,}; FX: {p['ngn_usdt_fx_status']}\n"
        "Contract/tokenomics: UNVERIFIED; trade thesis: NOT ASSESSED\n"
        "Order quote: UNVERIFIED; stop-loss: NOT CONFIGURED\n"
        f"Observed UTC: {p['observed_at']}\n"
        f"Snapshot expiry UTC: {p['expires_at']}\n"
        "FINAL DECISION: BUY WATCHLIST — RESEARCH ONLY\n"
        "No BUY CANDIDATE or executable order exists. Replying APPROVE does nothing.\n"
        "No trade will be placed; further independent verification is required.\n"
        + format_assessment(assess_entry(p, now=dt.datetime.fromisoformat(p["observed_at"])))
    )


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Telegram credentials unavailable")
    if len(text) > 4096:
        raise ValueError("Telegram text too long")
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, method="POST"
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        response = json.load(resp)
    if response.get("ok") is not True:
        raise RuntimeError("Telegram did not confirm delivery")


def main():
    proposals = [p for c in research() if (p := make_proposal(c)) is not None]
    print(f"Gate watchlist proposals (NOT buy signals): {len(proposals)}")
    # Opt-in only. The existing hourly scanner remains unchanged.
    if os.environ.get("GATE_WATCHLIST_SEND", "false").lower() != "true":
        for p in proposals:
            print(render_proposal(p))
        print("Telegram disabled by default; no orders possible.")
        return
    for p in proposals[:3]:
        send_telegram(render_proposal(p))
    print("Research alerts delivered; no orders possible.")


if __name__ == "__main__":
    main()
