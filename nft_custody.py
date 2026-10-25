"""Bounded V3 position NFT custody, bound to official chain deployments.

Provider NFT IDs are candidates only. Validate the canonical pool and manager,
position tokens/fee, ownerOf and getApproved at one pinned block. Do not infer
position percentages, complete inventory, beneficial ownership or lock expiry.
"""
import json
import pathlib
from onchain import Rpc,address,word_address,verify_v3_pool,uint
from verification import observation


def inspect(rpc,pool,manager,token_id,claimed_owner):
    argument=format(token_id,'064x')
    raw=rpc.read(manager,'99fbab88',argument)
    if not isinstance(raw,str) or len(raw)!=2+12*64:raise ValueError('Invalid position ABI')
    words=[raw[i:i+64] for i in range(2,len(raw),64)]
    token0=word_address('0x'+words[2]);token1=word_address('0x'+words[3]);fee=int(words[4],16)
    key=pool.get('tick_spacing') if pool.get('tick_spacing') is not None else pool['fee_tier_pips']
    if (token0,token1,fee)!=(pool['token0'],pool['token1'],key):raise ValueError('NFT belongs to a different pool')
    owner=word_address(rpc.read(manager,'6352211e',argument))
    approved=word_address(rpc.read(manager,'081812fc',argument))
    if approved!=word_address('0x'+words[1]):raise ValueError('NFT approval evidence conflicts')
    low=int.from_bytes(bytes.fromhex(words[5]),'big',signed=True);high=int.from_bytes(bytes.fromhex(words[6]),'big',signed=True)
    if not -887272<=low<high<=887272:raise ValueError('Invalid tick range')
    return dict(token_id=str(token_id),position_manager=manager,owner=owner,approved_operator=approved,
                matches_provider_owner=owner==address(claimed_owner),tick_lower=low,tick_upper=high,
                position_liquidity=str(int(words[7],16)),beneficial_owner_verified=False,
                all_operator_approvals_audited=False,escrow_release_restrictions_verified=False)


def collect(item,rows,rpc=None):
    if not isinstance(rows,list):return observation('nft_custody','',None,'UNKNOWN','Malformed NFT nomination data')
    ids=[];seen=set()
    for holder in rows[:10]:
        if not isinstance(holder,dict) or not isinstance(holder.get('NFT_list'),list):continue
        for nft in holder['NFT_list'][:20]:
            if not isinstance(nft,dict):continue
            value=nft.get('NFT_id')
            if not isinstance(value,(str,int)) or isinstance(value,bool) or not str(value).isdigit():continue
            token_id=int(value)
            if token_id<=0 or token_id>=2**256 or token_id in seen:continue
            seen.add(token_id);ids.append((token_id,holder.get('address')))
            if len(ids)>=4:break
        if len(ids)>=4:break
    if not ids and not any(isinstance(x,dict) and x.get('address') for x in rows):return observation('nft_custody','',None,'UNKNOWN','No nominated NFT owners/IDs; no custody or absence-of-lock inference')
    try:
        address(item['address']);rpc=rpc or Rpc(item['network']);block=rpc.snapshot()
        pool=verify_v3_pool(rpc,item['address'],item['token_address'])
        registry=json.loads(pathlib.Path(__file__).with_name('chain_factories.json').read_text())
        manager=registry['position_managers'][str(rpc.chain)][pool['factory']]
        if word_address(rpc.read(manager,'c45a0155'))!=pool['factory']:raise ValueError('Position manager factory mismatch')
        enumerated=[];owners_seen=set()
        for holder in rows[:3]:
            try:
                owner=address(holder['address'])
                if owner in owners_seen:continue
                owners_seen.add(owner);balance=rpc.balance(manager,owner)
                for index in range(min(balance,2)):
                    token_id=uint(rpc.read(manager,'2f745c59',owner[2:].zfill(64)+format(index,'064x')))
                    enumerated.append(dict(owner=owner,token_id=str(token_id),source='canonical manager tokenOfOwnerByIndex'))
                    if token_id not in seen:ids.append((token_id,owner));seen.add(token_id)
            except (KeyError,ValueError,TypeError,OSError):continue
        records=[]
        for token_id,owner in ids[:10]:
            try:
                result=inspect(rpc,pool,manager,token_id,owner)
                records.append(dict(status='LIMITED' if result['matches_provider_owner'] else 'CONFLICTING',metrics=result))
            except (KeyError,ValueError,TypeError,OSError) as exc:
                reason='NFT belongs to a different pool' if isinstance(exc,ValueError) and str(exc)=='NFT belongs to a different pool' else 'Position ID/pool/owner/approval evidence unavailable or mismatched'
                records.append(dict(status='UNKNOWN',token_id=str(token_id),reason=reason))
        rpc.unchanged()
        return observation('nft_custody',rpc.url,dict(block=block,pool=pool,records=records,owner_enumeration=enumerated,calls=rpc.calls),'CONFLICTING' if any(x['status']=='CONFLICTING' for x in records) else 'LIMITED',
                           'Bounded canonical NFT custody observations; complete position inventory, beneficial ownership, all approvals and escrow restrictions unverified')
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('nft_custody','',None,'UNKNOWN','Canonical V3 pool/manager mapping or NFT custody evidence unavailable; no ERC20 LP assumption')
