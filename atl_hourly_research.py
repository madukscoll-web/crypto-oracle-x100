"""Bounded, read-only CoinGecko market-cap universe probe.

Provider ATL fields are NOT validated lifetime trading lows. This stage emits
diagnostics only, and deliberately sends no token alerts or BUY decisions.
"""
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request
from atl_monitor_core import cap_class, positive, classify_low

API = "https://api.coingecko.com/api/v3/coins/markets"
MAX_PAGES = 1
PAGE_SIZE = 100

def run(fetch=None, *, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    report = {"schema_version": 1, "mode": "READ_ONLY_UNVERIFIED_HISTORY",
              "source": "CoinGecko public coins/markets",
              "observed_at": now.isoformat(), "pages_attempted": 0,
              "assets_received": 0, "eligible_verified": 0,
              "market_cap_unverified": 0, "provider_atl_candidates": 0, "historical_baselines_validated": 0,
              "assets_checked_against_validated_low": 0,
              "alerts_delivered": 0, "orders_allowed": False,
              "buy_authorized": False, "coverage_complete": False,
              "status": "UNAVAILABLE", "errors": [], "observations": []}
    if fetch is None:
        def fetch(url):
            request = urllib.request.Request(url, headers={"Accept": "application/json",
                "User-Agent": "crypto-oracle-x100-atl-research/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                return json.load(response)
    params = urllib.parse.urlencode({"vs_currency": "usd", "order": "market_cap_desc",
                                     "per_page": PAGE_SIZE, "page": 1,
                                     "sparkline": "false"})
    report["pages_attempted"] = 1
    try:
        rows = fetch(API + "?" + params)
        if not isinstance(rows, list):
            raise ValueError("Invalid market catalog response")
        report["assets_received"] = len(rows)
        for row in rows[:PAGE_SIZE]:
            if not isinstance(row, dict):
                continue
            identifier = row.get("id")
            market_cap = positive(row.get("market_cap"))
            price = positive(row.get("current_price"))
            if not isinstance(identifier, str) or not identifier or market_cap is None or price is None:
                continue
            if market_cap < 100000000:
                continue
            # Provider-reported ATL is useful for discovery, but is not
            # independently validated lifetime trading history.
            reported_atl = positive(row.get("atl"))
            reported_date = row.get("atl_date")
            candidate = None
            if reported_atl is not None and isinstance(reported_date, str) and reported_date:
                finding = classify_low(price, reported_atl, lifetime_complete=False,
                                       comparable=True, corroborated=False)
                if finding["status"] in ("NEAR OBSERVED LOW", "UNVALIDATED_LOW"):
                    candidate = {"label": "PROVIDER-REPORTED ATL | RESEARCH CANDIDATE",
                                 "percent_above": str(finding["percent_above"]),
                                 "source": "CoinGecko", "source_atl_usd": str(reported_atl),
                                 "source_atl_date": reported_date,
                                 "independently_verified": False,
                                 "telegram_eligible": False}
            if candidate is not None:
                report["provider_atl_candidates"] += 1
            report["market_cap_unverified"] += 1
            report["observations"].append({
                "provider_id": identifier, "symbol_hint": row.get("symbol"),
                "market_cap_usd": str(market_cap), "indicative_price_usd": str(price),
                "provider_last_updated": row.get("last_updated"),
                "cap_classification": cap_class(market_cap),
                "history_status": "UNVALIDATED",
                "atl_status": "UNAVAILABLE",
                "telegram_eligible": False, "provider_atl_candidate": candidate})
        report["status"] = "OBSERVATIONS_UNVERIFIED"
    except Exception as exc:
        report["errors"].append(type(exc).__name__)
    return report

def main():
    result = run()
    path = pathlib.Path("atl_coverage_report.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("ATL research coverage:", json.dumps({k:v for k,v in result.items()
          if k != "observations"}, sort_keys=True))

if __name__ == "__main__":
    main()
