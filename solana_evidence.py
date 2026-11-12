"""Read-only finalized Solana SPL mint evidence; no routes or signing.

RPC account lookup is exact and case-sensitive. Largest token accounts are not
beneficial owners. Supply/authority observations do not prove circulating supply,
vesting, pool controls, sellability or independent security.

Token-2022 mints are read with an explicit extension policy. Only extensions
reviewed as benign are accepted; known-dangerous ones fail the contract-security
check; any extension or shape not listed is UNSUPPORTED (fail closed).
"""
from asset_identity import canonical
from verification import observation
from evidence_coverage import unavailable

URL = 'https://api.mainnet-beta.solana.com'
TOKEN_PROGRAM = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
# RPC returns the full genesis hash; the CAIP chain identifier uses its prefix.
TOKEN_2022_PROGRAM = 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'
# Metadata and grouping extensions do not change transfer behaviour.
BENIGN_EXTENSIONS = frozenset({'metadataPointer', 'tokenMetadata', 'groupPointer', 'tokenGroup',
                               'groupMemberPointer', 'tokenGroupMember'})
# Each of these lets an issuer block, tax, seize or redirect holders' tokens.
DANGEROUS_EXTENSIONS = {
    'permanentDelegate': 'permanent delegate can move or burn any holder balance',
    'transferHook': 'transfer hook runs arbitrary issuer code on every transfer',
    'pausableConfig': 'issuer can pause all transfers',
    'nonTransferable': 'tokens cannot be transferred or sold',
    'confidentialTransferMint': 'confidential transfers hide balances and hinder verification',
    'confidentialTransferFeeConfig': 'confidential transfer fees hinder verification',
}
MAX_TRANSFER_FEE_BPS = 100
GENESIS = '5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d'


def integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('Invalid integer')
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError('Invalid decimal integer')
    result = int(value)
    if result < 0:
        raise ValueError('Negative integer')
    return result


def extension_policy(extensions):
    """Return (unknown, failures, notes) for a Token-2022 extension list. Fails closed."""
    unknown, failures, notes = [], [], []
    if not isinstance(extensions, list):
        return ['extensions-not-a-list'], failures, notes
    for entry in extensions:
        name = entry.get('extension') if isinstance(entry, dict) else None
        state = entry.get('state') if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            unknown.append('unnamed')
        elif name in BENIGN_EXTENSIONS:
            continue
        elif name in DANGEROUS_EXTENSIONS:
            failures.append(name + ': ' + DANGEROUS_EXTENSIONS[name])
        elif name == 'defaultAccountState':
            if not isinstance(state, dict) or state.get('accountState') != 'initialized':
                failures.append('defaultAccountState: new holder accounts start frozen or unknown')
        elif name == 'transferFeeConfig':
            try:
                fees = [integer(state[key]['transferFeeBasisPoints'])
                        for key in ('olderTransferFee', 'newerTransferFee')]
                authority = state['transferFeeConfigAuthority']
            except (KeyError, TypeError, ValueError):
                unknown.append(name)
                continue
            if max(fees) > MAX_TRANSFER_FEE_BPS:
                failures.append('transferFeeConfig: transfer fee %s bps exceeds %s' % (max(fees), MAX_TRANSFER_FEE_BPS))
            elif authority is not None:
                failures.append('transferFeeConfig: fee authority active; fee can be raised later')
            else:
                notes.append('transfer fee %s bps, authority revoked' % max(fees))
        else:
            unknown.append(name)
    return unknown, failures, notes


def collect(item, request):
    report = {}
    calls = []
    def rpc(method, params):
        payload = dict(jsonrpc='2.0', id=len(calls) + 1, method=method, params=params)
        raw = request(URL, payload)
        calls.append(dict(request=payload, response=raw))
        if not isinstance(raw, dict) or raw.get('id') != payload['id'] or raw.get('error') or 'result' not in raw:
            raise ValueError('Invalid RPC response')
        return raw['result']
    try:
        mint = canonical('solana', item['token_address'])
        if rpc('getGenesisHash', []) != GENESIS:
            raise ValueError('Wrong Solana cluster')
        result = rpc('getAccountInfo', [mint, dict(encoding='jsonParsed', commitment='finalized')])
        slot = integer(result['context']['slot'])
        account = result['value']
        if not isinstance(account, dict) or account.get('executable') is not False:
            raise ValueError('Missing or executable mint account')
        owner = account.get('owner')
        unknown, ext_failures, ext_notes = [], [], []
        if owner == TOKEN_2022_PROGRAM and isinstance(account.get('data'), dict):
            unknown, ext_failures, ext_notes = extension_policy(
                (((account['data'].get('parsed') or {}).get('info') or {}).get('extensions') or []))
        if owner not in (TOKEN_PROGRAM, TOKEN_2022_PROGRAM):
            report['onchain'] = observation('Solana RPC', URL, calls, 'UNSUPPORTED',
                'Mint owner is not legacy SPL Token; Token-2022/other programs need reviewed extension parsing')
        elif unknown:
            report['onchain'] = observation('Solana RPC', URL, calls, 'UNSUPPORTED',
                'Token-2022 mint has extension(s) without a reviewed policy: ' + ', '.join(sorted(set(unknown))[:5]))
        else:
            parsed = account['data']['parsed']
            expected_program = 'spl-token' if owner == TOKEN_PROGRAM else 'spl-token-2022'
            if account['data'].get('program') != expected_program or parsed.get('type') != 'mint':
                raise ValueError('Not an SPL mint')
            info = parsed['info']
            supply, decimals = integer(info['supply']), integer(info['decimals'])
            if info.get('isInitialized') is not True or decimals > 255:
                raise ValueError('Invalid mint data')
            for field in ('mintAuthority', 'freezeAuthority'):
                if field not in info:
                    raise ValueError('Missing mint authority field')
                if info[field] is not None:
                    canonical('solana', info[field])
            report['onchain'] = observation('Solana RPC', URL, list(calls), 'LIMITED',
                'Finalized exact legacy SPL mint observed; single RPC source, not an independent audit')
            report['onchain']['checks'] = {
                ('legacy_spl_mint_identity' if owner == TOKEN_PROGRAM else 'token2022_mint_identity'):
                    dict(status='VERIFIED', slot=slot, mint=mint),
                'mint_authority_revoked': dict(status='VERIFIED' if info['mintAuthority'] is None else 'FAILED', value=info['mintAuthority'], slot=slot),
                'freeze_authority_revoked': dict(status='VERIFIED' if info['freezeAuthority'] is None else 'FAILED', value=info['freezeAuthority'], slot=slot),
            }
            if owner == TOKEN_2022_PROGRAM:
                report['onchain']['checks']['token2022_extensions'] = dict(
                    status='FAILED' if ext_failures else 'VERIFIED', slot=slot,
                    failures=ext_failures, notes=ext_notes)
            report['onchain']['metrics'] = dict(total_supply_base_units=str(supply), decimals=decimals, slot=slot)
            adverse = info['mintAuthority'] is not None or info['freezeAuthority'] is not None or bool(ext_failures)
            report['contract_security'] = observation('Solana RPC', URL, list(calls),
                'FAIL' if adverse else 'UNKNOWN',
                ('Violates conservative policy: ' + '; '.join(
                    (['active mint/freeze authority'] if info['mintAuthority'] is not None or info['freezeAuthority'] is not None else [])
                    + ext_failures)) if adverse else
                'Mint/freeze authorities revoked' + (' and only reviewed Token-2022 extensions' if owner == TOKEN_2022_PROGRAM else '')
                + '; independent security and pool program review remain incomplete')
            report['supply_comparison'] = observation('Solana RPC', URL, list(calls), 'UNKNOWN',
                'Finalized gross mint supply observed; independent reconciliation, circulating supply and unlocks absent')
            report['supply_comparison']['metrics'] = dict(total_supply_base_units=str(supply), decimals=decimals, slot=slot)
            try:
                largest = rpc('getTokenLargestAccounts', [mint, dict(commitment='finalized')])
                holder_slot = integer(largest['context']['slot'])
                rows = largest['value']
                if not isinstance(rows, list) or holder_slot < slot or len(rows) > 20:
                    raise ValueError('Invalid largest account snapshot')
                addresses = [canonical('solana', row['address']) for row in rows]
                amounts = [integer(row['amount']) for row in rows]
                if len(set(addresses)) != len(addresses) or any(integer(row['decimals']) != decimals for row in rows):
                    raise ValueError('Invalid token accounts')
                report['holders'] = observation('Solana RPC', URL, list(calls), 'UNKNOWN',
                    'Largest token accounts observed; slots may differ, wallet aggregation, LP/CEX exclusions and beneficial ownership unverified')
                report['holders']['metrics'] = dict(listed_base_units=str(sum(amounts)), account_count=len(rows), slot=holder_slot)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                report['holders'] = unavailable('Solana RPC', URL, exc)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        report['onchain'] = unavailable('Solana RPC', URL, exc)
        report['onchain']['raw'] = calls
    for name in ('contract_security', 'holders', 'supply_comparison'):
        report.setdefault(name, observation('Solana RPC', URL, None,
            report['onchain']['status'] if report['onchain']['status'] in ('UNSUPPORTED', 'NOT_CHECKED') else 'UNKNOWN',
            'Mint evidence unavailable: ' + report['onchain']['reason']))
    for name, reason in (
        ('sellability', 'No reviewed Solana exact-pool buy/sell simulator configured'),
        ('liquidity', 'No reviewed Solana pool withdrawal/control adapter configured'),
        ('execution', 'No reviewed Solana funded sequential execution adapter configured')):
        report[name] = observation('policy', '', None, 'UNSUPPORTED', reason)
    return report
