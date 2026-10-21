"""Pinned-block, read-only EVM evidence. No wallet, signatures or send methods.

RPC API: https://ethereum.org/en/developers/docs/apis/json-rpc/
Pair ABI: https://docs.uniswap.org/contracts/v2/reference/smart-contracts/pair
Only canonical Ethereum Uniswap V2 is recognized initially. V3/V4 positions and
unknown lockers cannot be treated as fungible locked LP tokens.
"""
import datetime as dt
import json
import re
import urllib.request
from verification import observation

ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}')
ZERO = '0x' + '0' * 40
DEAD = '0x000000000000000000000000000000000000dead'
FACTORY = '0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f'
RPCS = {'eth': ('https://ethereum-rpc.publicnode.com', 1),
        'base': ('https://base-rpc.publicnode.com', 8453),
        'bsc': ('https://bsc-rpc.publicnode.com', 56)}


def address(value):
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise ValueError('Invalid address')
    return value.lower()


def word_address(value):
    if not isinstance(value, str) or not re.fullmatch('0x0{24}[0-9a-fA-F]{40}', value):
        raise ValueError('Invalid ABI address')
    return address('0x' + value[-40:])


def uint(value):
    if not isinstance(value, str) or not re.fullmatch('0x[0-9a-fA-F]{64}', value):
        raise ValueError('Invalid ABI uint256')
    return int(value, 16)


class Rpc:
    def __init__(self, network, transport=None):
        self.url, self.chain = RPCS[network]
        self.transport = transport or self._http
        self.calls = []

    def _http(self, payload):
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'crypto-oracle-validation/1.0', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)

    def call(self, method, params):
        if method not in ('eth_chainId', 'eth_getBlockByNumber', 'eth_getCode', 'eth_call', 'eth_gasPrice', 'eth_getBalance', 'eth_simulateV1'):
            raise ValueError('RPC method is not read-only allowlisted')
        payload = dict(jsonrpc='2.0', id=len(self.calls) + 1, method=method, params=params)
        raw = self.transport(payload)
        self.calls.append(dict(request=payload, response=raw))
        if not isinstance(raw, dict) or raw.get('id') != payload['id'] or raw.get('error') or 'result' not in raw:
            raise ValueError('Invalid RPC response')
        return raw['result']

    def snapshot(self, now=None):
        now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
        if int(self.call('eth_chainId', []), 16) != self.chain:
            raise ValueError('RPC chain mismatch')
        block = self.call('eth_getBlockByNumber', ['latest', False])
        if not re.fullmatch('0x[0-9a-fA-F]{64}', block['hash']):
            raise ValueError('Missing block hash')
        age = now - int(block['timestamp'], 16)
        if not 0 <= age <= 180:
            raise ValueError('RPC head stale or future dated')
        int(block['number'], 16)
        self.block = block
        return block

    def read(self, contract, selector, args=''):
        return self.call('eth_call', [{'to': address(contract), 'data': '0x' + selector + args}, self.block['number']])

    def balance(self, token, owner):
        return uint(self.read(token, '70a08231', address(owner)[2:].zfill(64)))

    def unchanged(self):
        block = self.call('eth_getBlockByNumber', [self.block['number'], False])
        if block['hash'] != self.block['hash']:
            raise ValueError('Block reorganized during verification')


def verify_pair(rpc, pair, token):
    pair, token = address(pair), address(token)
    if rpc.chain != 1:
        raise ValueError('No reviewed factory for this network')
    code = rpc.call('eth_getCode', [pair, rpc.block['number']])
    if code in ('0x', '0x0', None):
        raise ValueError('Pair has no contract code')
    token0 = word_address(rpc.read(pair, '0dfe1681'))
    token1 = word_address(rpc.read(pair, 'd21220a7'))
    if token not in (token0, token1) or token0 == token1:
        raise ValueError('Pair token mismatch')
    factory = word_address(rpc.read(pair, 'c45a0155'))
    if factory != FACTORY:
        raise ValueError('Unreviewed factory / unsupported position type')
    canonical = word_address(rpc.read(FACTORY, 'e6a43905', token0[2:].zfill(64) + token1[2:].zfill(64)))
    if canonical != pair:
        raise ValueError('Factory does not recognize exact pair')
    supply = uint(rpc.read(pair, '18160ddd'))
    if supply <= 0:
        raise ValueError('Zero LP supply')
    burned = {owner: rpc.balance(pair, owner) for owner in (ZERO, DEAD)}
    if sum(burned.values()) > supply:
        raise ValueError('LP balances exceed supply')
    reserves = rpc.read(pair, '0902f1ac')
    if not re.fullmatch('0x[0-9a-fA-F]{192}', reserves):
        raise ValueError('Invalid pair reserves')
    reserves = [int(reserves[i:i+64], 16) for i in (2, 66)]
    if min(reserves) <= 0:
        raise ValueError('Empty reserves')
    return dict(pair=pair, factory=factory, token0=token0, token1=token1,
                total_lp_base_units=str(supply), burned_lp_balances={k: str(v) for k, v in burned.items()},
                burned_lp_fraction=sum(burned.values()) / supply,
                reserves_base_units=[str(v) for v in reserves],
                lock_coverage_complete=False,
                limitation='Burn-address holdings observed; timelock custody, expiry and V3/V4 positions not verified')


def holder_concentration(rpc, token, provider_rows, pair=None):
    supply = uint(rpc.read(token, '18160ddd'))
    if supply <= 0:
        raise ValueError('Zero token supply')
    owners = [ZERO, DEAD]
    for row in provider_rows[:20]:
        owner = address(row['address'])
        if owner in owners:
            continue
        owners.append(owner)
    balances = {owner: rpc.balance(token, owner) for owner in owners}
    if sum(balances.values()) > supply:
        raise ValueError('Observed balances exceed token supply')
    burned = balances[ZERO] + balances[DEAD]
    live_supply = supply - burned
    if live_supply <= 0:
        raise ValueError('No non-burn supply')
    # Exchange/LP tags and common funders never prove beneficial ownership.
    # No custodial or LP holder is silently excluded from concentration bounds.
    observed = {k: v for k, v in balances.items() if k not in (ZERO, DEAD)}
    return dict(total_supply_base_units=str(supply), burned_base_units=str(burned),
                non_burn_supply_base_units=str(live_supply),
                balances_base_units={k: str(v) for k, v in balances.items()},
                listed_coverage_fraction=sum(observed.values()) / live_supply,
                largest_observed_wallet_fraction=max(observed.values(), default=0) / live_supply,
                beneficial_cluster_upper_bound_fraction=1.0,
                verified_beneficial_ownership=False,
                limitation='Unknown holders or common control may own all non-burn supply; provider tags are unverified')


def collect(item, provider_rows=(), rpc=None, lock_descriptors=()):
    try:
        rpc = rpc or Rpc(item['network'])
        block = rpc.snapshot()
        results = {}
        try:
            lp = verify_pair(rpc, item['address'], item['token_address'])
            from lp_locks import analyze
            lp['escrow_analysis'] = analyze(rpc, lp, list(lock_descriptors))
            results['lp'] = dict(status='LIMITED', reason=lp['limitation'], metrics=lp)
        except (KeyError, ValueError, TypeError, OSError):
            results['lp'] = dict(status='UNKNOWN', reason='Unsupported pair/factory or unavailable LP proof')
        concentration = holder_concentration(rpc, item['token_address'], provider_rows)
        results['holders'] = dict(status='LIMITED', reason=concentration['limitation'], metrics=concentration)
        rpc.unchanged()
        return observation('evm_rpc', rpc.url, dict(block=block, calls=rpc.calls, results=results),
                           'LIMITED', 'Pinned-block independent observations; beneficial ownership and timelock coverage not established')
    except (KeyError, ValueError, TypeError, OSError, AttributeError, OverflowError):
        return observation('evm_rpc', getattr(rpc, 'url', ''), dict(calls=getattr(rpc, 'calls', [])), 'UNKNOWN', 'RPC evidence unavailable, stale, malformed or chain/block identity mismatch')
