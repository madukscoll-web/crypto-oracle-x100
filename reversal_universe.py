"""Bounded rotating Gate Spot research universe, with explicit coverage gaps.

Selection uses exchange metadata and quoted turnover, never token ticker identity.
No investment authorization, messages, account access or order submission.
"""
import datetime as dt
import math
from collections import Counter

from altcoin_reversal_cli import run
from altcoin_reversal_research import eligible_symbol
from gate_spot_research import PublicGate
from provider_session import Session


def active_pair(row, now):
    if not isinstance(row, dict):
        return False
    pair, base = row.get('id'), row.get('base')
    return (isinstance(base, str) and eligible_symbol(base)
            and base not in ('BTC', 'WBTC', 'WETH', 'WSTETH', 'STETH', 'PAXG', 'XAUT')
            and pair == base + '_USDT' and row.get('quote') == 'USDT'
            and row.get('type') == 'normal' and row.get('trade_status') == 'tradable'
            and row.get('st_tag') is False and row.get('delisting_time') in (None, 0)
            and all(type(row.get(k)) is int and 0 <= row[k] <= now
                    for k in ('buy_start', 'sell_start')))


def collect(*, fetch=None, now=None, cursor=0, batch_size=6, allowed_pairs=None):
    if type(batch_size) is not int or not 1 <= batch_size <= 10:
        raise ValueError('Research batch must contain 1 to 10 pairs')
    if type(cursor) is not int or cursor < 0:
        raise ValueError('Invalid universe cursor')
    if fetch is None:
        with Session(max_requests=2 + 4*batch_size, max_seconds=100,
                     max_request_seconds=5) as session:
            result = collect(fetch=session.get, now=now, cursor=cursor, batch_size=batch_size, allowed_pairs=allowed_pairs)
            result['provider_session'] = session.summary()
            return result
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    report = dict(scope='BOUNDED_ROTATING_SPOT_RESEARCH', buy_authorized=False,
                  orders_allowed=False, telegram_eligible=False, results=[],
                  next_cursor=cursor, status_counts={}, coverage={}, errors=[],
                  as_of=dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                  limitations=['Turnover is an exchange observation, not proof of organic volume.',
                               'Pair metadata is not exact-contract identity or independent security.',
                               'Historical paper observations do not establish strategy validation.',
                               'Unassessed pairs are deferred, never classified as negative setups.'])
    gate = PublicGate(fetch)
    try:
        metadata = gate.get('/spot/currency_pairs')
        tickers = gate.get('/spot/tickers')
        if not isinstance(metadata, list) or not isinstance(tickers, list):
            raise ValueError('Malformed universe response')
        # Duplicates or malformed turnover cannot be silently selected.
        ids = Counter(row.get('id') for row in metadata if isinstance(row, dict))
        ticker_ids = Counter(row.get('currency_pair') for row in tickers if isinstance(row, dict))
        volumes = {}
        for ticker in tickers:
            if not isinstance(ticker, dict):
                continue
            pair = ticker.get('currency_pair')
            try:
                value = ticker['quote_volume']
                if isinstance(value, bool):
                    raise ValueError('Boolean turnover')
                volume = float(value)
                if not math.isfinite(volume) or volume < 0 or ticker_ids[pair] != 1:
                    continue
                volumes[pair] = volume
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
        active = sorted(row['id'] for row in metadata
                        if active_pair(row, now) and ids[row['id']] == 1)
        eligible = [pair for pair in active if volumes.get(pair, -1) >= 1_000_000]
        all_liquid = len(eligible)
        if allowed_pairs is not None:
            eligible = [pair for pair in eligible if pair in allowed_pairs]
        unknown = sum(pair not in volumes for pair in active)
        start = cursor % len(eligible) if eligible else 0
        selected = (eligible[start:] + eligible[:start])[:batch_size]
        report['coverage'] = dict(catalog_records=len(metadata), active_altcoin_pairs=len(active),
                                  liquid_eligible_pairs=len(eligible), unknown_turnover=unknown,
                                  selected_pairs=len(selected), deferred_pairs=len(eligible)-len(selected),
                                  minimum_reported_quote_volume_usdt=1_000_000,
                                  all_liquid_eligible_pairs=all_liquid,
                                  restricted_research_scope=allowed_pairs is not None)
        report['next_cursor'] = (start + len(selected)) % len(eligible) if eligible else 0
        for interval in ('1d', '1w'):
            rows = run(selected, interval, fetch=fetch, now=now)['results']
            for row in rows:
                row['interval'] = interval
                row['reported_quote_volume_usdt'] = volumes[row['pair']]
            report['results'].extend(rows)
        report['status_counts'] = dict(Counter(row['status'] for row in report['results']))
        report['coverage'].update(
            timeframe_assessments=len(report['results']),
            unavailable=sum(row['status'] != 'RESEARCH_ONLY' for row in report['results']),
            technical_watches=sum((row.get('research') or {}).get('classification') in
                                  ('EARLY REVERSAL WATCH', 'TECHNICAL REVERSAL WATCH')
                                  for row in report['results']))
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        report['errors'].append('Universe unavailable: ' + type(exc).__name__)
        report['coverage']['universe_status'] = 'UNAVAILABLE'
    report['universe_evidence'] = gate.evidence
    return report
