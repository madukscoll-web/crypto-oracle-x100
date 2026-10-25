"""Evidence for explicitly reviewed OpenZeppelin-style TokenTimelock escrows.

A locker label never suffices. Require exact runtime fingerprint, token binding,
beneficiary, release time and current LP balance at the pair snapshot. Proxies,
revocable vesting and arbitrary lock ABIs are deliberately unsupported. Registry
fingerprints are reviewed inputs, not proof that source review was independent;
therefore results remain LIMITED and cannot authorize a BUY.
"""
import hashlib
import re
from urllib.parse import urlsplit
from onchain import address, uint, word_address


def inspect(rpc, pair, descriptor, horizon_seconds=30*86400):
    if descriptor.get('standard') != 'openzeppelin_token_timelock':
        raise ValueError('Unsupported escrow standard')
    contract = address(descriptor['address'])
    source = urlsplit(descriptor['review_source_url'])
    expected = descriptor['runtime_sha256']
    if source.scheme != 'https' or not source.hostname or not re.fullmatch('[0-9a-f]{64}',expected):
        raise ValueError('Missing reviewed source or runtime fingerprint')
    code = rpc.call('eth_getCode',[contract,rpc.block['number']])
    if not re.fullmatch('0x(?:[0-9a-fA-F]{2})+',code):
        raise ValueError('Invalid runtime bytecode')
    if hashlib.sha256(bytes.fromhex(code[2:])).hexdigest() != expected:
        raise ValueError('Escrow runtime fingerprint mismatch')
    token = word_address(rpc.read(contract,'fc0c546a'))
    beneficiary = word_address(rpc.read(contract,'38af3eed'))
    release = uint(rpc.read(contract,'b91d4001'))
    if token != address(pair) or int(rpc.block['timestamp'],16) + horizon_seconds >= release:
        raise ValueError('Wrong LP token or insufficient lock horizon')
    balance = rpc.balance(pair,contract)
    if balance <= 0:
        raise ValueError('Escrow holds no LP tokens')
    return dict(contract=contract,lp_token=token,beneficiary=beneficiary,release_timestamp=release,
                locked_lp_base_units=str(balance),runtime_sha256=expected,
                review_source_url=descriptor['review_source_url'],independent_source_review_verified=False)


def analyze(rpc, pair_metrics, descriptors):
    if not isinstance(descriptors,list) or len(descriptors)>10:
        raise ValueError('Bounded lock descriptor list required')
    results=[]; errors=[]; seen=set()
    burned=sum(int(x) for x in pair_metrics['burned_lp_balances'].values())
    for descriptor in descriptors:
        try:
            contract=address(descriptor['address'])
            if contract in seen or contract in pair_metrics['burned_lp_balances']:
                raise ValueError('Duplicate escrow or burn address')
            seen.add(contract)
            results.append(inspect(rpc,pair_metrics['pair'],descriptor))
        except (KeyError,TypeError,ValueError,OSError):
            errors.append('Escrow proof missing, unsupported, expired or bytecode/identity mismatch')
    covered=burned+sum(int(x['locked_lp_base_units']) for x in results)
    supply=int(pair_metrics['total_lp_base_units'])
    if covered> supply:raise ValueError('Lock coverage exceeds LP supply')
    return dict(escrows=results,errors=errors,covered_lp_fraction=covered/supply,
                minimum_lock_horizon_days=30,complete_lock_inventory_verified=False,
                independently_reviewed_escrow_code=False)
