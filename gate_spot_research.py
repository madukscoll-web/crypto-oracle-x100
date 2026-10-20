"""Gate spot research adapter. Read-only public endpoints; NEVER places orders.

A WATCHLIST is not a buy signal. Ticker snapshots and order books can be
manipulated and are not evidence of token contract safety or future returns.
"""
import json
import math
import os
import urllib.parse
import urllib.request

GATE_API = "https://api.gateio.ws/api/v4"
HEADERS = {"Accept": "application/json", "User-Agent": "CRYPTO-ORACLE-Z/spot-research"}
MAX_PAIRS = 6
MIN_TURNOVER_USDT = 300_000
MAX_SPREAD_PERCENT = 0.8
MIN_TOP5_DEPTH_USDT = 5_000


def finite_positive(value):
    try:
        n = float(value)
        return n if math.isfinite(n) and n > 0 else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


def get_json(path):
    if not path.startswith("/spot/"):
        raise ValueError("Only public spot endpoints permitted")
    req = urllib.request.Request(GATE_API + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def eligible_tickers(tickers, pair_metadata):
    """Require an actively tradeable USDT spot pair with substantial turnover."""
    allowed = {
        x.get("id") for x in pair_metadata
        if isinstance(x, dict) and x.get("trade_status") == "tradable"
        and x.get("quote") == "USDT" and x.get("id", "").endswith("_USDT")
    }
    result = []
    for t in tickers:
        if not isinstance(t, dict):
            continue
        pair = t.get("currency_pair")
        turnover = finite_positive(t.get("quote_volume"))
        last = finite_positive(t.get("last"))
        change = t.get("change_percentage")
        if pair not in allowed or turnover < MIN_TURNOVER_USDT or not last:
            continue
        try:
            change = float(change)
            if not math.isfinite(change):
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        result.append({"pair": pair, "last": last, "turnover": turnover, "change_24h": change})
    return sorted(result, key=lambda t: t["turnover"], reverse=True)


def orderbook_evidence(book):
    """Top-five quote depth is only an approximation, not guaranteed execution."""
    bids, asks = book.get("bids") or [], book.get("asks") or []
    def rows(raw):
        values = []
        for r in raw[:5]:
            if not isinstance(r, (list, tuple)) or len(r) < 2:
                continue
            p, q = finite_positive(r[0]), finite_positive(r[1])
            if p and q:
                values.append((p, q))
        return values
    b, a = rows(bids), rows(asks)
    if not b or not a:
        return None
    bid, ask = b[0][0], a[0][0]
    if ask <= bid:
        return None
    spread = 200 * (ask - bid) / (ask + bid)
    bid_depth = sum(p*q for p, q in b)
    ask_depth = sum(p*q for p, q in a)
    return {"bid": bid, "ask": ask, "spread_pct": spread,
            "bid_depth_usdt": bid_depth, "ask_depth_usdt": ask_depth}


def assess_spot_candidate(ticker, book):
    evidence = orderbook_evidence(book)
    if evidence is None:
        return "WAIT / VERIFY", "Invalid or crossed order book", None
    if evidence["spread_pct"] > MAX_SPREAD_PERCENT:
        return "WAIT / VERIFY", "Spread exceeds 0.8%; entry costs elevated", evidence
    if min(evidence["bid_depth_usdt"], evidence["ask_depth_usdt"]) < MIN_TOP5_DEPTH_USDT:
        return "WAIT / VERIFY", "Top-five order-book depth below USDT 5,000", evidence
    if abs(ticker["change_24h"]) > 30:
        return "WAIT / VERIFY", "24h price move exceeds 30%; chase/dump risk", evidence
    return "BUY WATCHLIST — RESEARCH ONLY", (
        "Active Gate spot pair with turnover, spread and depth screening; "
        "contract, holder, tokenomics, execution quote and entry thesis remain UNVERIFIED"
    ), evidence


def build_watchlist(tickers, pairs, book_fetcher, limit=MAX_PAIRS):
    """Bounded read-only screening; never output a BUY CANDIDATE or order."""
    out = []
    for t in eligible_tickers(tickers, pairs)[:max(0, min(12, limit))]:
        try:
            book = book_fetcher(t["pair"])
            label, reason, depth = assess_spot_candidate(t, book)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            label, reason, depth = "WAIT / VERIFY", "Order book unavailable: " + type(exc).__name__, None
        out.append({**t, "decision": label, "reason": reason, "orderbook": depth})
    return out


def research():
    tickers = get_json("/spot/tickers")
    pairs = get_json("/spot/currency_pairs")
    if not isinstance(tickers, list) or not isinstance(pairs, list):
        raise ValueError("Unexpected Gate public API response")
    return build_watchlist(tickers, pairs, lambda pair: get_json(
        "/spot/order_book?currency_pair=" + urllib.parse.quote(pair, safe="") + "&limit=5"))


def main():
    items = research()
    print("Gate spot research:", json.dumps(items, indent=2))
    # No order endpoint, API key, or auto-execution exists in this module.
    # Do not send duplicate Telegram alerts until explicit alert cadence is tested.
    print("Research-only. No purchases proposed or executed.")


if __name__ == "__main__":
    main()
