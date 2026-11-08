"""Fair bounded tracked-pool retries. Scheduling never grants alert eligibility.

Priority setups receive a bounded age credit, rather than an absolute bucket
that could indefinitely starve ordinary pools. Attempt timestamps advance even
when a provider fails, independently of successful evidence observations.
"""
import datetime as dt

PRIORITY_AGE_CREDIT_SECONDS = 3600
MAX_REVISITS = 12


def _timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def select(watchlist, limit, *, excluded=(), now=None):
    """Select eligible retries and retain their attempt time in existing state.

    Finite stable queues are oldest-attempt-first with at most one hour of
    priority preference. A failed request therefore moves behind older work.
    Repeated arrivals and unavailable providers do not warrant complete-market
    coverage claims; the request cap is unchanged.
    """
    if not isinstance(watchlist, dict):
        raise ValueError('Watchlist must be an object')
    if type(limit) is not int or not 1 <= limit <= MAX_REVISITS:
        raise ValueError('Revisit limit outside bounded range')
    now = now or dt.datetime.now(dt.timezone.utc)
    if not isinstance(now, dt.datetime) or now.tzinfo is None:
        raise ValueError('Timezone-aware scheduling time required')
    current = now.timestamp()
    excluded = set(excluded)
    candidates = []
    for key, record in watchlist.items():
        if (key in excluded or not isinstance(key, str) or
                not isinstance(record, dict) or
                not isinstance(record.get('network'), str) or not record['network'] or
                not isinstance(record.get('pool_address'), str) or not record['pool_address']):
            continue
        times = [_timestamp(record.get(field)) for field in
                 ('revisit_attempted_at', 'evidence_checked_at', 'observed_at')]
        last = max((min(t, current) for t in times if t is not None), default=0)
        credit = PRIORITY_AGE_CREDIT_SECONDS if record.get('setup') == 'PRIORITY VERIFY' else 0
        candidates.append((last-credit, last, key, record))
    selected = [(key, record) for _, _, key, record in sorted(candidates)[:limit]]
    for _, record in selected:
        record['revisit_attempted_at'] = now.isoformat()
    return selected
