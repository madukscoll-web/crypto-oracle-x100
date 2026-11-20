"""Re-price tracked pools through DexScreener before GeckoTerminal. Research only.

GeckoTerminal's free quota is shared by discovery, enrichment and re-pricing, and
GitHub's shared runner IPs exhaust it quickly: re-pricing ran last and often got
nothing. DexScreener's pairs endpoint prices up to 30 pools per call on a separate,
larger free quota. This adapter answers GeckoTerminal multi-pool URLs with a
GeckoTerminal-shaped payload built from DexScreener, so callers keep their own
identity, liquidity and vanished-pool checks unchanged.

Fail-safe rules:
- Pools DexScreener does not return are re-asked from GeckoTerminal, never
  treated as vanished on DexScreener's word alone.
- Unknown networks, malformed responses and DexScreener errors fall back to the
  original GeckoTerminal request.
- Only exact requested pair addresses are accepted; prices are never invented.
"""
import math
import re
import urllib.parse

DEX = "https://api.dexscreener.com/latest/dex/pairs"
BATCH_LIMIT = 30
# GeckoTerminal network id -> DexScreener chain id.
CHAINS = {"eth": "ethereum", "base": "base", "bsc": "bsc", "solana": "solana",
          "polygon_pos": "polygon", "arbitrum": "arbitrum", "avax": "avalanche"}
_MULTI = re.compile(r"^/api/v2/networks/([a-z0-9_]+)/pools/multi/([A-Za-z0-9,]+)$")


def _norm(network, address):
    return address if network == "solana" else address.lower()


def _positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def parse_multi(url):
    """(network, [addresses]) for a GeckoTerminal multi-pool URL, else None."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "api.geckoterminal.com" or parts.query:
        return None
    match = _MULTI.match(parts.path)
    if not match:
        return None
    addresses = [a for a in match.group(2).split(",") if a]
    if not addresses or len(addresses) > BATCH_LIMIT:
        return None
    return match.group(1), addresses


def convert(network, addresses, payload):
    """GeckoTerminal-shaped pools for the requested addresses DexScreener returned."""
    if not isinstance(payload, dict):
        raise ValueError("Malformed DexScreener response")
    pairs = payload.get("pairs")
    if pairs is None:
        pairs = []
    if not isinstance(pairs, list):
        raise ValueError("Malformed DexScreener pairs")
    wanted = {_norm(network, a): a for a in addresses}
    pools = {}
    for pair in pairs:
        if not isinstance(pair, dict) or pair.get("chainId") != CHAINS[network]:
            continue
        address = str(pair.get("pairAddress") or "")
        base = str(((pair.get("baseToken") or {}).get("address")) or "")
        if _norm(network, address) not in wanted or not base:
            continue
        price = _positive(pair.get("priceUsd"))
        liquidity = _positive((pair.get("liquidity") or {}).get("usd"))
        pools[_norm(network, address)] = {
            "attributes": {"address": wanted[_norm(network, address)],
                           "base_token_price_usd": None if price is None else str(price),
                           "reserve_in_usd": None if liquidity is None else str(liquidity),
                           "price_source": "dexscreener"},
            "relationships": {"base_token": {"data": {"id": network + "_" + base}}}}
    return pools


def make_fetch(dex_fetch, gecko_fetch, report=None):
    """A fetch(url) that serves GeckoTerminal multi-pool URLs from DexScreener first."""
    report = report if report is not None else {}
    for name in ("dexscreener_batches", "dexscreener_priced", "gecko_fallback_pools", "dexscreener_errors"):
        report.setdefault(name, 0)

    def fetch(url):
        parsed = parse_multi(url)
        if parsed is None or parsed[0] not in CHAINS:
            return gecko_fetch(url)
        network, addresses = parsed
        try:
            pools = convert(network, addresses, dex_fetch(f"{DEX}/{CHAINS[network]}/{','.join(addresses)}"))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            report["dexscreener_errors"] += 1
            return gecko_fetch(url)
        report["dexscreener_batches"] += 1
        report["dexscreener_priced"] += len(pools)
        missing = [a for a in addresses if _norm(network, a) not in pools]
        data = list(pools.values())
        if missing:
            # Never let DexScreener's silence mark a pool vanished: ask GeckoTerminal.
            # A GeckoTerminal failure propagates so the caller stops without state changes.
            report["gecko_fallback_pools"] += len(missing)
            fallback = gecko_fetch(f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/multi/{','.join(missing)}")
            extra = fallback.get("data") if isinstance(fallback, dict) else None
            if not isinstance(extra, list):
                raise ValueError("Malformed GeckoTerminal fallback response")
            data.extend(extra)
        return {"data": data}

    return fetch


def _count(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def pool_payload(network, address, dex_fetch):
    """One pool as a GeckoTerminal-shaped payload (with included tokens) from DexScreener.

    Used for per-candidate identity so GeckoTerminal rate limits stop leaving tokens
    UNVERIFIED. Returns None when DexScreener cannot prove the exact requested pool
    on the exact chain with both token addresses; the caller then asks GeckoTerminal.
    """
    if network not in CHAINS or not address:
        return None
    try:
        payload = dex_fetch(f"{DEX}/{CHAINS[network]}/{address}")
    except (OSError, ValueError, TypeError):
        return None
    pairs = payload.get("pairs") if isinstance(payload, dict) else None
    if not isinstance(pairs, list):
        return None
    for pair in pairs:
        if not isinstance(pair, dict) or pair.get("chainId") != CHAINS[network]:
            continue
        if _norm(network, str(pair.get("pairAddress") or "")) != _norm(network, address):
            continue
        base, quote = pair.get("baseToken") or {}, pair.get("quoteToken") or {}
        if not base.get("address") or not quote.get("address"):
            return None
        txns = (pair.get("txns") or {}).get("h1") or {}
        changes = pair.get("priceChange") or {}
        price = _positive(pair.get("priceUsd"))
        liquidity = _positive((pair.get("liquidity") or {}).get("usd"))
        volume = _finite((pair.get("volume") or {}).get("h24"))
        base_id, quote_id = network + "_" + str(base["address"]), network + "_" + str(quote["address"])
        return {
            "data": {"attributes": {
                "address": address,
                "base_token_price_usd": None if price is None else str(price),
                "reserve_in_usd": None if liquidity is None else str(liquidity),
                "volume_usd": {"h24": None if volume is None or volume < 0 else str(volume)},
                "transactions": {"h1": {"buys": _count(txns.get("buys")), "sells": _count(txns.get("sells"))}},
                "price_change_percentage": {"h1": _finite(changes.get("h1")), "h24": _finite(changes.get("h24"))},
                "price_source": "dexscreener"},
                "relationships": {"base_token": {"data": {"id": base_id}}, "quote_token": {"data": {"id": quote_id}}}},
            "included": [
                {"type": "token", "id": base_id, "attributes": {"address": str(base["address"]), "symbol": base.get("symbol") or "UNKNOWN"}},
                {"type": "token", "id": quote_id, "attributes": {"address": str(quote["address"]), "symbol": quote.get("symbol") or "UNKNOWN"}}],
        }
    return None
