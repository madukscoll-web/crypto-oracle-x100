"""Read-only multichain discovery runner; never produces or sends BUY alerts.

Runs existing GeckoTerminal adapters, deduplicates by chain and contract, then
applies fair research rotation. Existing production scanner is unchanged.
"""
import argparse
import datetime as dt
import json
from discovery_adapters import RESEARCH_ADAPTERS, deduplicate, ProfileFallback
from multichain_candidate_rotation import rotate
from provider_session import Session
from global_discovery import EvidenceFetch
from multichain_research_audit import audit
from collections import Counter
from stonk_launch_discovery import run as stonk_run

def run(limit=12, cursor=0, fetch=None, adapters=RESEARCH_ADAPTERS, include_profiles=False, include_stonk=False, stonk_fetch=None):
    if not 1 <= limit <= 100:
        raise ValueError("Invalid limit")
    if fetch is None:
        with Session(max_requests=80, max_seconds=180,
                     host_intervals={"api.geckoterminal.com": 6.1}) as session:
            report = run(limit, cursor, EvidenceFetch(session), adapters, include_profiles, include_stonk, stonk_fetch)
            report["provider_session"] = session.summary()
            return report
    rows, failures, observations = [], [], []
    for adapter in adapters:
        try:
            result = adapter(fetch).discover()
            rows.extend(result["rows"])
            failures.extend(result["failures"])
            observations.extend(result.get("observations", []))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            failures.append({"network": adapter.network, "error_type": type(exc).__name__})
    if include_profiles:
        fallback = ProfileFallback(fetch)
        for network in dict.fromkeys(a.network for a in adapters):
            result = fallback.discover(network, limit=2)
            rows.extend(result["rows"])
            failures.extend(result["failures"])
            observations.extend(result.get("observations", []))
    launchpad_feeds = []
    if include_stonk:
        try:
            stonk = stonk_run(fetch=stonk_fetch)
            rows.extend(stonk["tokens"])
            launchpad_feeds.append("StonkFun (provider-attested; on-chain unverified)")
            observations.append({"source": "StonkFun", "url": stonk["source_url"],
                                 "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                 "valid_rows": stonk["count"],
                                 "invalid_rows": stonk["invalid_rows"]})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            failures.append({"source": "StonkFun", "error_type": type(exc).__name__,
                             "http_status": getattr(exc, "code", None)})
    assets = deduplicate(rows)
    source_counts = Counter(str(row.get("source") or "UNKNOWN") for row in rows)
    selection = rotate(assets, per_run=limit, cursor=cursor,
                       enabled=tuple(a.network for a in adapters))
    report = {"observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode": "READ_ONLY_RESEARCH", "orders_allowed": False,
            "buy_authorized": False, "telegram_transmission": False,
            "observed_pools": len(rows), "unique_tokens": len(assets),
            "requested_networks": list(dict.fromkeys(a.network for a in adapters)),
            "observed_by_chain": dict(sorted(Counter(r["network"] for r in rows).items())),
            "provider_observations": observations,
            "discovery_sources": dict(sorted(source_counts.items())),
            "launchpad_direct_feeds_active": launchpad_feeds,
            "selected": [{"network": a["network"], "token_address": a["token_address"],
                          "asset_key": a["asset_key"], "pool_count": len(a["pools"]),
                          "discovery_sources": sorted(set(str(p.get("source") or "UNKNOWN") for p in a["pools"])),
                          "launchpad": ("StonkFun — PROVIDER_ATTESTED, ONCHAIN UNVERIFIED" if any(p.get("launchpad") == "stonk" for p in a["pools"]) else "UNKNOWN — no authenticated launchpad-origin evidence")}
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
    parser.add_argument("--include-profiles", action="store_true", help="Add promotional DEX Screener leads; never assert launchpad provenance")
    parser.add_argument("--include-stonk", action="store_true", help="Include provider-attested StonkFun leads; never authorize BUY")
    args = parser.parse_args()
    report = run(args.limit, args.cursor, include_profiles=args.include_profiles, include_stonk=args.include_stonk)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "selected"}))
