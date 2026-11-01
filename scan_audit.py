"""Stage-specific accounting. Counts name their populations; reasons may overlap."""
import datetime as dt
from collections import Counter


def increment(counts, key):
    counts[key] = counts.get(key, 0) + 1


def discovery_reason(pool, network, mode):
    # Shared ordered rules used by inspect and rejection accounting.
    import crypto_oracle_scanner as s
    attrs = pool.get('attributes') or {}
    created = attrs.get('pool_created_at')
    if not created:
        return 'missing_pool_creation_time'
    try:
        stamp = dt.datetime.fromisoformat(created.replace('Z', '+00:00'))
        stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=dt.timezone.utc)
        age = (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds() / 3600
    except (TypeError, ValueError, OverflowError):
        return 'invalid_pool_creation_time'
    if age < 0:
        return 'future_pool_creation_time'
    if mode == 'new_pools' and age > s.MAX_NEW_POOL_AGE_HOURS:
        return 'outside_new_pool_age'
    if mode == 'trending_pools' and age < s.MIN_TRENDING_POOL_AGE_HOURS:
        return 'outside_trending_pool_age'
    import math
    h1 = (attrs.get('transactions') or {}).get('h1') or {}
    measures = {'liquidity': attrs.get('reserve_in_usd'),
                'volume': (attrs.get('volume_usd') or {}).get('h24'),
                'buys': h1.get('buys'), 'sells': h1.get('sells')}
    for name, value in measures.items():
        try:
            if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError('Invalid measurement')
            if name in ('buys', 'sells') and float(value) != int(float(value)):
                raise ValueError('Fractional transaction count')
        except (TypeError, ValueError, OverflowError):
            return 'missing_or_invalid_' + name
    if s.number(attrs.get('reserve_in_usd')) < s.MIN_LIQUIDITY_USD:
        return 'liquidity_missing_or_below_minimum'
    if s.number((attrs.get('volume_usd') or {}).get('h24')) < s.MIN_24H_VOLUME_USD:
        return 'volume_missing_or_below_minimum'
    h1 = (attrs.get('transactions') or {}).get('h1') or {}
    if sum(int(max(0, s.number(h1.get(k)))) for k in ('buys', 'sells')) < s.MIN_1H_TRANSACTIONS:
        return 'transactions_missing_or_below_minimum'
    if not (attrs.get('address') or (pool.get('id') or '').removeprefix(network + '_')):
        return 'missing_pool_address'
    return None


def summarize(discovery, notifications, candidates, selected, rows):
    from evidence_coverage import GATES
    decisions = Counter()
    blockers = Counter()
    gates = (*GATES, 'tokenomics', 'source_controls', 'kyber')
    coverage = {gate: Counter() for gate in gates}
    for row in rows:
        assessment = row['assessment']
        decisions[assessment['decision']] += 1
        # Each blocker counts at most once per assessed candidate.
        blockers.update(set(assessment.get('blockers', [])))
        from evidence_coverage import state
        for gate in gates:
            entry = (row.get('verification') or {}).get(gate) or {}
            coverage[gate][state(entry)] += 1
    return dict(
        discovery_observations=dict(discovery),
        discovery_observation_count=sum(discovery.values()),
        qualified_unique_pools=len(candidates), assessed_candidates=len(rows),
        selected_candidates=len(selected),
        # A revisit can be absent from this run's discovery population.
        discovery_pools_not_selected=sum(c['key'] not in {i['key'] for i in selected} for c in candidates),
        assessed_decisions=dict(decisions),
        security_rejections=sum(row.get('risk_category') == 'AVOID / HIGH CONCERN' for row in rows),
        assessed_blocker_counts=dict(blockers), blocker_counts_overlap=True,
        evidence_states={gate: dict(values) for gate, values in coverage.items()},
        notification_outcomes=dict(notifications),
        notification_population='Assessed candidates, including watchlist revisits; one terminal outcome each',
        discovery_scope='Returned pool observations only; rejected duplicates are observations, not unique tokens')
