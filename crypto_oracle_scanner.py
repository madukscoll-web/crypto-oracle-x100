"""CRYPTO-ORACLE X100: research-only new-pool watcher (Solana + Base).
Python 3.10+, standard library only. No trading, wallet connection, or safety certification.
"""
import json, time, urllib.request, urllib.error, datetime, os, pathlib

BASE = 'https://api.geckoterminal.com/api/v2'
HEADERS = {'Accept': 'application/json;version=20230203', 'User-Agent': 'CryptoOracleResearch/0.1'}
NETWORKS = ('solana', 'base')
INTERVAL_SECONDS = 75  # 2 requests / 75 seconds; below documented ~10/min public limit
MIN_LIQUIDITY_USD = 50_000
MIN_24H_VOLUME_USD = 100_000
MIN_TXNS_1H = 40
MAX_POOL_AGE_HOURS = 72
LOG = pathlib.Path(__file__).with_name('crypto_oracle_candidates.jsonl')


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def inspect(pool, network):
    attrs = pool.get('attributes') or {}
    created = attrs.get('pool_created_at')
    if not created:
        return None
    try:
        dt = datetime.datetime.fromisoformat(created.replace('Z', '+00:00'))
        age_hours = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 3600
    except ValueError:
        return None
    liquidity = number(attrs.get('reserve_in_usd'))
    volume = number((attrs.get('volume_usd') or {}).get('h24'))
    txns = (attrs.get('transactions') or {}).get('h1') or {}
    buys, sells = int(number(txns.get('buys'))), int(number(txns.get('sells')))
    if not (0 <= age_hours <= MAX_POOL_AGE_HOURS and liquidity >= MIN_LIQUIDITY_USD and
            volume >= MIN_24H_VOLUME_USD and buys + sells >= MIN_TXNS_1H):
        return None
    address = (attrs.get('address') or pool.get('id') or '').removeprefix(network + '_')
    return {
        'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'network': network, 'pool_name': attrs.get('name'), 'pool_address': address,
        'pool_age_hours': round(age_hours, 2), 'liquidity_usd': round(liquidity, 2),
        'volume_24h_usd': round(volume, 2), 'buys_1h': buys, 'sells_1h': sells,
        'price_change_1h_pct': (attrs.get('price_change_percentage') or {}).get('h1'),
        'pool_url': f'https://www.geckoterminal.com/{network}/pools/{address}',
        'status': 'UNVERIFIED RESEARCH LEAD — NOT A BUY SIGNAL',
    }


def main():
    print('CRYPTO-ORACLE X100 | RESEARCH ONLY | Ctrl+C to stop', flush=True)
    print('Security, holders, mint controls, and sellability NOT verified.', flush=True)
    seen = set()
    if LOG.exists():
        for line in LOG.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
                seen.add((item['network'], item['pool_address']))
            except (ValueError, KeyError):
                pass
    while True:
        for network in NETWORKS:
            try:
                url = f'{BASE}/networks/{network}/new_pools?include=base_token%2Cquote_token&page=1'
                payload = get_json(url)
                pools = payload.get('data') or []
                print(f'{datetime.datetime.now().isoformat(timespec="seconds")} {network}: {len(pools)} pools reviewed', flush=True)
                for pool in pools:
                    item = inspect(pool, network)
                    if not item:
                        continue
                    key = (network, item['pool_address'])
                    if key in seen:
                        continue
                    seen.add(key)
                    with LOG.open('a', encoding='utf-8') as f:
                        f.write(json.dumps(item, ensure_ascii=False) + '\n')
                    print('\nRESEARCH LEAD (NOT SAFE TO BUY):\n' + json.dumps(item, indent=2), flush=True)
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
                print(f'{network} fetch failed: {exc}', flush=True)
            time.sleep(4)
        time.sleep(INTERVAL_SECONDS)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped.')
