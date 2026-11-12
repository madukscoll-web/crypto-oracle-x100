"""Read-only on-chain facts for an ATL research asset's exact contracts.

Supplies independent, point-in-time facts (contract exists, decimals, total supply,
mint/freeze authority, owner/proxy) from public RPC. These facts can reduce what the
alert lists as missing and can WITHHOLD an alert; they never grant eligibility, BUY
admission or order permission, and never certify a lifetime all-time low.
"""
import datetime as dt
import re
from decimal import Decimal, InvalidOperation

EVM_NETWORKS = ('eth', 'base', 'bsc')
MAX_CONTRACTS = 2
MAX_AGE_SECONDS = 7200
SECURITY = ('FAIL', 'UNKNOWN', 'LIMITED')
EVM = re.compile('0x[0-9a-fA-F]{40}')
SOLANA = re.compile('[1-9A-HJ-NP-Za-km-z]{32,44}')


def _stamp(value):
    parsed = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed.timestamp()


def _supply(raw, decimals):
    value = Decimal(int(raw)) / (Decimal(10) ** int(decimals))
    return format(value.normalize(), 'f') if value > 0 else None


def _solana(contract, request, now):
    import solana_evidence
    report = solana_evidence.collect(dict(network='solana', token_address=contract, key='solana:' + contract), request)
    on, sec = report.get('onchain') or {}, report.get('contract_security') or {}
    checks = on.get('checks') or {}
    identity = any(name.endswith('mint_identity') and v.get('status') == 'VERIFIED' for name, v in checks.items())
    entry = dict(network='solana', contract=contract, source='solana_rpc', observed_at=_iso(now),
                 identity='VERIFIED' if identity else 'UNVERIFIED', total_supply=None, decimals=None,
                 security_status=sec.get('status') if sec.get('status') in SECURITY else 'UNKNOWN',
                 security_reason=str(sec.get('reason') or on.get('reason') or '')[:240], facts=[])
    if identity:
        metrics = on.get('metrics') or {}
        entry['decimals'] = int(metrics['decimals'])
        entry['total_supply'] = _supply(metrics['total_supply_base_units'], metrics['decimals'])
        mint = checks.get('mint_authority_revoked', {}).get('status')
        freeze = checks.get('freeze_authority_revoked', {}).get('status')
        entry['facts'] = ['Solana mint confirmed on-chain at a finalized slot (%s decimals)' % entry['decimals'],
                          'Mint authority ' + ('revoked' if mint == 'VERIFIED' else 'ACTIVE (supply can be created)'),
                          'Freeze authority ' + ('revoked' if freeze == 'VERIFIED' else 'ACTIVE (accounts can be frozen)')]
        if entry['total_supply']:
            entry['facts'].append('On-chain total supply: ' + entry['total_supply'])
    return entry


def _iso(now):
    return dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat()


def _evm(network, contract, rpc_factory, now):
    import onchain
    rpc = rpc_factory(network)
    rpc.snapshot()
    code = rpc.call('eth_getCode', [onchain.address(contract), rpc.block['number']])
    identity = isinstance(code, str) and re.fullmatch('0x[0-9a-fA-F]+', code) is not None and int(code, 16) != 0
    entry = dict(network=network, contract=contract.lower(), source='evm_rpc', observed_at=_iso(now),
                 identity='VERIFIED' if identity else 'UNVERIFIED', total_supply=None, decimals=None,
                 security_status='UNKNOWN', security_reason='Ownership or upgradeability could not be established on-chain',
                 facts=[])
    if not identity:
        return entry
    entry['facts'] = ['Contract code exists on-chain at the pinned block']
    try:
        decimals = onchain.uint(rpc.read(contract, '313ce567'))
        total = onchain.uint(rpc.read(contract, '18160ddd'))
        if decimals > 36:
            raise ValueError('Unreasonable decimals')
        entry['decimals'], entry['total_supply'] = decimals, _supply(total, decimals)
        if entry['total_supply']:
            entry['facts'].append('On-chain total supply: ' + entry['total_supply'])
    except (ValueError, TypeError, OSError):
        pass  # supply stays unknown; never guessed
    control = onchain.owner_control(rpc, contract)
    entry['security_status'] = control['status'] if control['status'] in SECURITY else 'UNKNOWN'
    entry['security_reason'] = str(control.get('reason', ''))[:240]
    kind = (control.get('metrics') or {}).get('owner_kind')
    if kind == 'RENOUNCED':
        entry['facts'].append('owner() is renounced (other admin roles not ruled out)')
    return entry


def collect(contracts, *, now, solana_request=None, rpc_factory=None):
    """One entry per supported exact contract (bounded). Failures yield UNVERIFIED, never raise."""
    entries = []
    for item in list(contracts)[:MAX_CONTRACTS]:
        network, contract = item.get('network'), item.get('contract')
        try:
            if network == 'solana' and solana_request is not None and isinstance(contract, str) and SOLANA.fullmatch(contract):
                entries.append(_solana(contract, solana_request, now))
            elif network in EVM_NETWORKS and rpc_factory is not None and isinstance(contract, str) and EVM.fullmatch(contract):
                entries.append(_evm(network, contract, rpc_factory, now))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError, InvalidOperation):
            entries.append(dict(network=network, contract=contract, source='unavailable', observed_at=_iso(now),
                                identity='UNVERIFIED', total_supply=None, decimals=None, security_status='UNKNOWN',
                                security_reason='On-chain read failed', facts=[]))
    return entries


def validate(entries, asset, now):
    """Re-check stored evidence at replay. Returns entries or raises ValueError."""
    if not isinstance(entries, list) or not entries or len(entries) > MAX_CONTRACTS:
        raise ValueError('On-chain evidence malformed')
    wanted = {(c['network'], c['contract']) for c in asset['contracts']}
    for entry in entries:
        if not isinstance(entry, dict) or (entry.get('network'), entry.get('contract')) not in wanted:
            raise ValueError('On-chain evidence identity mismatch')
        if entry.get('identity') not in ('VERIFIED', 'UNVERIFIED') or entry.get('security_status') not in SECURITY:
            raise ValueError('On-chain evidence status invalid')
        observed = _stamp(entry.get('observed_at'))
        if observed > now or now - observed > MAX_AGE_SECONDS:
            raise ValueError('Stale on-chain evidence')
        supply = entry.get('total_supply')
        if supply is not None:
            try:
                if not Decimal(supply).is_finite() or Decimal(supply) <= 0:
                    raise ValueError('Invalid on-chain supply')
            except InvalidOperation as exc:
                raise ValueError('Invalid on-chain supply') from exc
        facts = entry.get('facts')
        if not isinstance(facts, list) or len(facts) > 6 or not all(isinstance(f, str) and len(f) <= 160 for f in facts):
            raise ValueError('On-chain facts malformed')
        if entry['identity'] != 'VERIFIED' and facts:
            raise ValueError('Unverified identity cannot carry facts')
    return entries
