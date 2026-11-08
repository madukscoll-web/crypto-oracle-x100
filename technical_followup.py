"""Prospective sampling of delivered technical hypotheses, never paper fills.

No historic price, entry, stop execution, fees or return is reconstructed. Sampling
begins with the first fresh book after deployment. Between-sample paths are unknown.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import time
from gate_spot_research import PublicGate, analyze_book, decimal
from provider_session import Session
from research_notice import _issue

MAX_HYPOTHESES = 64
MAX_SAMPLES = 256


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def timestamp(value):
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timezone required')
    return stamp.timestamp()


def load(path):
    path = pathlib.Path(path)
    if not path.exists():
        return {'version': 1, 'hypotheses': {}}
    data = json.loads(path.read_text())
    if data.get('version') != 1 or not isinstance(data.get('hypotheses'), dict):
        raise ValueError('Invalid follow-up state; refusing reset')
    return data


def identity(pair, receipt):
    if not re.fullmatch(r'[A-Z0-9_.-]+_USDT', pair):
        raise ValueError('Invalid research pair')
    anchor = {k: receipt[k] for k in ('delivered_at', 'interval', 'entry_trigger', 'invalidation')}
    timestamp(anchor['delivered_at'])
    if decimal(anchor['entry_trigger']) <= decimal(anchor['invalidation']):
        raise ValueError('Invalid research levels')
    return hashlib.sha256(canonical({'pair': pair, **anchor})).hexdigest(), anchor


def observe(pair, receipt, previous, gate, now, clock=None):
    identifier, anchor = identity(pair, receipt)
    if timestamp(anchor['delivered_at']) > now:
        raise ValueError('Future receipt')
    row = dict(previous) if previous else {'pair': pair, 'alert': anchor, 'samples': []}
    if row['pair'] != pair or row['alert'] != anchor:
        raise ValueError('Follow-up identity mismatch')
    samples = list(row['samples'])
    if len(samples) >= MAX_SAMPLES:
        return identifier, row, 'SAMPLE_CAPACITY_REACHED'
    if samples and now - timestamp(samples[-1]['observed_at']) < 1800:
        return identifier, row, 'RECENT_SAMPLE'
    metadata = gate.get('/spot/currency_pairs/' + pair)
    if (metadata.get('id') != pair or metadata.get('base') != pair[:-5] or
            metadata.get('quote') != 'USDT' or metadata.get('type') != 'normal' or
            metadata.get('trade_status') != 'tradable' or metadata.get('st_tag') is not False):
        raise ValueError('Pair no longer eligible for observation')
    # Retry only an expired snapshot, once, inside the caller's request budget.
    # Malformed or contradictory books remain rejected without a retry loop.
    for attempt in range(2):
        raw = gate.get('/spot/order_book', {'currency_pair': pair, 'limit': 20, 'with_id': 'true'})
        now = clock() if clock else now
        try:
            metrics = analyze_book(raw, '100', now)
            break
        except ValueError as exc:
            if attempt or str(exc) != 'Stale/future order book':
                raise
    provider_at = metrics['provider_current_ms']/1000
    if samples and provider_at <= samples[-1]['provider_current_ms']/1000:
        return identifier, row, 'NONADVANCING_PROVIDER_SNAPSHOT'
    midpoint = (decimal(metrics['best_bid']) + decimal(metrics['best_ask']))/2
    sample = {'observed_at': dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
              'provider_current_ms': metrics['provider_current_ms'], 'midpoint_usdt': str(midpoint),
              'best_bid': metrics['best_bid'], 'best_ask': metrics['best_ask'],
              'at_or_below_invalidation_observed': decimal(metrics['best_bid']) <= decimal(anchor['invalidation']),
              'at_or_above_trigger_observed': decimal(metrics['best_ask']) >= decimal(anchor['entry_trigger']),
              'raw_book': raw, 'raw_sha256': hashlib.sha256(canonical(raw)).hexdigest(),
              'source_url': gate.evidence[-1]['url'], 'run_id': os.environ.get('GITHUB_RUN_ID', '')}
    samples.append(sample)
    row.update(samples=samples, monitoring_started_at=samples[0]['observed_at'],
               original_alert_entry_price='UNKNOWN_NOT_RECONSTRUCTED',
               exact_onchain_identity='NOT_ESTABLISHED_BY_PAIR_BOOK', orders_allowed=False, buy_authorized=False)
    return identifier, row, 'OBSERVED'


def summarize(row):
    samples = row['samples']
    first = samples[0]
    start = timestamp(first['observed_at'])
    horizons = []
    for hours in (24, 168, 720):
        eligible = [s for s in samples[1:] if timestamp(s['observed_at']) >= start+hours*3600]
        result = {'hours': hours, 'status': 'PENDING'}
        if eligible:
            match = eligible[0]
            delay = (timestamp(match['observed_at'])-start)/3600-hours
            result.update(status='NO_TIMELY_SAMPLE' if delay > max(6, hours*.1) else 'OBSERVED_PRICE_CHANGE_ONLY',
                          delay_hours=round(delay, 3), observed_at=match['observed_at'])
            if result['status'] == 'OBSERVED_PRICE_CHANGE_ONLY':
                result['midpoint_change_percent'] = str((decimal(match['midpoint_usdt'])/decimal(first['midpoint_usdt'])-1)*100)
        horizons.append(result)
    return {'pair': row['pair'], 'monitoring_started_at': first['observed_at'],
            'sample_count': len(samples), 'last_observed_at': samples[-1]['observed_at'],
            'sampled_invalidation_breach': any(s['at_or_below_invalidation_observed'] for s in samples),
            'between_sample_path': 'UNKNOWN', 'entry_execution': 'NOT_ASSUMED',
            'strategy_return': 'UNKNOWN', 'horizons': horizons}


def collect(receipts, state, fetch, now=None, allowed=()):
    clock = time.time if now is None else lambda: now
    now = clock()
    if state.get('version') != 1 or not isinstance(state.get('hypotheses'), dict):
        raise ValueError('Malformed follow-up state')
    rows = state['hypotheses']
    report = {'scope': 'PROSPECTIVE_HYPOTHESIS_OBSERVATIONS_NOT_STRATEGY_VALIDATION',
              'buy_authorized': False, 'orders_allowed': False, 'outcomes': {}, 'errors': {}}
    candidates = []
    for pair, receipt in receipts.items():
        if pair not in allowed:
            continue
        try:
            key, _ = identity(pair, receipt)
            previous = rows.get(key)
            at = previous['samples'][-1]['observed_at'] if previous and previous['samples'] else ''
            candidates.append((at, pair, key, receipt))
        except (ValueError, TypeError, KeyError, AttributeError):
            report['errors'][pair] = 'INVALID_RECEIPT_OR_STATE'
    gate = PublicGate(fetch)
    for _, pair, key, receipt in sorted(candidates)[:3]:
        if key not in rows and len(rows) >= MAX_HYPOTHESES:
            report['outcomes'][pair] = 'HYPOTHESIS_CAPACITY_REACHED'
            continue
        try:
            identifier, row, status = observe(pair, receipt, rows.get(key), gate, clock(), clock)
            rows[identifier] = row
            report['outcomes'][pair] = status
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
            report['errors'][pair] = type(exc).__name__
    report['hypotheses'] = [summarize(row) for row in rows.values() if row.get('samples')]
    report['limitations'] = ['Selection is delivered technical watches, not all launches or an unbiased historical cohort.',
                            'No original alert fill is reconstructed; monitoring starts at first fresh observation.',
                            'Sampled midpoint changes exclude fees, execution and between-sample excursions.']
    return report


def deliver_invalidations(state, sender, persist, *, now=None, allowed=(), max_per_run=2):
    """Recompute a fresh sampled breach and notify once per delivered hypothesis.

    Only already delivered watches qualify. This is withdrawal of a technical
    hypothesis, never a claim that a stop was executed or a trade existed.
    """
    now = time.time() if now is None else now
    if type(max_per_run) is not int or not 1 <= max_per_run <= 2:
        raise ValueError('Invalidation delivery budget must be one or two attempts')
    summary = dict(delivered=0, failed=0, stale=0, attempted=0,
                   buy_authorized=False, orders_allowed=False, errors={})
    if state.get('version') != 1 or not isinstance(state.get('hypotheses'), dict):
        raise ValueError('Malformed follow-up state')
    for identifier, row in state['hypotheses'].items():
        if summary['attempted'] >= max_per_run:
            break
        if row.get('pair') not in allowed or row.get('invalidation_notified_at'):
            continue
        samples = row.get('samples') or []
        if not samples:
            continue
        try:
            sample = samples[-1]
            if not 0 <= now-timestamp(sample['observed_at']) <= 900:
                summary['stale'] += 1
                continue
            # Never trust attached at_or_below flags or an unbound state key.
            expected, _ = identity(row['pair'], row['alert'])
            if identifier != expected:
                raise ValueError('Invalidation hypothesis binding mismatch')
            raw = sample['raw_book']
            if hashlib.sha256(canonical(raw)).hexdigest() != sample['raw_sha256']:
                raise ValueError('Invalidation book digest mismatch')
            book = analyze_book(raw, '100', now)
            if decimal(book['best_bid']) > decimal(row['alert']['invalidation']):
                continue
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
            summary['errors'][identifier] = type(exc).__name__
            continue
        text = ('INVALIDATED SETUP\n'
                f"Gate Spot: {row['pair']} | timeframe {row['alert']['interval']}\n"
                f"Previously delivered technical hypothesis: {row['alert']['delivered_at']}\n"
                f"Fresh observed best bid {book['best_bid']} USDT is at/below invalidation "
                f"reference {row['alert']['invalidation']} USDT. Withdraw this hypothesis.\n"
                f"Observed UTC: {sample['observed_at']}\n"
                'Sampled book observation only; between-sample path and actual trade execution are unknown. '
                'No stop fill, realized loss, security approval or purchase authority is inferred.\n'
                f"Source: {sample['source_url']}")
        summary['attempted'] += 1
        try:
            if sender(_issue('INVALIDATED SETUP', text)) is not True:
                raise RuntimeError('Telegram receipt unconfirmed')
        except (RuntimeError, OSError, ValueError):
            summary['failed'] += 1
            continue
        row['invalidation_notified_at'] = dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat()
        # Publication failure must surface; do not claim durable deduplication.
        persist(state)
        summary['delivered'] += 1
    return summary


if __name__ == '__main__':
    import technical_watch
    state_path = pathlib.Path('technical_followup_state.json')
    state = load(state_path)
    receipts = json.loads(pathlib.Path('technical_watch_state.json').read_text())['delivered']
    with Session(max_requests=9, max_seconds=20, max_request_seconds=3) as session:
        report = collect(receipts, state, session.get, allowed=technical_watch.policy()['pairs'])
        report['provider_session'] = session.summary()
    def persist(snapshot):
        temporary = state_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(snapshot, indent=2)+'\n')
        temporary.replace(state_path)
    persist(state)
    from telegram_notify import send_research_message
    report['invalidation_delivery'] = deliver_invalidations(
        state, send_research_message, persist, allowed=technical_watch.policy()['pairs'])
    # Asset-level unavailable observations are data degradation, not a crashed
    # batch. Retain them for pipeline_health; unconfirmed delivery stays fatal.
    report['status'] = ('DEGRADED' if report['errors'] or report['invalidation_delivery']['errors']
                        else 'COMPLETED')
    pathlib.Path('technical_followup_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    if report['invalidation_delivery']['failed']:
        raise SystemExit(1)

