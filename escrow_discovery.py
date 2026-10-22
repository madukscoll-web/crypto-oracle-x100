"""Discover potential LP escrows without trusting provider lock labels.

Candidates come from provider LP holder addresses but must actually hold the
selected canonical LP token at the pinned block. Only a canonical source profile
and observed bytecode/token/release/balance can corroborate a simple timelock.
Unknown sources and complex lockers stay unresolved; inventory is not complete.
"""
import json
import pathlib
from onchain import Rpc,address,verify_pair
from lp_locks import inspect as inspect_lock
from contract_sources import inspect as inspect_source
from verification import observation


def collect(item,rows,fetch,rpc=None):
    try:
        rpc=rpc or Rpc(item['network']);block=rpc.snapshot()
        pair=verify_pair(rpc,item['address'],item['token_address'])
        profile=json.loads(pathlib.Path(__file__).with_name('source_profiles.json').read_text())
        candidates=[];seen=set()
        for row in rows[:10]:
            owner=address(row['address'])
            if owner in seen:continue
            seen.add(owner)
            balance=rpc.balance(item['address'],owner)
            if balance==0:continue
            code=rpc.call('eth_getCode',[owner,block['number']])
            if code in ('0x','0x0'):continue
            result=dict(address=owner,observed_lp_base_units=str(balance),status='UNKNOWN')
            url=f'https://sourcify.dev/server/v2/contract/{rpc.chain}/{owner}?fields=all'
            try:
                raw=fetch(url);source=inspect_source(raw,rpc,owner,profile)
                result['source']=source
                if not source['canonical_timelock_source']:
                    result['reason']='Verified source does not match reviewed simple timelock profile'
                else:
                    descriptor=dict(address=owner,standard='openzeppelin_token_timelock',
                                    runtime_sha256=source['runtime_sha256'],review_source_url=url)
                    result.update(status='LIMITED',escrow=inspect_lock(rpc,item['address'],descriptor),
                                  reason='Canonical source and pinned escrow properties corroborated; independent build and full inventory still unverified')
            except (KeyError,ValueError,TypeError,AttributeError,OSError):
                result['reason']='Escrow source, bytecode, token, balance or future expiry not corroborated'
            candidates.append(result)
            if len(candidates)>=3:break
        rpc.unchanged()
        return observation('escrow_discovery',rpc.url,dict(block=block,pair=pair,candidates=candidates,calls=rpc.calls),
                           'LIMITED','Bounded provider-nominated escrow search; no complete lock inventory inferred from missing candidates')
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('escrow_discovery','',None,'UNKNOWN','Unsupported pair/factory or unavailable escrow evidence')
