"""Exact-token disclosure analysis. A disclosure is not verified unlock coverage.

Registry entries need explicit contract identity and source URLs. No symbol/name
matching and no inference of zero unlocks from a missing calendar are permitted.
Amounts are integer base units; vesting contracts and mint authority must still
be independently checked before a disclosure could satisfy a mandatory gate.
"""
import datetime as dt
import re
from urllib.parse import urlsplit
from verification import observation
from onchain import address


def units(value):
    if isinstance(value, bool) or not re.fullmatch(r'0|[1-9][0-9]*', str(value)):
        raise ValueError('Expected nonnegative integer base units')
    return int(value)


def timestamp(value):
    parsed = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return int(parsed.timestamp())


def vested(schedule, when):
    amount = units(schedule['amount_base_units'])
    start, end = timestamp(schedule['start']), timestamp(schedule['end'])
    if end < start or amount <= 0:
        raise ValueError('Invalid vesting schedule')
    if schedule['kind'] == 'cliff':
        if start != end:
            raise ValueError('Cliff must have a single timestamp')
        return amount if when >= start else 0
    if schedule['kind'] != 'linear' or start == end:
        raise ValueError('Unsupported vesting type')
    return amount * max(0, min(end - start, when - start)) // (end - start)


def analyze(disclosure, network, token, now=None):
    now = int(now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp())
    if disclosure.get('network') != network or address(disclosure.get('token_address', '')) != address(token):
        raise ValueError('Disclosure identity mismatch')
    source = urlsplit(disclosure['source_url'])
    if source.scheme != 'https' or not source.hostname or source.username or source.password:
        raise ValueError('HTTPS disclosure source required')
    age = now - timestamp(disclosure['observed_at'])
    if not 0 <= age <= 86400:
        raise ValueError('Stale or future disclosure')
    circulating = units(disclosure['circulating_supply_base_units'])
    total = units(disclosure['total_supply_base_units'])
    if not 0 < circulating <= total:
        raise ValueError('Invalid circulating/total supply')
    schedules = disclosure['schedules']
    if not isinstance(schedules, list) or not schedules:
        raise ValueError('Missing schedules cannot mean no unlocks')
    identifiers = [x['id'] for x in schedules]
    if any(not isinstance(x, str) or not x for x in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('Missing or duplicate allocation IDs')
    allocation = sum(units(x['amount_base_units']) for x in schedules)
    if allocation > total:
        raise ValueError('Disclosed vesting exceeds total supply')
    baseline = sum(vested(x, now) for x in schedules)
    remaining = allocation - baseline
    if remaining > total - circulating:
        raise ValueError('Disclosed unvested supply conflicts with circulation')
    horizons = {}
    for days in (7, 30, 90, 365):
        unlock = sum(vested(x, now + days * 86400) for x in schedules) - baseline
        horizons[str(days)] = dict(disclosed_unlock_base_units=str(unlock),
                                  disclosed_dilution_fraction=unlock / circulating)
    return dict(circulating_supply_base_units=str(circulating), total_supply_base_units=str(total),
                disclosed_remaining_vesting_base_units=str(remaining), horizons_days=horizons,
                coverage_verified=False, mint_authority_verified=False,
                undisclosed_future_dilution_upper_bound=None,
                limitation='Issuer/provider disclosure only; on-chain vesting, circulation, related allocations and mint authority unverified')


def collect(item, registry):
    key = item.get('network', '') + ':' + item.get('token_address', '').lower()
    disclosure = registry.get('tokens', {}).get(key)
    if disclosure is None:
        return observation('unlock_registry', '', None, 'UNKNOWN',
                           'No exact-contract sourced unlock disclosure; missing data does not mean zero dilution')
    try:
        metrics = analyze(disclosure, item['network'], item['token_address'])
        result = observation('unlock_registry', disclosure['source_url'], disclosure, 'LIMITED', metrics['limitation'])
        result['metrics'] = metrics
        return result
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return observation('unlock_registry', '', None, 'UNKNOWN', 'Invalid, stale or identity-conflicting unlock disclosure')
