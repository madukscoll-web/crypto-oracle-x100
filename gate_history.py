"""Gate spot venue history and book depth for exchange-listed research assets.

Public Gate market-data endpoints only; no account, wallet or order methods.

This is VENUE evidence: the lowest daily-candle low on Gate spot since its first
candle, and top-of-book depth on Gate. It is not a verified lifetime all-time
low (other venues, pre-listing trading and migrations are not covered) and it
never grants eligibility, BUY admission or order permission. USDT quotes are
treated as an approximation of USD and labelled as such.
"""
import datetime as dt
import math
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

BASE = 'https://api.gateio.ws/api/v4'
PAIR = re.compile(r'[A-Z0-9]{1,20}_USDT')
DAY = 86400
WINDOW_DAYS = 990          # Gate returns at most 1000 points per from/to request
MAX_PAGES = 3              # ~8 years of daily history per asset
SLACK_DAYS = 7             # first candle this far inside a window means listing began there
BOOK_LEVELS = 20
LIMITATION = ('Gate spot venue only, daily candles, USDT quote treated as USD. Other venues, pre-listing '
              'trading, migrations and splits are not covered; not a verified lifetime all-time low.')


def _iso(timestamp):
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat()


def _decimal(value):
    if isinstance(value, bool):
        raise ValueError('Invalid number')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('Invalid number') from exc
    if not number.is_finite():
        raise ValueError('Non-finite number')
    return number


def _pair(pair):
    if not isinstance(pair, str) or not PAIR.fullmatch(pair):
        raise ValueError('Gate USDT spot pair required')
    return pair


def candle_url(pair, start, end):
    return f'{BASE}/spot/candlesticks?currency_pair={_pair(pair)}&interval=1d&from={int(start)}&to={int(end)}'


def book_url(pair):
    return f'{BASE}/spot/order_book?currency_pair={_pair(pair)}&limit={BOOK_LEVELS}&with_id=true'


def parse_candles(rows, now):
    """Closed daily candles as (timestamp, low, high). Rejects malformed data."""
    if not isinstance(rows, list):
        raise ValueError('Malformed Gate candle response')
    parsed = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ValueError('Malformed Gate candle')
        try:
            timestamp = int(row[0])
            high, low = _decimal(row[3]), _decimal(row[4])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError('Invalid Gate candle values') from exc
        if timestamp <= 0 or timestamp + DAY > now:
            continue  # never use an incomplete candle
        if low <= 0 or high <= 0 or low > high:
            continue  # unusable quote; never treated as a real low of zero
        if timestamp in parsed:
            raise ValueError('Duplicate Gate candle timestamps')
        parsed[timestamp] = (low, high)
    return [(t, *parsed[t]) for t in sorted(parsed)]


def collect(get, pair, *, now, max_pages=MAX_PAGES):
    """Page daily candles backwards from today until the pair's first candle."""
    _pair(pair)
    now = int(now)
    end = now // DAY * DAY
    candles, urls, pages, reached_listing = {}, [], 0, False
    while pages < max_pages:
        start = end - WINDOW_DAYS * DAY
        url = candle_url(pair, start, end)
        rows = get(url)
        pages += 1
        urls.append(url)
        page = parse_candles(rows, now)
        for timestamp, low, high in page:
            candles[timestamp] = (low, high)
        if not page or page[0][0] > start + SLACK_DAYS * DAY:
            reached_listing = True
            break
        end = start - DAY
    if not candles:
        raise ValueError('No usable Gate daily candles')
    ordered = sorted(candles)
    low_at = min(ordered, key=lambda t: (candles[t][0], t))
    gaps = [(b - a) // DAY for a, b in zip(ordered, ordered[1:])]
    return dict(
        organization='gate', pair=pair, source_urls=urls, observed_at=_iso(now),
        earliest_candle_at=_iso(ordered[0]), latest_candle_at=_iso(ordered[-1]),
        candles=len(ordered), pages=pages,
        minimum_price_usd=str(candles[low_at][0]), minimum_at=_iso(low_at),
        maximum_gap_days=max(gaps, default=0),
        reaches_first_candle=reached_listing,
        coverage='GATE_SPOT_DAILY_SINCE_FIRST_CANDLE' if reached_listing else 'GATE_SPOT_DAILY_TRUNCATED',
        venue_lifetime_complete=False, limitation=LIMITATION)


def collect_book(get, pair, *, now):
    """Top-of-book depth within 1% of mid. A lower bound: only the top levels are read."""
    raw = get(book_url(pair))
    bids, asks = (raw or {}).get('bids'), (raw or {}).get('asks')
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        raise ValueError('Gate order book unavailable')

    def levels(side):
        out = []
        for level in side:
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                raise ValueError('Malformed Gate book level')
            price, size = _decimal(level[0]), _decimal(level[1])
            if price <= 0 or size < 0:
                raise ValueError('Invalid Gate book level')
            out.append((price, size))
        return out
    bids, asks = levels(bids), levels(asks)
    best_bid, best_ask = max(p for p, _ in bids), min(p for p, _ in asks)
    if best_bid >= best_ask:
        raise ValueError('Crossed Gate order book')
    mid = (best_bid + best_ask) / 2
    return dict(
        pair=_pair(pair), observed_at=_iso(int(now)), source_url=book_url(pair),
        best_bid=str(best_bid), best_ask=str(best_ask),
        spread_bps=str(((best_ask - best_bid) / mid * 10000).quantize(Decimal('0.1'))),
        bid_depth_usdt_1pct=str(sum(p * s for p, s in bids if p >= mid * Decimal('0.99')).quantize(Decimal('1'))),
        ask_depth_usdt_1pct=str(sum(p * s for p, s in asks if p <= mid * Decimal('1.01')).quantize(Decimal('1'))),
        levels_read=BOOK_LEVELS, scope='Gate venue top-of-book lower bound; not executable size or other venues')


def collect_all(get, pair, *, now):
    """History is required; a missing book is reported, never fatal."""
    result = dict(history=collect(get, pair, now=now), book=None, book_error=None)
    try:
        result['book'] = collect_book(get, pair, now=now)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
        result['book_error'] = type(exc).__name__
    return result


def _host_ok(url):
    parts = urlsplit(url if isinstance(url, str) else '')
    return parts.scheme == 'https' and parts.hostname == 'api.gateio.ws' and not parts.username and not parts.password


def _stamp(value):
    parsed = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed.timestamp()


def validate(evidence, pair, now, *, max_age_seconds=7200):
    """Re-check stored venue evidence at replay; return it unchanged or raise."""
    if not isinstance(evidence, dict) or not isinstance(evidence.get('history'), dict):
        raise ValueError('Venue history missing')
    history = evidence['history']
    if history.get('organization') != 'gate' or history.get('pair') != _pair(pair):
        raise ValueError('Venue history identity mismatch')
    urls = history.get('source_urls')
    if not isinstance(urls, list) or not urls or not all(_host_ok(u) for u in urls):
        raise ValueError('Untrusted venue history provenance')
    if history.get('venue_lifetime_complete') is not False:
        raise ValueError('Venue history cannot claim lifetime completeness')
    low = _decimal(history.get('minimum_price_usd'))
    if low <= 0:
        raise ValueError('Invalid venue minimum')
    first, low_at, last = (_stamp(history.get(k)) for k in ('earliest_candle_at', 'minimum_at', 'latest_candle_at'))
    if not first <= low_at <= last <= now:
        raise ValueError('Venue history dates inconsistent')
    observed = _stamp(history.get('observed_at'))
    if observed > now or now - observed > max_age_seconds:
        raise ValueError('Stale venue history')
    count = history.get('candles')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('Invalid venue candle count')
    book = evidence.get('book')
    if book is not None:
        if not isinstance(book, dict) or book.get('pair') != pair or not _host_ok(book.get('source_url')):
            raise ValueError('Venue book identity mismatch')
        for key in ('best_bid', 'best_ask', 'spread_bps', 'bid_depth_usdt_1pct', 'ask_depth_usdt_1pct'):
            value = _decimal(book.get(key))
            if value < 0 or (key in ('best_bid', 'best_ask') and value == 0):
                raise ValueError('Invalid venue book value')
    return evidence


def below_reported_low(history, provider_low, tolerance=Decimal('0.95')):
    """True when Gate traded materially under a provider-reported all-time low."""
    return _decimal(history['minimum_price_usd']) < _decimal(provider_low) * tolerance


def covers_date(history, moment):
    """Does Gate's first candle precede the date of the reported low?"""
    return _stamp(history['earliest_candle_at']) <= moment
