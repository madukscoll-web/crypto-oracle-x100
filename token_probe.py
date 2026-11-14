"""Read-only probe of one EVM token contract across the chains the bot supports.

Public data only: public RPC reads (code, name, symbol, decimals, supply, owner,
proxy slots), GoPlus token security and DexScreener pairs. No keys, no orders, no
state. Output is printed as `PROBE <chain> <json>` lines for a human to read; a
missing or unreadable answer is reported as UNKNOWN, never as clear.

Usage: python token_probe.py 0xTOKEN
"""
import json
import re
import sys
import urllib.request

import onchain

CHAINS = {'eth': 1, 'base': 8453, 'bsc': 56}
HOSTS = ('api.gopluslabs.io', 'api.dexscreener.com')
GOPLUS_FIELDS = ('token_name', 'token_symbol', 'total_supply', 'holder_count', 'is_honeypot', 'honeypot_with_same_creator',
                 'buy_tax', 'sell_tax', 'transfer_tax', 'cannot_buy', 'cannot_sell_all', 'is_open_source', 'is_proxy',
                 'is_mintable', 'can_take_back_ownership', 'owner_change_balance', 'hidden_owner', 'selfdestruct',
                 'external_call', 'is_blacklisted', 'is_whitelisted', 'transfer_pausable', 'trading_cooldown',
                 'slippage_modifiable', 'personal_slippage_modifiable', 'is_anti_whale', 'owner_address',
                 'owner_percent', 'creator_address', 'creator_percent', 'lp_holder_count', 'lp_total_supply',
                 'is_in_dex', 'trust_list', 'other_potential_risks', 'note')


def get_json(url):
    from urllib.parse import urlparse
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in HOSTS:
        raise ValueError('Host not allowed')
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'crypto-oracle-research/1'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read(2_000_000))


def abi_string(word):
    if not isinstance(word, str) or not word.startswith('0x'):
        return None
    raw = bytes.fromhex(word[2:])
    if len(raw) == 32:
        return raw.rstrip(b'\x00').decode('utf-8', 'replace') or None
    if len(raw) >= 64:
        length = int.from_bytes(raw[32:64], 'big')
        return raw[64:64 + length].decode('utf-8', 'replace')
    return None


def rpc_facts(network, token):
    rpc = onchain.Rpc(network)
    rpc.snapshot()
    code = rpc.call('eth_getCode', [token, rpc.block['number']])
    facts = dict(block=int(rpc.block['number'], 16), has_code=code not in ('0x', '0x0'), code_bytes=(len(code) - 2) // 2)
    if not facts['has_code']:
        return facts
    for key, selector in (('name', '06fdde03'), ('symbol', '95d89b41')):
        try:
            facts[key] = abi_string(rpc.read(token, selector))
        except (ValueError, OSError):
            facts[key] = 'UNREADABLE'
    try:
        facts['decimals'] = onchain.uint(rpc.read(token, '313ce567'))
        facts['total_supply_raw'] = onchain.uint(rpc.read(token, '18160ddd'))
        facts['total_supply'] = facts['total_supply_raw'] / 10 ** facts['decimals']
    except (ValueError, OSError):
        facts['decimals'] = 'UNREADABLE'
    facts['owner_control'] = onchain.owner_control(rpc, token)
    return facts


def goplus(chain_id, token):
    raw = get_json(f'https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token}')
    info = (raw.get('result') or {}).get(token.lower())
    if raw.get('code') != 1 or not isinstance(info, dict):
        return dict(status='NO_DATA', code=raw.get('code'), message=raw.get('message'))
    out = {k: info.get(k) for k in GOPLUS_FIELDS if k in info}
    out['top_holders'] = [dict(address=h.get('address'), percent=h.get('percent'), tag=h.get('tag'), is_contract=h.get('is_contract'), is_locked=h.get('is_locked'))
                          for h in (info.get('holders') or [])[:10] if isinstance(h, dict)]
    out['lp_holders'] = [dict(address=h.get('address'), percent=h.get('percent'), tag=h.get('tag'), is_locked=h.get('is_locked'), is_contract=h.get('is_contract'))
                         for h in (info.get('lp_holders') or [])[:6] if isinstance(h, dict)]
    return out


def dexscreener(token):
    raw = get_json(f'https://api.dexscreener.com/latest/dex/tokens/{token}')
    pairs = raw.get('pairs') or []
    keep = ('chainId', 'dexId', 'pairAddress', 'priceUsd', 'fdv', 'marketCap', 'pairCreatedAt')
    rows = []
    for p in pairs[:10]:
        row = {k: p.get(k) for k in keep}
        row['base'] = (p.get('baseToken') or {}).get('symbol')
        row['quote'] = (p.get('quoteToken') or {}).get('symbol')
        row['liquidityUsd'] = (p.get('liquidity') or {}).get('usd')
        row['volume24h'] = (p.get('volume') or {}).get('h24')
        row['txns24h'] = (p.get('txns') or {}).get('h24')
        row['priceChange'] = p.get('priceChange')
        row['socials'] = [s.get('url') for s in ((p.get('info') or {}).get('socials') or [])][:4]
        row['websites'] = [w.get('url') for w in ((p.get('info') or {}).get('websites') or [])][:2]
        rows.append(row)
    return rows


def main(argv, out=print):
    if len(argv) != 1:
        raise SystemExit('usage: token_probe.py 0xTOKEN')
    token = onchain.address(argv[0])
    out('PROBE target ' + token)
    for network, chain_id in CHAINS.items():
        for name, call in (('rpc', lambda: rpc_facts(network, token)), ('goplus', lambda: goplus(chain_id, token))):
            try:
                result = call()
            except (ValueError, OSError, KeyError, TypeError) as exc:
                result = dict(status='UNKNOWN', error=f'{type(exc).__name__}: {str(exc)[:160]}')
            out(f'PROBE {network} {name} ' + json.dumps(result, default=str, sort_keys=True))
    try:
        out('PROBE dexscreener ' + json.dumps(dexscreener(token), default=str))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        out('PROBE dexscreener ' + json.dumps(dict(status='UNKNOWN', error=f'{type(exc).__name__}: {str(exc)[:160]}')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
