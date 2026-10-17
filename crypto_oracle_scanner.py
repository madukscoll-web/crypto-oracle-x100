"""CRYPTO-ORACLE Z: multichain, evidence-labelled crypto research alerts.

No contract audit, token inception date, price forecast, or calibrated return
probability is inferred from pool-level GeckoTerminal market data.
"""

import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.geckoterminal.com/api/v2"
# Override with comma-separated GeckoTerminal network IDs using ORACLE_NETWORKS.
# Network IDs and API availability must be checked against GeckoTerminal.
DEFAULT_NETWORKS = ("solana", "base", "eth", "bsc", "arbitrum", "polygon_pos", "avax", "optimism")
NETWORKS = tuple(x.strip() for x in os.environ.get(
    "ORACLE_NETWORKS", ",".join(DEFAULT_NETWORKS)).split(",") if x.strip())
SCAN_MODES = ("new_pools", "trending_pools")
DATA_SOURCE = "GeckoTerminal public API"
HEADERS = {
    "Accept": "application/json;version=20230302",
    "User-Agent": "CRYPTO-ORACLE-Z/0.1",
}
MIN_LIQUIDITY_USD = 50_000
MIN_24H_VOLUME_USD = 100_000
MIN_1H_TRANSACTIONS = 40
MAX_NEW_POOL_AGE_HOURS = 72
# Older pools can appear via trending_pools. These are NOT necessarily old tokens.
MIN_TRENDING_POOL_AGE_HOURS = 72
PAGES_PER_NETWORK = max(1, min(3, int(os.environ.get("ORACLE_PAGES", "1"))))
REQUEST_DELAY_SECONDS = 5
RATE_LIMIT_RETRIES = 2
RATE_LIMIT_WAIT_SECONDS = (12, 24)
MAX_ALERTS_PER_RUN = max(1, min(20, int(os.environ.get("ORACLE_MAX_ALERTS", "10"))))
STATE_FILE = pathlib.Path("reported_pools.json")


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def fetch_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt >= RATE_LIMIT_RETRIES:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = number(retry_after) if retry_after else 0
            if delay <= 0:
                delay = RATE_LIMIT_WAIT_SECONDS[attempt]
            delay = min(max(delay, 1), 60)
            print(f"Rate limited (HTTP 429); retrying in {delay:g}s", flush=True)
            time.sleep(delay)
    raise RuntimeError("Unreachable rate-limit retry state")


def inspect(pool, network, mode="new_pools"):
    """Score observed pool activity; never infer contract or token safety."""
    attrs = pool.get("attributes") or {}
    created = attrs.get("pool_created_at")
    if not created:
        return None
    try:
        timestamp = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        age_hours = (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds() / 3600
    except (TypeError, ValueError, OverflowError):
        return None
    if age_hours < 0:
        return None
    if mode == "new_pools" and age_hours > MAX_NEW_POOL_AGE_HOURS:
        return None
    if mode == "trending_pools" and age_hours < MIN_TRENDING_POOL_AGE_HOURS:
        return None

    liquidity = number(attrs.get("reserve_in_usd"))
    volume = number((attrs.get("volume_usd") or {}).get("h24"))
    h1 = (attrs.get("transactions") or {}).get("h1") or {}
    buys = int(max(0, number(h1.get("buys"))))
    sells = int(max(0, number(h1.get("sells"))))
    trades = buys + sells
    if (liquidity < MIN_LIQUIDITY_USD or volume < MIN_24H_VOLUME_USD
            or trades < MIN_1H_TRANSACTIONS):
        return None

    address = attrs.get("address") or (pool.get("id") or "").removeprefix(network + "_")
    if not address:
        return None
    name = attrs.get("name") or "Unnamed pool"
    buy_share = buys / trades if trades else 0
    volume_liquidity = volume / liquidity if liquidity else 0

    # Activity score (0-100). Deliberately excludes contract security.
    score = 0
    score += 25 if liquidity >= 250_000 else 15 if liquidity >= 100_000 else 8
    score += 25 if volume >= 1_000_000 else 15 if volume >= 300_000 else 8
    score += 20 if trades >= 200 else 12 if trades >= 100 else 6
    score += 15 if 0.45 <= buy_share <= 0.70 else 8 if 0.35 <= buy_share <= 0.80 else 0
    score += 15 if 0.5 <= volume_liquidity <= 10 else 7 if volume_liquidity <= 20 else 0
    flags = []
    if buy_share < 0.35:
        flags.append("Sell-heavy trading in last hour")
    if buy_share > 0.80:
        flags.append("Buy-heavy trading; authenticity unverified")
    if volume_liquidity > 20:
        flags.append("Very high 24h volume relative to liquidity")
    if age_hours < 1:
        flags.append("Pool younger than one hour")

    safe_address = urllib.parse.quote(address, safe="")
    return {
        "key": f"{network}:{address}",
        "network": network,
        "address": address,
        "name": name,
        "age_hours": age_hours,
        "pool_class": "NEW POOL" if age_hours <= 72 else "EXISTING POOL",
        "token_age": "UNKNOWN — pool creation does not establish token launch date",
        "discovery_mode": mode,
        "source": DATA_SOURCE,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "contract_security": "NOT VERIFIED",
        "holder_concentration": "NOT VERIFIED",
        "liquidity_lock": "NOT VERIFIED",
        "return_probabilities": "UNAVAILABLE — no validated historical probability model",
        "liquidity": liquidity,
        "volume": volume,
        "buys": buys,
        "sells": sells,
        "trades": trades,
        "buy_share": buy_share,
        "score": score,
        "flags": flags,
        "url": f"https://www.geckoterminal.com/{network}/pools/{safe_address}",
    }


def load_state():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(item) for item in data}
        if isinstance(data, dict):
            # Backward compatible with earlier state file: {"base:address": ...}
            return {str(key) for key in data}
        raise ValueError("State file must contain a JSON object or array")
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot safely load existing alert history: {exc}") from exc


def save_state(seen):
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(sorted(seen), indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE_FILE)


def strategy(item):
    """Non-personalized research process, not a trading recommendation."""
    if item["pool_class"] == "NEW POOL":
        return ("WAIT / RESEARCH: verify token contract, ownership, sellability, "
                "liquidity withdrawal risk and holder distribution before considering exposure")
    return ("RESEARCH / WATCH: verify token inception date, fundamentals, "
            "supply unlocks and longer price history before considering any entry")


def horizon_notes():
    return (
        "3 months: monitor liquidity persistence, activity and severe downside risk; "
        "probability unavailable.\n"
        "12 months: investigate adoption, supply dilution and token survival; "
        "probability unavailable.\n"
        "3 years: investigate team execution, security history and long-term tokenomics; "
        "probability unavailable."
    )


def send_telegram(item):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    flags = "; ".join(item["flags"]) if item["flags"] else "No additional activity flags triggered"
    message = (
        "🔎 CRYPTO-ORACLE Z — UNVERIFIED RESEARCH LEAD\n"
        f"Network: {item['network']}\n"
        f"Pool: {item['name']}\n"
        f"Pool classification: {item['pool_class']}\n"
        f"TOKEN AGE: {item['token_age']}\n"
        f"Activity score: {item['score']}/100 (NOT safety or success probability)\n"
        f"Pool age: {item['age_hours']:.1f} hours\n"
        f"Liquidity: ${item['liquidity']:,.0f}\n"
        f"24h volume: ${item['volume']:,.0f}\n"
        f"1h trades: {item['trades']} ({item['buys']} buys / {item['sells']} sells)\n"
        f"1h buy share: {item['buy_share']:.0%}\n"
        f"Activity flags: {flags}\n"
        f"Security: {item['contract_security']}; holders: {item['holder_concentration']}; "
        f"liquidity lock: {item['liquidity_lock']}\n"
        f"Research strategy: {strategy(item)}\n"
        f"{horizon_notes()}\n"
        f"Success / 10x / 100x probabilities: {item['return_probabilities']}\n"
        f"Source: {item['source']}\n"
        f"Retrieved UTC: {item['observed_at']}\n"
        f"Pool link: {item['url']}\n\n"
        "NOT A BUY SIGNAL. No token audit, liquidity-lock check, holder audit, "
        "or price forecast has been performed."
    )
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST"
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram API did not confirm delivery")


def main():
    seen = load_state()
    candidates = []
    keys_in_run = set()
    warnings = []
    errors = []
    total_checked = 0
    for network in NETWORKS:
        network_checked = 0
        for mode in SCAN_MODES:
            for page in range(1, PAGES_PER_NETWORK + 1):
                try:
                    url = f"{API}/networks/{network}/{mode}?page={page}"
                    payload = fetch_json(url)
                    pools = payload.get("data") or []
                    network_checked += len(pools)
                    total_checked += len(pools)
                    for pool in pools:
                        item = inspect(pool, network, mode)
                        if item and item["key"] not in keys_in_run:
                            candidates.append(item)
                            keys_in_run.add(item["key"])
                    if not pools:
                        break
                except (urllib.error.URLError, ValueError, KeyError, TimeoutError, OSError) as exc:
                    detail = f"{network} {mode} page {page}: {type(exc).__name__}: {exc}"
                    if (isinstance(exc, urllib.error.HTTPError) and exc.code == 429
                            and total_checked > 0):
                        warnings.append(f"Incomplete scan after rate limiting: {detail}")
                    else:
                        errors.append(detail)
                    break
                finally:
                    time.sleep(REQUEST_DELAY_SECONDS)
        print(f"{network}: checked {network_checked} pool observations", flush=True)

    # A market-activity ranking, not a safety or investment assessment.
    candidates.sort(key=lambda item: (item["score"], item["liquidity"]), reverse=True)
    delivered = 0
    for item in candidates:
        if delivered >= MAX_ALERTS_PER_RUN:
            break
        if item["key"] in seen:
            continue
        try:
            send_telegram(item)
        except (urllib.error.URLError, ValueError, RuntimeError, TimeoutError, OSError) as exc:
            errors.append(f"Telegram delivery failed for {item['key']}: {type(exc).__name__}: {exc}")
            continue
        seen.add(item["key"])
        save_state(seen)
        delivered += 1
        time.sleep(1)

    print(f"Total pool observations checked: {total_checked}", flush=True)
    print(f"Candidates found: {len(candidates)}; alerts delivered: {delivered}", flush=True)
    for warning in warnings:
        print(f"WARNING: {warning}", flush=True)
    for error in errors:
        print(f"ERROR: {error}", flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
