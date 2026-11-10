"""Independent market-data corroboration (not a security or execution audit)."""
import datetime as dt
import math
import urllib.parse
from fundamental_evidence import same_address

DEX = "https://api.dexscreener.com/latest/dex/pairs"
NETWORK_IDS = {"eth": "ethereum", "bsc": "bsc", "base": "base",
               "arbitrum": "arbitrum", "polygon_pos": "polygon",
               "avax": "avalanche", "optimism": "optimism", "solana": "solana"}

MIN_LIQUIDITY_USD = 50_000  # Preserve the production scanner's stricter floor.
MAX_VOLUME_LIQUIDITY_RATIO = 50


def market_activity_screen(pair_data):
    """Reported pool reserves are not executable depth or token security."""
    def measurement(section, field):
        value=(pair_data.get(section) or {}).get(field)
        if isinstance(value,bool):return None
        try:
            value=float(value)
            return value if math.isfinite(value) and value>=0 else None
        except (ValueError,TypeError,OverflowError):return None
    result=dict(status='UNKNOWN',liquidity_usd=None,volume_24h_usd=None,
                volume_liquidity_ratio=None,warnings=[],security_status='UNVERIFIED',
                executable_depth_status='UNKNOWN',buy_authorized=False,orders_allowed=False)
    if (not isinstance(pair_data,dict) or
            any(pair_data.get(k) is not None and not isinstance(pair_data[k],dict) for k in ('liquidity','volume'))):
        result['warnings'].append('Malformed provider market measurements')
        return result
    liquidity=measurement('liquidity','usd');volume=measurement('volume','h24')
    result.update(liquidity_usd=liquidity,volume_24h_usd=volume)
    if liquidity is None or volume is None:
        result['warnings'].append('Liquidity or 24h volume unavailable or invalid')
        return result
    if liquidity<MIN_LIQUIDITY_USD:
        result.update(status='BELOW_LIQUIDITY_FLOOR')
        result['warnings'].append(f'Low reported liquidity: ${liquidity:,.2f}; minimum ${MIN_LIQUIDITY_USD:,.0f}')
        return result
    ratio=volume/liquidity
    if not math.isfinite(ratio):
        result['warnings'].append('Volume/liquidity ratio invalid')
        return result
    result['volume_liquidity_ratio']=ratio
    if ratio>MAX_VOLUME_LIQUIDITY_RATIO:
        result['status']='VOLUME_ANOMALY'
        result['warnings'].append('Suspicious reported volume/liquidity ratio; investigate, not proof of wash trading')
    else:result['status']='METRICS_ONLY_PASS'
    return result


def evaluate_tokenomics_and_security(pair_data):
    """Compatibility name: Boolean means market screen only, never safety."""
    result=market_activity_screen(pair_data)
    return result['status']=='METRICS_ONLY_PASS',result['warnings']


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
                   and same_address(item.get("network"), p.get("pairAddress"), pool)
                   and same_address(item.get("network"), (p.get("baseToken") or {}).get("address"),
                                    item.get("token_address"))]
        if not matches:
            return {"status": "CONFLICTING", "reason": "Exact pool/base-token match absent"}
        pair = matches[0]
        activity=market_activity_screen(pair)
        price = float(pair.get("priceUsd"))
        original = float(item.get("base_token_price_usd"))
        if not all(math.isfinite(x) and x > 0 for x in (price, original)):
            return {"status": "UNKNOWN", "reason": "Nonpositive or invalid price"}
        divergence = abs(price / original - 1) * 100
        if divergence > 5:
            return {"status": "CONFLICTING", "reason": f"Provider prices differ {divergence:.1f}%"}
        return {"status": "CORROBORATED", "reason": "Matching chain, pool, base token and price",
                "source": url, "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "price_usd": price, "price_divergence_percent": round(divergence, 2),
                "market_activity_screen":activity}
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError, OSError, IndexError) as exc:
        return {"status": "UNKNOWN", "reason": f"Provider unavailable or invalid: {type(exc).__name__}"}
