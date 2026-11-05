"""Read-only EVM evidence adapters. Unknown or conflicting evidence never passes.

No signing, transaction broadcasting, wallet credentials or trading endpoints.
Raw responses remain attached to observations for independent review.
"""
import datetime as dt
import math
import re
import urllib.parse

CHAINS = {'eth': 1, 'bsc': 56, 'base': 8453, 'arbitrum': 42161,
          'polygon_pos': 137, 'avax': 43114, 'optimism': 10}
SIMULATOR_CHAINS = {'eth', 'bsc', 'base'}
DOCS = {
    'goplus': 'https://docs.gopluslabs.io/reference/token-security-api',
    'honeypot': 'https://docs.honeypot.is/ishoneypot',
    'ohlcv': 'https://apiguide.geckoterminal.com/',
    'quote': 'https://0x.org/docs/api#tag/Swap',
}


def finite(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a measurement')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Nonfinite measurement')
    return value


def observation(source, url, raw, status, reason):
    return dict(source=source, url=url, observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                status=status, reason=reason, raw=raw)


def binary_flag(value):
    """Normalize explicit provider booleans/0/1 without truthiness coercion."""
    if value is True:
        return '1'
    if value is False:
        return '0'
    if type(value) is int and value in (0, 1):
        return str(value)
    return value if isinstance(value, str) and value in ('0', '1') else None


def security(info):
    required = {'is_honeypot': '0', 'cannot_sell_all': '0', 'owner_change_balance': '0',
                'hidden_owner': '0', 'is_blacklisted': '0', 'is_open_source': '1',
                'is_mintable': '0', 'trading_cooldown': '0', 'is_proxy': '0',
                'transfer_pausable': '0', 'slippage_modifiable': '0',
                'personal_slippage_modifiable': '0', 'selfdestruct': '0'}
    if any(binary_flag(info.get(k)) in ('0', '1') and binary_flag(info[k]) != v for k, v in required.items()):
        return 'FAIL', 'Contract capability or sellability concern reported'
    if any(binary_flag(info.get(k)) != v for k, v in required.items()):
        return 'UNKNOWN', 'Required contract fields absent; no audit inferred'
    return 'LIMITED', 'Provider screening clear; independent source/authority review required'


def holders(info):
    rows = info.get('holders')
    if not isinstance(rows, list) or not rows:
        return 'UNKNOWN', 'No holder list'
    try:
        values = [finite(x['percent']) for x in rows]
        if any(x < 0 or x > 1 for x in values) or sum(values) > 1.001:
            raise ValueError('Invalid holder shares')
    except (KeyError, TypeError, ValueError):
        return 'UNKNOWN', 'Invalid holder shares'
    # Even labelled LP wallets do not establish beneficial ownership or coverage.
    if max(values) > .20:
        return 'UNKNOWN', f'Largest listed wallet {max(values):.1%}; classify LP/custody before approval'
    return 'UNKNOWN', f'Listed share {sum(values):.1%}; coverage, LP exclusions and related-wallet ownership unverified'


def liquidity(info):
    pools = info.get('dex')
    if not isinstance(pools, list) or not pools:
        return 'UNKNOWN', 'No liquidity records'
    return 'UNKNOWN', 'Pool liquidity reported; LP lock contract, expiry, ownership and exit depth require verification'


def tokenomics(info):
    try:
        supply = finite(info['total_supply'])
        if supply <= 0:
            raise ValueError('Invalid supply')
    except (KeyError, ValueError, TypeError):
        return 'UNKNOWN', 'No valid total supply'
    if binary_flag(info.get('is_mintable')) == '1':
        return 'FAIL', 'Mint authority creates dilution exposure'
    return 'UNKNOWN', f'Total supply {supply:g}; circulating supply, vesting and future unlocks unverified'


def honeypot(raw, token, chain=None, pair=None):
    # Verify returned identity, successful simulation, explicit result and taxes.
    try:
        if raw['token']['address'].lower() != token.lower():
            return 'UNKNOWN', 'Simulation token identity mismatch'
        if chain is not None and str(raw.get('chain', {}).get('id')) != str(chain):
            return 'UNKNOWN', 'Independent simulation chain identity mismatch'
        returned_pair = raw.get('pairAddress') or raw.get('pair', {}).get('pair', {}).get('address')
        if pair is not None and str(returned_pair).lower() != pair.lower():
            return 'UNKNOWN', 'Independent simulation used a different or unverified pool'
        if raw['honeypotResult']['isHoneypot'] is True:
            reason = str(raw['honeypotResult'].get('honeypotReason', '')).lower()
            if 'target contract does not contain code' in reason or 'router not found' in reason:
                return 'CONFLICTING', 'Provider honeypot verdict conflicts with simulator target/router failure; sellability unresolved'
            return 'FAIL', 'Independent provider reports honeypot'
        if raw['simulationSuccess'] is not True or raw['honeypotResult']['isHoneypot'] is not False:
            return 'UNKNOWN', 'Simulation unsuccessful or incomplete'
        sim = raw['simulationResult']
        taxes = [finite(sim[k]) for k in ('buyTax', 'sellTax', 'transferTax')]
        if any(x < 0 or x > 5 for x in taxes):
            return 'FAIL', 'Tax exceeds 5% policy limit or is invalid'
        if raw.get('flags') or raw.get('summary', {}).get('flags'):
            return 'UNKNOWN', 'Provider flags require review'
        return 'LIMITED', 'Independent buy/sell simulation succeeded; size-specific quotes still required'
    except (KeyError, TypeError, ValueError, AttributeError):
        return 'UNKNOWN', 'Incomplete independent simulation response'


def historical_entry(raw, now=None):
    """Observed closed candles, never a prediction or aggregate-price target."""
    now = now or dt.datetime.now(dt.timezone.utc).timestamp()
    try:
        rows = raw['data']['attributes']['ohlcv_list']
        bars = sorted([[finite(v) for v in row] for row in rows])
        bars = [x for x in bars if len(x) == 6 and x[0] + 300 <= now]
        if len(bars) < 21 or now - bars[-1][0] > 900:
            return {'status': 'UNKNOWN', 'reason': 'Insufficient fresh closed five-minute candles'}
        bars = bars[-21:]
        if any(b[0] - a[0] != 300 for a, b in zip(bars, bars[1:])):
            raise ValueError('Candle gaps or duplicates')
        if any(not (0 < x[3] <= min(x[1], x[4]) <= max(x[1], x[4]) <= x[2]) or x[5] <= 0 for x in bars):
            raise ValueError('Invalid candle geometry/volume')
        previous, last = bars[:-1], bars[-1]
        resistance = max(x[2] for x in previous)
        support = min(x[3] for x in previous[-6:])
        volume = sum(x[5] for x in previous) / len(previous)
        if not (resistance < last[4] <= resistance * 1.03 and last[5] >= volume * 1.5):
            return {'status': 'WAIT', 'reason': 'No confirmed volume-supported breakout'}
        return {'status': 'LIMITED', 'reason': 'Closed-candle breakout; execution and security gates still mandatory',
                'entry_reference': last[4], 'invalidation': support, 'candle_at': last[0]}
    except (KeyError, TypeError, ValueError, IndexError):
        return {'status': 'UNKNOWN', 'reason': 'Malformed historical candle evidence'}


def risk_plan(equity, entry, invalidation, fees_fraction, slippage_fraction, liquidity_usd):
    """USD-only sizing from explicit inputs. Stops cannot guarantee maximum loss."""
    equity, entry, invalidation, fees, slip, depth = map(finite,
        (equity, entry, invalidation, fees_fraction, slippage_fraction, liquidity_usd))
    if not (equity > 0 and 0 < invalidation < entry and 0 <= fees <= .1 and 0 <= slip <= .02 and depth > 0):
        raise ValueError('Invalid risk inputs')
    loss_fraction = (entry - invalidation) / entry + fees + 2 * slip
    allocation = min(equity * .10, equity * .01 / loss_fraction, depth * .001)
    return {'allocation_usd': allocation, 'units': allocation / entry,
            'planned_loss_usd': allocation * loss_fraction, 'total_loss_exposure_usd': allocation,
            'invalidation': invalidation, 'fees_fraction': fees, 'slippage_fraction': slip}


def collect(item, fetch, rpc_request=None, include_entry=True):
    from evidence_coverage import unavailable
    if item.get('network') == 'solana':
        import solana_evidence
        from provider_session import CURRENT
        request = rpc_request or (CURRENT.get().json if CURRENT.get() is not None else None)
        if request is None:
            return {name: observation('policy', '', None, 'NOT_CHECKED', 'Solana RPC transport not configured')
                    for name in ('integration', 'onchain', 'contract_security', 'holders', 'supply_comparison', 'liquidity', 'sellability', 'execution')}
        return solana_evidence.collect(item, request)
    report = {}
    network, token = item.get('network'), item.get('token_address', '')
    if not re.fullmatch(r'0x[0-9a-fA-F]{40}', token):
        return {'integration': observation('policy', '', None, 'UNKNOWN', 'Invalid EVM token identity')}
    chain = CHAINS.get(network)
    if not chain:
        return {'integration': observation('policy', '', None, 'UNSUPPORTED', 'No reviewed verification adapter on network')}
    endpoints = {
        'goplus': f'https://api.gopluslabs.io/api/v1/token_security/{chain}?contract_addresses={token}',
        'honeypot': 'https://api.honeypot.is/v2/IsHoneypot?' + urllib.parse.urlencode({'address': token, 'chainID': chain, 'pair': item['address']}),
        'ohlcv': 'https://api.geckoterminal.com/api/v2/networks/' + urllib.parse.quote(network, safe='') + '/pools/' + urllib.parse.quote(item['address'], safe='') + '/ohlcv/minute?aggregate=5&limit=30&currency=usd&token=base',
    }
    for source, url in endpoints.items():
        if source == "ohlcv" and not include_entry:
            continue
        try:
            if source == 'honeypot' and network not in SIMULATOR_CHAINS:
                report['sellability'] = observation(source, url, None, 'UNSUPPORTED', 'Independent simulator does not support this network')
                continue
            if source == 'honeypot' and not re.fullmatch(r'0x[0-9a-fA-F]{40}', item['address']):
                report['sellability'] = observation(source, url, None, 'UNSUPPORTED', 'Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported')
                continue
            raw = fetch(url)
            if not isinstance(raw, dict):
                raise ValueError('Expected object')
            if source == 'goplus':
                info = (raw.get('result') or {}).get(token.lower())
                if raw.get('code') != 1 or not isinstance(info, dict):
                    raise ValueError('Missing exact token security result')
                for key, analyze in (('contract_security', security), ('holders', holders), ('liquidity', liquidity), ('tokenomics', tokenomics)):
                    status, reason = analyze(info)
                    report[key] = observation(source, url, raw, status, reason)
            elif source == 'honeypot':
                report['sellability'] = observation(source, url, raw, *honeypot(raw, token, chain, item['address']))
            else:
                analysis = historical_entry(raw)
                report['entry'] = observation(source, url, raw, analysis['status'], analysis['reason'])
                report['entry']['analysis'] = analysis
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            report[source] = unavailable(source, url, exc)
            names = {'goplus': ('contract_security', 'holders', 'liquidity', 'tokenomics'), 'honeypot': ('sellability',), 'ohlcv': ('entry',)}[source]
            for name in names:
                report[name] = dict(report[source])
    report['execution'] = observation('0x', DOCS['quote'], None, 'NOT_CHECKED',
        'Executable two-way size-specific quote, taker address, API credential, gas and allowance simulation not configured')
    return report


