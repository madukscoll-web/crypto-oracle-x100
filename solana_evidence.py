"""Read-only finalized Solana SPL mint evidence; no routes or signing.

RPC account lookup is exact and case-sensitive. Largest token accounts are not
beneficial owners. Supply/authority observations do not prove circulating supply,
vesting, pool controls, sellability or independent security. Token-2022 extensions
require a separate reviewed parser and are explicitly unsupported here.
"""
from asset_identity import canonical
from verification import observation
from evidence_coverage import unavailable

URL = 'https://api.mainnet-beta.solana.com'
TOKEN_PROGRAM = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
# RPC returns the full genesis hash; the CAIP chain identifier uses its prefix.
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
        if account.get('owner') != TOKEN_PROGRAM:
            report['onchain'] = observation('Solana RPC', URL, calls, 'UNSUPPORTED',
                'Mint owner is not legacy SPL Token; Token-2022/other programs need reviewed extension parsing')
        else:
            parsed = account['data']['parsed']
            if account['data'].get('program') != 'spl-token' or parsed.get('type') != 'mint':
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
                'legacy_spl_mint_identity': dict(status='VERIFIED', slot=slot, mint=mint),
                'mint_authority_revoked': dict(status='VERIFIED' if info['mintAuthority'] is None else 'FAILED', value=info['mintAuthority'], slot=slot),
                'freeze_authority_revoked': dict(status='VERIFIED' if info['freezeAuthority'] is None else 'FAILED', value=info['freezeAuthority'], slot=slot),
            }
            report['onchain']['metrics'] = dict(total_supply_base_units=str(supply), decimals=decimals, slot=slot)
            report['contract_security'] = observation('Solana RPC', URL, list(calls),
                'FAIL' if info['mintAuthority'] is not None or info['freezeAuthority'] is not None else 'UNKNOWN',
                'Active mint/freeze authority violates conservative policy' if info['mintAuthority'] is not None or info['freezeAuthority'] is not None else
                'Legacy mint/freeze authorities revoked; independent security and pool program review remain incomplete')
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
