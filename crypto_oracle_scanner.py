"""CRYPTO-ORACLE X100: hourly research-only new-pool discovery.

Data: GeckoTerminal public API. Not a security audit or buy recommendation.
"""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.geckoterminal.com/api/v2'
NETWORKS = ('solana', 'base')
HEADERS = {'Accept': 'application/json;version=20230302', 'User-Agent': 'CryptoOracleResearch/0.2'}
MIN_LIQUIDITY_USD = 50_000
MIN_24H_VOLUME_USD = 100_000
MIN_1H_TRANSACTIONS = 40
MAX_POOL_AGE_HOURS = 72
STATE_FILE = pathlib.Path('reported_pools.json')


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def inspect(pool, network):
    a = pool.get('attributes') or {}
    created = a.get('pool_created_at')
    if not created:
        return None
    try:
        timestamp = dt.datetime.fromisoformat(created.replace('Z', '+00:00'))
        age = (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds() / 3600
    except (ValueError, TypeError):
        return None
    if not 0 <= age <= MAX_POOL_AGE_HOURS:
        return None
    liquidity = num(a.get('reserve_in_usd'))
    volume = num((a.get('volume_usd') or {}).get('h24'))
    txns = (a.get('transactions') or {}).get('h1') or {}
    buys, sells = int(num(txns.get('buys'))), int(num(txns.get('sells')))
    if liquidity < MIN_LIQUIDITY_USD or volume < MIN_24H_VOLUME_USD or buys + sells < MIN_1H_TRANSACTIONS:
        return None
    address = a.get('address') or pool.get('id', '').removeprefix(network + '_')
    if not address:
        return None
    return {
        'network': network, 'address': address, 'name': a.get('name') or 'Unnamed pool',
        'age_hours': round(age, 1), 'liquidity_usd': round(liquidity),
        'volume_24h_usd': round(volume), 'buys_1h': buys, 'sells_1h': sells,
        'url': f'https://www.geckoterminal.com/{network}/pools/{urllib.parse.quote(address, safe="")}',
    }


def load_state():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        return set(data) if isinstance(data, list) else set()
    except (ValueError, OSError):
        return set()


def save_state(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen), indent=2) + '\n', encoding='utf-8')


def send_telegram(item):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        raise RuntimeError('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID')
    message = (
        '🔎 CRYPTO-ORACLE X100 — UNVERIFIED RESEARCH LEAD\n'
        f'Network: {item["network"]}\nPool: {item["name"]}\n'
        f'Age: {item["age_hours"]}h\nLiquidity: ${item["liquidity_usd"]:,}\n'
        f'24h volume: ${item["volume_24h_usd"]:,}\n'
        f'1h transactions: {item["buys_1h"] + item["sells_1h"]} '
        f'({item["buys_1h"]} buys, {item["sells_1h"]} sells)\n'
        f'{item["url"]}\n\n'
        'NOT A BUY SIGNAL. Contract safety, liquidity locks, ownership, '
        'holder concentration and authenticity are NOT verified.'
    )
    body = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage', data=body, method='POST'
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram rejected alert')


def main():
    seen = load_state()
    candidates = []
    errors = []
    for network in NETWORKS:
        try:
            payload = fetch_json(f'{API}/networks/{network}/new_pools?page=1')
            pools = payload.get('data') or []
            print(f'{network}: checked {len(pools)} pools', flush=True)
            for pool in pools:
                item = inspect(pool, network)
                if item and f'{network}:{item["address"]}' not in seen:
                    candidates.append(item)
        except (urllib.error.URLError, ValueError, KeyError) as exc:
            errors.append(f'{network}: {type(exc).__name__}: {exc}')
        time.sleep(2)

    delivered = 0
    for item in candidates[:10]:  # limit notification bursts
        key = f'{item["network"]}:{item["address"]}'
        try:
            send_telegram(item)
        except (urllib.error.URLError, ValueError, RuntimeError) as exc:
            errors.append(f'Telegram delivery failed for {key}: {type(exc).__name__}: {exc}')
            continue
        seen.add(key)
        save_state(seen)
        delivered += 1
        time.sleep(1)
    print(f'Candidates found: {len(candidates)}; alerts delivered: {delivered}', flush=True)
    for err in errors:
        print(f'ERROR: {err}', flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
