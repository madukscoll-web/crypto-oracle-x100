"""Durable bounded scheduling identities, never cached investment evidence.

Two reserved assessment slots prevent new feed arrivals from starving retained
identities. Absent pools require fresh direct retrieval and normal inspection.
Retention is finite and losses are explicit; this is not market-wide coverage.
"""
import datetime as dt
import json
import pathlib
import urllib.parse

STATE = pathlib.Path('deferred_candidate_state.json')
MAX_ENTRIES = 1000
MAX_AGE_SECONDS = 7 * 86400
RESERVED_SLOTS = 2


def stamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def load(path=STATE):
    if not pathlib.Path(path).exists():
        return {'version': 1, 'pending': {}}
    state = json.loads(pathlib.Path(path).read_text())
    if (not isinstance(state, dict) or state.get('version') != 1 or
            not isinstance(state.get('pending'), dict) or len(state['pending']) > MAX_ENTRIES):
        raise ValueError('Invalid deferred candidate state')
    for key, row in state['pending'].items():
        if (not isinstance(row, dict) or not isinstance(row.get('network'), str) or
                not row['network'] or not isinstance(row.get('pool_address'), str) or
                not row['pool_address'] or key != row['network']+':'+row['pool_address'] or
                stamp(row.get('first_seen_at')) is None or
                (row.get('last_attempt_at') is not None and stamp(row['last_attempt_at']) is None)):
            raise ValueError('Invalid deferred candidate identity')
    return state


def save(state, path=STATE):
    path = pathlib.Path(path)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True)+'\n')
    temporary.replace(path)


def prepare(state, candidates, *, excluded=(), now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone required')
    pending = state['pending']
    excluded = set(excluded)
    expired = [key for key, row in pending.items()
               if now.timestamp() - stamp(row['first_seen_at']) > MAX_AGE_SECONDS]
    for key in expired:
        pending.pop(key)
    for key in excluded:
        pending.pop(key, None)
    report = {'expired': len(expired), 'capacity_deferred': 0, 'enqueued': 0,
              'attempted': 0, 'fresh_retained': 0, 'refresh_failed': 0,
              'no_longer_qualifying': 0, 'assessed_removed': 0,
              'maximum_entries': MAX_ENTRIES, 'retention_seconds': MAX_AGE_SECONDS,
              'market_evidence_reused_from_state': False, 'coverage_complete': False}
    for item in candidates:
        key = item['key']
        if key in excluded or key in pending:
            continue
        if len(pending) >= MAX_ENTRIES:
            report['capacity_deferred'] += 1
            continue
        # Persist only routing identities and scheduler times, never observed
        # prices/security findings or a caller-supplied authorization flag.
        pending[key] = {'network': item['network'], 'pool_address': item['address'],
                        'first_seen_at': now.isoformat(), 'last_attempt_at': None}
        report['enqueued'] += 1
    return report


def refresh(state, current, fetch, inspect, api, *, limit=RESERVED_SLOTS, now=None):
    if type(limit) is not int or not 1 <= limit <= RESERVED_SLOTS:
        raise ValueError('Invalid deferred refresh budget')
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone required')
    current = {item['key']: item for item in current}
    pending = state['pending']
    ordered = sorted(pending, key=lambda key: (
        stamp(pending[key].get('last_attempt_at')) or 0,
        stamp(pending[key]['first_seen_at']), key))[:limit]
    result = []
    counts = {'attempted': len(ordered), 'fresh_retained': 0,
              'refresh_failed': 0, 'no_longer_qualifying': 0}
    for key in ordered:
        row = pending[key]
        row['last_attempt_at'] = now.isoformat()
        item = current.get(key)
        try:
            if item is None:
                url = (api+'/networks/'+urllib.parse.quote(row['network'], safe='')+
                       '/pools/'+urllib.parse.quote(row['pool_address'], safe=''))
                payload = fetch(url)
                pool = payload.get('data')
                if not isinstance(pool, dict):
                    raise ValueError('Deferred pool response missing')
                item = inspect(pool, row['network'], 'tracked')
                if item is None:
                    pending.pop(key)
                    counts['no_longer_qualifying'] += 1
                    continue
            if item.get('key') != key:
                raise ValueError('Deferred pool identity mismatch')
            result.append(item)
            counts['fresh_retained'] += 1
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            counts['refresh_failed'] += 1
    return result, counts


def prioritize(reserved, other, limit):
    """Retain reserved fresh identities and deduplicate exact token hints."""
    result, identities = [], set()
    for item in list(reserved)+list(other):
        token = item.get('token_address') or item.get('discovery_token_hint') or item['key']
        identity = (item['network'], token if item['network'] == 'solana' else str(token).lower())
        if identity not in identities:
            identities.add(identity)
            result.append(item)
        if len(result) >= limit:
            break
    return result


def complete(state, selected):
    removed = 0
    for item in selected:
        if state['pending'].pop(item['key'], None) is not None:
            removed += 1
    return removed
