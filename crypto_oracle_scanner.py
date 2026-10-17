"""CRYPTO-ORACLE X100 v2: research-only new-pool discovery.

Market data: GeckoTerminal public API. This is not a contract-security audit,
verification of trading legitimacy, or investment recommendation.
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
NETWORKS = ("solana", "base")
HEADERS = {
    "Accept": "application/json;version=20230302",
    "User-Agent": "CRYPTO-ORACLE-X100/2.0",
}
MIN_LIQUIDITY_USD = 50_000
MIN_24H_VOLUME_USD = 100_000
MIN_1H_TRANSACTIONS = 40
MAX_POOL_AGE_HOURS = 72
PAGES_PER_NETWORK = 3  # GeckoTerminal typically returns 20 pools per page.
MAX_ALERTS_PER_RUN = 10
STATE_FILE = pathlib.Path("reported_pools.json")


def fetch_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def inspect(pool, network):
    attributes = pool.get("attributes") or {}
    created = attributes.get("pool_created_at")
    if not created:
        return None
    try:
        timestamp = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        age_hours = (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds() / 3600
    except (TypeError, ValueError):
        return None
    if not 0 <= age_hours <= MAX_POOL_AGE_HOURS:
        return None

    liquidity = number(attributes.get("reserve_in_usd"))
    volume = number((attributes.get("volume_usd") or {}).get("h24"))
    hour = (attributes.get("transactions") or {}).get("h1") or {}
    buys = int(number(hour.get("buys")))
    sells = int(number(hour.get("sells")))
    if (liquidity < MIN_LIQUIDITY_USD
            or volume < MIN_24H_VOLUME_USD
            or buys + sells < MIN_1H_TRANSACTIONS):
        return None

    address = attributes.get("address") or (pool.get("id") or "").removeprefix(network + "_")
    if not address:
        return None
    return {
        "network": network,
        "address": address,
        "name": attributes.get("name") or "Unnamed pool",
        "age_hours": round(age_hours, 1),
        "liquidity_usd": round(liquidity),
        "volume_24h_usd": round(volume),
        "buys_1h": buys,
        "sells_1h": sells,
        "url": f"https://www.geckoterminal.com/{network}/pools/{urllib.parse.quote(address, safe='')}",
    }


def load_state():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except (ValueError, OSError):
        return set()


def save_state(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen), indent=2) + "\n", encoding="utf-8")


def send_telegram(item):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    message = (
        "🔎 CRYPTO-ORACLE X100 — UNVERIFIED RESEARCH LEAD\n"
        f"Network: {item['network']}\n"
        f"Pool: {item['name']}\n"
        f"Age: {item['age_hours']} hours\n"
        f"Liquidity: ${item['liquidity_usd']:,}\n"
        f"24h volume: ${item['volume_24h_usd']:,}\n"
        f"1h transactions: {item['buys_1h'] + item['sells_1h']} "
        f"({item['buys_1h']} buys / {item['sells_1h']} sells)\n"
        f"Pool: {item['url']}\n\n"
        "NOT A BUY SIGNAL. Contract safety, liquidity locks, ownership, "
        "holder concentration and trading authenticity are NOT verified."
    )
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected alert")


def main():
    seen = load_state()
    candidates = []
    errors = []
    total_checked = 0
    for network in NETWORKS:
        network_checked = 0
        for page in range(1, PAGES_PER_NETWORK + 1):
            try:
                url = f"{API}/networks/{network}/new_pools?page={page}"
                payload = fetch_json(url)
                pools = payload.get("data") or []
                network_checked += len(pools)
                total_checked += len(pools)
                for pool in pools:
                    item = inspect(pool, network)
                    if item and f"{network}:{item['address']}" not in seen:
                        candidates.append(item)
                if not pools:
                    break
            except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as exc:
                errors.append(f"{network} page {page}: {type(exc).__name__}: {exc}")
                break
            time.sleep(2)  # Be considerate of public API rate limits.
        print(f"{network}: checked {network_checked} pools", flush=True)

    # Highest liquidity first; a discovery heuristic, not a safety score.
    candidates.sort(key=lambda item: item["liquidity_usd"], reverse=True)
    delivered = 0
    for item in candidates[:MAX_ALERTS_PER_RUN]:
        key = f"{item['network']}:{item['address']}"
        try:
            send_telegram(item)
        except (urllib.error.URLError, ValueError, RuntimeError, TimeoutError) as exc:
            errors.append(f"Telegram delivery failed for {key}: {type(exc).__name__}: {exc}")
            continue
        seen.add(key)
        save_state(seen)
        delivered += 1
        time.sleep(1)

    print(f"Total pools checked: {total_checked}", flush=True)
    print(f"Candidates found: {len(candidates)}; alerts delivered: {delivered}", flush=True)
    for error in errors:
        print(f"ERROR: {error}", flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
