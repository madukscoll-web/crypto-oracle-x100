"""Manual, read-only Gate Spot reversal research and historical evaluation.

Run: python altcoin_reversal_cli.py --pairs LINK_USDT,ONDO_USDT --interval 1d
Does not send Telegram messages, authenticate, or submit orders.
"""
import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request

from altcoin_reversal_gate import gate_candles, INTERVAL_SECONDS, GATE_INTERVAL
from altcoin_reversal_research import analyze, eligible_symbol
from altcoin_reversal_backtest import walk_forward
from gate_spot_research import PublicGate


def fetch_public(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "CryptoOracle-ReadOnly-ReversalResearch/1.0",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(3_000_001)
    if len(data) > 3_000_000:
        raise ValueError("Exchange response exceeded size limit")
    return json.loads(data)


def run(pairs, interval="1d", *, fetch=fetch_public, now=None):
    if interval not in INTERVAL_SECONDS:
        raise ValueError("Unsupported interval")
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    gate = PublicGate(fetch)
    results = []
    for pair in pairs:
        record = dict(pair=pair, status="UNAVAILABLE", buy_authorized=False,
                      orders_allowed=False, telegram_eligible=False)
        evidence_start = len(gate.evidence)
        try:
            if not isinstance(pair, str) or not pair.endswith("_USDT") or not eligible_symbol(pair[:-5]):
                raise ValueError("Excluded or malformed trading pair")
            # Do not assume a named pair is active Gate Spot: verify metadata.
            meta = gate.get("/spot/currency_pairs/" + pair)
            if (not isinstance(meta, dict) or meta.get("id") != pair
                    or meta.get("base") != pair[:-5] or meta.get("quote") != "USDT"
                    or meta.get("type") != "normal" or meta.get("trade_status") != "tradable"
                    or meta.get("st_tag") is not False):
                raise ValueError("Active normal Gate Spot pair not verified")
            if any(type(meta.get(k)) is not int or meta[k] > now for k in ("buy_start", "sell_start")):
                raise ValueError("Gate Spot activation times unknown or not active")
            if meta.get("delisting_time") not in (None, 0):
                raise ValueError("Delisting status requires independent review")
            raw = gate.get("/spot/candlesticks", dict(
                currency_pair=pair, interval=GATE_INTERVAL[interval], limit=1000))
            candles = gate_candles(raw, interval_seconds=INTERVAL_SECONDS[interval],
                                   now=now)
            if len(candles) < 65:
                raise ValueError("Not enough closed historical candles for 10-bar evaluation")
            period = INTERVAL_SECONDS[interval]
            if now - candles[-1]["timestamp"] > 3 * period:
                raise ValueError("Historical candles are stale")
            if any(b["timestamp"] - a["timestamp"] != period
                   for a, b in zip(candles, candles[1:])):
                raise ValueError("Missing or irregular historical candles")
            source = "Gate Spot public API v4"
            research = analyze(pair.replace("_", "/"), candles,
                               source=source, observed_at=dt.datetime.fromtimestamp(
                                   now, dt.timezone.utc).isoformat(), interval=interval)
            backtest = walk_forward(pair.replace("_", "/"), candles,
                                    source=source, interval=interval, horizon=10)
            # Avoid outputting every overlapping paper observation in the compact CLI.
            backtest.pop("observations", None)
            record.update(status="RESEARCH_ONLY", candle_count=len(candles),
                          latest_closed_candle=candles[-1]["timestamp"],
                          research=research, backtest=backtest)
        except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError,
                json.JSONDecodeError) as exc:
            record["reason"] = type(exc).__name__ + ": " + str(exc)[:180]
        record["provider_evidence"] = gate.evidence[evidence_start:]
        results.append(record)
    return dict(as_of=dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                strategy="ALTCOIN REVERSAL RESEARCH ONLY", results=results,
                buy_authorized=False, orders_allowed=False,
                disclaimer="Paper results do not establish forward profitability; no trading enabled")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default="LINK_USDT,ONDO_USDT")
    parser.add_argument("--interval", choices=tuple(INTERVAL_SECONDS), default="1d")
    args = parser.parse_args(argv)
    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    if not pairs or len(pairs) > 10 or len(set(pairs)) != len(pairs):
        parser.error("Provide 1 to 10 unique spot pairs")
    print(json.dumps(run(pairs, args.interval), indent=2))


if __name__ == "__main__":
    main()

