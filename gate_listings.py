"""Read-only snapshot of which base assets trade on Gate Spot against USDT.

Public endpoint only (api.gateio.ws /spot/currency_pairs). No account, order or
key access. Research use: lets a token screen be filtered to what is buyable on
Gate. It changes no gate, threshold or trading flag.

Usage: python gate_listings.py [SYMBOL ...]
Prints one `GATE_LISTINGS` summary line, one `GATE_BASES` line per 100 symbols,
and, when symbols are given, one `GATE_CHECK SYMBOL TRADABLE|NOT_LISTED` line each.
"""
import datetime as dt
import json
import sys
import urllib.request
from urllib.parse import urlparse

URL = 'https://api.gateio.ws/api/v4/spot/currency_pairs'
MAX_BYTES = 20_000_000


def allowed(url):
    parts = urlparse(url)
    return parts.scheme == 'https' and parts.hostname == 'api.gateio.ws' and not parts.username and not parts.password


def fetch(url=URL, timeout=30):
    if not allowed(url):
        raise ValueError('Outside the public Gate host')
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'crypto-oracle-research/1'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Gate response too large')
    return json.loads(raw)


def tradable_usdt_bases(pairs):
    """Base symbols with a tradable normal USDT pair. Unreadable input raises, never guesses."""
    if not isinstance(pairs, list) or not pairs:
        raise ValueError('Gate pair list missing or empty')
    bases = set()
    for pair in pairs:
        if not isinstance(pair, dict) or not isinstance(pair.get('id'), str):
            raise ValueError('Malformed Gate pair record')
        if pair.get('quote') != 'USDT' or pair.get('trade_status') != 'tradable' or pair.get('type', 'normal') != 'normal':
            continue
        base = pair.get('base')
        if isinstance(base, str) and base:
            bases.add(base.upper())
    if not bases:
        raise ValueError('No tradable USDT pairs found; refusing to report an empty venue')
    return sorted(bases)


def check(bases, symbols):
    listed = set(bases)
    return {s.upper(): ('TRADABLE' if s.upper() in listed else 'NOT_LISTED') for s in symbols}


def main(argv, fetcher=fetch, out=print):
    bases = tradable_usdt_bases(fetcher())
    out('GATE_LISTINGS ' + json.dumps(dict(retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(), tradable_usdt_bases=len(bases),
                                         source=URL, note='Spot only; tradable normal USDT pairs')))
    for i in range(0, len(bases), 100):
        out('GATE_BASES ' + ' '.join(bases[i:i + 100]))
    for symbol, status in check(bases, argv).items():
        out(f'GATE_CHECK {symbol} {status}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
