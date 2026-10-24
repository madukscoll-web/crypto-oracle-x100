"""Public, exact-contract fundamentals. Observations are never audit evidence.

CoinGecko contract lookup is independent of pool activity. Circulating/max
supply estimates, holder exclusions, vesting and executable quotes require
additional primary evidence; unsupported fields remain explicitly UNVERIFIED.
"""
import datetime as dt
import hashlib
import json
import math
import re
import urllib.parse

PLATFORMS = {"eth": "ethereum", "base": "base", "bsc": "binance-smart-chain",
             "polygon_pos": "polygon-pos", "arbitrum": "arbitrum-one",
             "optimism": "optimistic-ethereum", "avax": "avalanche", "solana": "solana"}
FIELDS = ("circulating_supply", "total_supply", "max_supply", "market_cap_usd",
          "fdv_usd", "unlocks", "adjusted_top10_fraction", "adoption",
          "lp_controls", "independent_security", "execution_quote")


def finite(value, minimum=0):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= minimum else None
    except (ValueError, TypeError, OverflowError):
        return None


def same_address(network, left, right):
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return left.lower() == right.lower() if network != "solana" else left == right


def collect(item, fetch, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.isoformat()
    network, contract = item.get("network"), item.get("token_address")
    def datum(value=None, provider=None, source=None, reason="Reliable evidence not obtained", digest=None):
        return dict(value=value, provider=provider or "UNVERIFIED", source_url=source,
                    network=network, contract=contract, observed_at=stamp,
                    status="UNVERIFIED", reason=reason, response_sha256=digest)
    result = {field: datum() for field in FIELDS}
    platform = PLATFORMS.get(network)
    # Never fetch a path derived from a missing identity or malformed contract.
    valid = (isinstance(contract, str) and
             (bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", contract)) if network == "solana"
              else bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", contract))))
    if not platform or not valid:
        return result
    url = ("https://api.coingecko.com/api/v3/coins/" + platform + "/contract/" +
           urllib.parse.quote(contract, safe=""))
    try:
        payload = fetch(url)
        returned = (payload.get("platforms") or {}).get(platform)
        if not returned:
            raise ValueError("Provider omitted contract identity")
        if not same_address(network, contract, returned):
            for field in FIELDS[:5]:
                result[field] = datum(provider="CoinGecko", source=url, reason="Exact-contract identity mismatch")
                result[field]["status"] = "CONFLICTING"
            return result
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        market = payload.get("market_data") or {}
        values = {key: market.get(key) for key in FIELDS[:3]}
        values.update(market_cap_usd=(market.get("market_cap") or {}).get("usd"),
                      fdv_usd=(market.get("fully_diluted_valuation") or {}).get("usd"))
        for field, raw in values.items():
            value = finite(raw)
            result[field] = datum(value, "CoinGecko", url,
                "Single-provider estimate; independent supply/primary-source verification unavailable", digest)
            result[field]["provider_updated_at"] = payload.get("last_updated")
        circ, total, maximum = [result[key]["value"] for key in FIELDS[:3]]
        if ((circ is not None and total is not None and circ > total) or
                (total is not None and maximum is not None and total > maximum) or
                (circ is not None and maximum is not None and circ > maximum)):
            for field in FIELDS[:3]:
                result[field].update(status="CONFLICTING", reason="Provider supply figures conflict")
    except (OSError, ValueError, TypeError, AttributeError, KeyError, OverflowError):
        for field in FIELDS[:5]:
            result[field] = datum(provider="CoinGecko", source=url, reason="Provider unavailable or malformed response")
    return result


def scenario_summary():
    return ("3m / 12m / 3y scenarios (arithmetic only): P_future/P_now = "
            "(cap_future/cap_now)/(supply_future/supply_now). "
            "At every horizon, 2x cap with 2x supply = 1x price; "
            "100x price requires 100x cap times supply growth. "
            "Future supply, valuation and probabilities: UNVERIFIED.")
