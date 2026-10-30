"""Pinned-block, read-only EVM evidence. No wallet, signatures or send methods.

RPC API: https://ethereum.org/en/developers/docs/apis/json-rpc/
Pair ABI: https://docs.uniswap.org/contracts/v2/reference/smart-contracts/pair
Reviewed Ethereum/Base/BSC V2 deployments support fungible LP observations.
Reviewed Base V3 identity is separate from NFT custody. V4 and unknown lockers
cannot be treated as fungible locked LP tokens.
"""
import datetime as dt
import json
import re
import pathlib
from provider_session import CURRENT
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
        if CURRENT.get() is not None:
            return CURRENT.get().json(self.url, payload)
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'crypto-oracle-validation/1.0', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)

    def call(self, method, params):
        if method not in ('eth_chainId', 'eth_getBlockByNumber', 'eth_getCode', 'eth_call', 'eth_gasPrice', 'eth_getBalance', 'eth_simulateV1', 'web3_sha3'):
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

    def checksum(self,value):
        value=address(value)[2:]
        digest=self.call('web3_sha3',['0x'+value.encode('ascii').hex()])
        if not isinstance(digest,str) or not re.fullmatch('0x[0-9a-fA-F]{64}',digest):raise ValueError('Invalid checksum hash response')
        hashed=digest[2:]
        return '0x'+''.join(c.upper() if c in 'abcdef' and int(hashed[i],16)>=8 else c for i,c in enumerate(value))

    def unchanged(self):
        block = self.call('eth_getBlockByNumber', [self.block['number'], False])
        if block['hash'] != self.block['hash']:
            raise ValueError('Block reorganized during verification')


def verify_pair(rpc, pair, token):
    pair, token = address(pair), address(token)
    code = rpc.call('eth_getCode', [pair, rpc.block['number']])
    if code in ('0x', '0x0', None):
        raise ValueError('Pair has no contract code')
    token0 = word_address(rpc.read(pair, '0dfe1681'))
    token1 = word_address(rpc.read(pair, 'd21220a7'))
    if token not in (token0, token1) or token0 == token1:
        raise ValueError('Pair token mismatch')
    factory = word_address(rpc.read(pair, 'c45a0155'))
    registry = json.loads(pathlib.Path(__file__).with_name('chain_factories.json').read_text())
    family = registry['v2'].get(str(rpc.chain), {}).get(factory)
    if family is None:
        raise ValueError('Unreviewed factory / unsupported position type')
    stable = None
    arguments = token0[2:].zfill(64) + token1[2:].zfill(64)
    if family == 'AerodromeV2':
        stable_value = uint(rpc.read(pair, '22be3de1'))
        if stable_value not in (0, 1):
            raise ValueError('Invalid stable-pool flag')
        stable = bool(stable_value)
        implementation = word_address(rpc.read(factory, '5c60da1b'))
        expected_clone = '0x363d3d373d3d3d363d73' + implementation[2:] + '5af43d82803e903d91602b57fd5bf3'
        if code.lower() != expected_clone:
            raise ValueError('Aerodrome pool clone does not match factory implementation')
        canonical = word_address(rpc.read(factory, '79bc57d5', arguments + format(stable_value, '064x')))
    else:
        canonical = word_address(rpc.read(factory, 'e6a43905', arguments))
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
    return dict(pair=pair, factory=factory, token0=token0, token1=token1, protocol=family, position_type='fungible_v2_lp',
                stable_pool=stable, total_lp_base_units=str(supply), burned_lp_balances={k: str(v) for k, v in burned.items()},
                burned_lp_fraction=sum(burned.values()) / supply,
                reserves_base_units=[str(v) for v in reserves],
                lock_coverage_complete=False,
                limitation='Burn-address holdings observed; timelock custody, expiry and V3/V4 positions not verified')


def verify_v3_pool(rpc,pair,token):
    pair,token=address(pair),address(token)
    registry=json.loads(pathlib.Path(__file__).with_name('chain_factories.json').read_text())
    factory=word_address(rpc.read(pair,'c45a0155'))
    family=registry['v3'].get(str(rpc.chain),{}).get(factory)
    if family is None:raise ValueError('Unreviewed concentrated-liquidity factory')
    token0=word_address(rpc.read(pair,'0dfe1681'));token1=word_address(rpc.read(pair,'d21220a7'))
    if token not in (token0,token1) or token0==token1:raise ValueError('Pool token mismatch')
    fee=uint(rpc.read(pair,'ddca3f43'))
    if not 0<=fee<1000000:raise ValueError('Invalid fee tier')
    spacing=None;pool_key=fee;selector='1698ee82'
    if family=='AerodromeSlipstream':
        spacing=uint(rpc.read(pair,'d0c93a7c'))
        if not 0<spacing<2**23:raise ValueError('Invalid tick spacing')
        pool_key=spacing;selector='28af8d0b'
    args=token0[2:].zfill(64)+token1[2:].zfill(64)+format(pool_key,'064x')
    if word_address(rpc.read(factory,selector,args))!=pair:raise ValueError('Factory getPool does not recognize exact pool')
    liquidity=uint(rpc.read(pair,'1a686502'))
    if liquidity<=0:raise ValueError('No active liquidity')
    return dict(pair=pair,factory=factory,token0=token0,token1=token1,protocol=family,
                fee_tier_pips=fee,tick_spacing=spacing,active_liquidity=str(liquidity),position_type='concentrated_nft',
                lock_coverage_complete=False,
                limitation='Exact V3 pool identity/active liquidity corroborated; position NFT owners, ranges and escrow restrictions unverified')


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
            try:
                lp=verify_v3_pool(rpc,item['address'],item['token_address'])
                results['lp']=dict(status='LIMITED',reason=lp['limitation'],metrics=lp)
            except (KeyError,ValueError,TypeError,OSError):
                results['lp'] = dict(status='UNKNOWN', reason='Unsupported pair/factory or unavailable LP proof')
        concentration = holder_concentration(rpc, item['token_address'], provider_rows)
        results['holders'] = dict(status='LIMITED', reason=concentration['limitation'], metrics=concentration)
        rpc.unchanged()
        return observation('evm_rpc', rpc.url, dict(block=block, calls=rpc.calls, results=results),
                           'LIMITED', 'Pinned-block independent observations; beneficial ownership and timelock coverage not established')
    except (KeyError, ValueError, TypeError, OSError, AttributeError, OverflowError) as exc:
        from evidence_coverage import unavailable
        result = unavailable('evm_rpc', getattr(rpc, 'url', ''), exc)
        result['raw'] = dict(calls=getattr(rpc, 'calls', []))
        return result
