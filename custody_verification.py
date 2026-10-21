"""Safe signing-authority corroboration, never natural-person beneficial ownership.

Docs: https://docs.safe.global/core-api/transaction-service-reference
EOA keys, custodial clients, hidden agreements and related wallets remain unknown.
"""
from onchain import Rpc,address,uint,word_address
from verification import observation


def owners(value):
    if not isinstance(value,str) or not value.startswith('0x') or len(value)<130:
        raise ValueError('Invalid ABI owners')
    words=[value[i:i+64] for i in range(2,len(value),64)]
    if len(value[2:])%64 or int(words[0],16)!=32:raise ValueError('Invalid owner array offset')
    count=int(words[1],16)
    if not 0<count<=100 or len(words)!=count+2:raise ValueError('Invalid owner count')
    result=[word_address('0x'+x) for x in words[2:]]
    if len(set(result))!=len(result):raise ValueError('Duplicate owners')
    return result


def collect(item,rows,fetch,rpc=None):
    if item.get('network')!='eth':
        return observation('safe_custody','',None,'UNKNOWN','Reviewed Safe service mapping unavailable for this network')
    try:
        rpc=rpc or Rpc('eth');block=rpc.snapshot();results=[];seen=set()
        for row in rows[:5]:
            owner=address(row['address'])
            if owner in seen:continue
            seen.add(owner)
            code=rpc.call('eth_getCode',[owner,block['number']])
            if code in ('0x','0x0'):continue
            url='https://safe-transaction-mainnet.safe.global/api/v1/safes/'+owner+'/'
            record=dict(address=owner,status='UNKNOWN')
            try:
                raw=fetch(url)
                if address(raw['address'])!=owner:raise ValueError('Safe identity mismatch')
                actual=owners(rpc.read(owner,'a0e67e2b'))
                threshold=uint(rpc.read(owner,'e75235b8'))
                if set(actual)!={address(x) for x in raw['owners']} or threshold!=int(raw['threshold']) or not 1<=threshold<=len(actual):
                    raise ValueError('Safe authority disagreement')
                record.update(status='LIMITED',source=url,raw=raw,onchain_owners=actual,threshold=threshold,
                              reason='Safe signing addresses corroborated; implementation, modules, beneficial persons and cross-wallet control not fully audited')
            except (KeyError,ValueError,TypeError,AttributeError,OSError):
                record['reason']='Contract custody identity/authority unresolved'
            results.append(record)
        rpc.unchanged()
        return observation('safe_custody',rpc.url,dict(block=block,records=results,calls=rpc.calls),'LIMITED',
                           'Bounded signing-authority checks; beneficial ownership and complete related-wallet coverage remain unverified')
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('safe_custody','',None,'UNKNOWN','Custody corroboration unavailable; do not infer independent ownership')
