"""Sourcify source reproduction claims cross-checked against pinned RPC code.

Docs: https://docs.sourcify.dev/docs/api/
Source verification is a scoped property, never a security/ownership audit.
"""
import hashlib
import json
import pathlib
from onchain import Rpc, address
from verification import observation


def inspect(raw, rpc, target, profile=None):
    target=address(target)
    if address(raw['address'])!=target or str(raw['chainId'])!=str(rpc.chain):
        raise ValueError('Source identity mismatch')
    if raw.get('runtimeMatch')!='match':
        raise ValueError('Exact runtime source match unavailable')
    code=rpc.call('eth_getCode',[target,rpc.block['number']])
    published=raw['runtimeBytecode']['onchainBytecode']
    if not isinstance(code,str) or code in ('0x','0x0') or code.lower()!=str(published).lower():
        raise ValueError('Verified source runtime differs from pinned-chain code')
    sources=raw.get('sources')
    if not isinstance(sources,dict) or not sources:
        raise ValueError('Verified sources missing')
    hashes={name:hashlib.sha256(source['content'].encode()).hexdigest() for name,source in sources.items()}
    proxy=raw.get('proxyResolution') or {}
    functions=[x['name'] for x in raw.get('abi',[]) if x.get('type')=='function']
    canonical=False
    if profile and proxy.get('isProxy') is False:
        allowed={x['sha256'] for x in profile['files'].values()}
        primary=profile['files']['token/ERC20/utils/TokenTimelock.sol']['sha256']
        canonical=(raw.get('compilation',{}).get('name')==profile['compilation_name']
                   and primary in hashes.values() and set(hashes.values())==allowed)
    return dict(runtime_source_match=True,source_sha256=hashes,
                runtime_sha256=hashlib.sha256(bytes.fromhex(code[2:])).hexdigest(),
                compiler=raw.get('compilation'),proxy_resolution=proxy,
                exposed_functions=sorted(set(functions)),canonical_timelock_source=canonical,
                independent_local_compiler_reproduction=False,
                mint_and_upgrade_authority_audited=False,
                limitation='Source service match corroborated with RPC runtime; no full authority, ownership or vesting-completeness audit')


def collect(item,fetch,rpc=None,target=None):
    try:
        target=address(target or item['token_address'])
        rpc=rpc or Rpc(item['network']);block=rpc.snapshot()
        url=f'https://sourcify.dev/server/v2/contract/{rpc.chain}/{target}?fields=all'
        raw=fetch(url)
        profile=json.loads(pathlib.Path(__file__).with_name('source_profiles.json').read_text())
        metrics=inspect(raw,rpc,target,profile)
        rpc.unchanged()
        result=observation('sourcify',url,dict(source=raw,block=block,calls=rpc.calls),'LIMITED',metrics['limitation'])
        result['metrics']=metrics
        return result
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError) as exc:
        result=observation('sourcify','',None,'UNKNOWN','Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion')
        result['diagnostic']=dict(error_type=type(exc).__name__,http_status=getattr(exc,'code',None))
        return result
