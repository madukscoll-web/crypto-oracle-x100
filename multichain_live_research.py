"""Read-only multichain discovery runner; never produces or sends BUY alerts.

Runs existing GeckoTerminal adapters, deduplicates by chain and contract, then
applies fair research rotation. Existing production scanner is unchanged.
"""
import argparse
import datetime as dt
import json
from discovery_adapters import ADAPTERS, deduplicate
from multichain_candidate_rotation import rotate
from provider_session import Session
from global_discovery import EvidenceFetch
from multichain_research_audit import audit
from collections import Counter

def run(limit=12, cursor=0, fetch=None, adapters=ADAPTERS):
    if not 1 <= limit <= 100:
        raise ValueError("Invalid limit")
    if fetch is None:
        with Session(max_requests=80, max_seconds=180) as session:
            return run(limit, cursor, EvidenceFetch(session), adapters)
    rows, failures = [], []
    for adapter in adapters:
        try:
            result = adapter(fetch).discover()
            rows.extend(result["rows"])
            failures.extend(result["failures"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            failures.append({"network": adapter.network, "error_type": type(exc).__name__})
    assets = deduplicate(rows)
    source_counts = Counter(str(row.get("source") or "UNKNOWN") for row in rows)
    selection = rotate(assets, per_run=limit, cursor=cursor)
    report = {"observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode": "READ_ONLY_RESEARCH", "orders_allowed": False,
            "buy_authorized": False, "telegram_transmission": False,
            "observed_pools": len(rows), "unique_tokens": len(assets),
            "discovery_sources": dict(sorted(source_counts.items())),
            "launchpad_direct_feeds_active": [],
            "selected": [{"network": a["network"], "token_address": a["token_address"],
                          "asset_key": a["asset_key"], "pool_count": len(a["pools"]),
                          "discovery_sources": sorted(set(str(p.get("source") or "UNKNOWN") for p in a["pools"])),
                          "launchpad": "UNKNOWN — no authenticated launchpad-origin evidence"}
                         for a in selection["selected"]],
            "next_cursor": selection["next_cursor"],
            "deferred": selection["deferred"], "failures": failures}
    report["coverage_audit"] = audit(report)
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--cursor", type=int, default=0)
    parser.add_argument("--output", default="multichain_research_report.json")
    args = parser.parse_args()
    report = run(args.limit, args.cursor)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "selected"}))
