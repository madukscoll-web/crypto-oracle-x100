"""Independent market-data corroboration (not a security or execution audit)."""
import datetime as dt
import math
import urllib.parse

DEX = "https://api.dexscreener.com/latest/dex/pairs"
NETWORK_IDS = {"eth": "ethereum", "bsc": "bsc", "base": "base",
               "arbitrum": "arbitrum", "polygon_pos": "polygon",
               "avax": "avalanche", "optimism": "optimism", "solana": "solana"}


def check(item, fetch):
    network = NETWORK_IDS.get(item.get("network"))
    pool = item.get("address")
    if not network or not pool:
        return {"status": "UNKNOWN", "reason": "Unsupported chain or missing pool"}
    url = f"{DEX}/{network}/{urllib.parse.quote(str(pool), safe='')}"
    try:
        payload = fetch(url)
        matches = [p for p in payload.get("pairs") or []
                   if p.get("chainId") == network
                   and str(p.get("pairAddress", "")).lower() == str(pool).lower()
                   and str((p.get("baseToken") or {}).get("address", "")).lower()
                   == str(item.get("token_address", "")).lower()]
        if not matches:
            return {"status": "CONFLICTING", "reason": "Exact pool/base-token match absent"}
        pair = matches[0]
        price = float(pair.get("priceUsd"))
        original = float(item.get("base_token_price_usd"))
        if not all(math.isfinite(x) and x > 0 for x in (price, original)):
            return {"status": "UNKNOWN", "reason": "Nonpositive or invalid price"}
        divergence = abs(price / original - 1) * 100
        if divergence > 5:
            return {"status": "CONFLICTING", "reason": f"Provider prices differ {divergence:.1f}%"}
        return {"status": "CORROBORATED", "reason": "Matching chain, pool, base token and price",
                "source": url, "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "price_usd": price, "price_divergence_percent": round(divergence, 2)}
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError, OSError, IndexError) as exc:
        return {"status": "UNKNOWN", "reason": f"Provider unavailable or invalid: {type(exc).__name__}"}
