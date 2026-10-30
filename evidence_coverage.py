"""Coverage states describe checks, never investment authorization.

VERIFIED is reserved for a named narrow claim with retained provider evidence.
Legacy LIMITED/CORROBORATED observations remain UNKNOWN for complete gates.
"""
from verification import observation

STATES = {'UNSUPPORTED', 'NOT_CHECKED', 'UNKNOWN', 'FAILED', 'VERIFIED'}
GATES = ('contract_security', 'sellability', 'holders', 'liquidity',
         'supply_comparison', 'unlocks', 'execution', 'onchain')


def unavailable(source, url, exc):
    from provider_session import ProviderUnavailable
    code = getattr(exc, 'code', None)
    if code in (401, 402, 403):
        state, reason = 'NOT_CHECKED', 'Provider credentials/payment/permission unavailable'
    elif isinstance(exc, ProviderUnavailable):
        state, reason = 'NOT_CHECKED', str(exc)
    else:
        state, reason = 'UNKNOWN', 'Provider transport or response unavailable: ' + type(exc).__name__
    result = observation(source, url, None, state, reason)
    result['diagnostic'] = dict(error_type=type(exc).__name__, http_status=code)
    return result


def complete(item):
    report = item.setdefault('verification', {})
    for gate in GATES:
        if gate not in report:
            integration = report.get('integration') or {}
            report[gate] = observation('policy', '', None,
                integration.get('status', 'NOT_CHECKED'),
                integration.get('reason') or (item.get('hourly_evidence') or {}).get('reason', 'No collector result'))
    for entry in report.values():
        if isinstance(entry, dict):
            entry.setdefault('network', item.get('network'))
            entry.setdefault('token_address', item.get('token_address'))
            entry.setdefault('pool_address', item.get('address'))
    return report


def state(entry):
    status = entry.get('status', 'NOT_CHECKED')
    if status in STATES:
        return status
    if status in ('FAIL', 'HIGH CONCERN', 'CONFLICTING'):
        return 'FAILED'
    return 'UNKNOWN'


def summary(item):
    report = complete(item)
    return {gate: dict(status=state(report[gate]),
                       provider_status=report[gate].get('status'),
                       reason=report[gate].get('reason'),
                       source=report[gate].get('source'),
                       observed_at=report[gate].get('observed_at')) for gate in GATES}
