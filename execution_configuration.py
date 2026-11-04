"""Non-secret quote-configuration diagnostics. Never signs or submits an order."""
import re

ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}')


def status(env):
    missing = []
    if not str(env.get('ZEROX_API_KEY', '')).strip():
        missing.append('ZEROX_API_KEY')
    for name in ('ORACLE_TAKER_ADDRESS', 'ORACLE_FUNDING_TOKEN'):
        value = env.get(name, '')
        if not isinstance(value, str) or not ADDRESS.fullmatch(value) or int(value[2:], 16) == 0:
            missing.append(name)
    size = env.get('ORACLE_ORDER_BASE_UNITS', '')
    if not isinstance(size, str) or not re.fullmatch(r'[1-9][0-9]{0,77}', size):
        missing.append('ORACLE_ORDER_BASE_UNITS')
    return {'status': 'MISSING_OR_INVALID_INPUTS' if missing else 'INPUTS_PRESENT_UNVERIFIED',
            'missing_or_invalid_names': missing, 'values_included': False,
            'buy_authorized': False, 'orders_allowed': False,
            'scope': 'Configuration presence only; network, funding, allowance, route and execution remain unverified'}
