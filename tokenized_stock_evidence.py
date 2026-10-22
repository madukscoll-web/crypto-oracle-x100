"""Scoped public issuer reference for Base B20 tokenized-stock candidates.

Docs: https://docs.base.org/sdks/tokenized-stocks/overview
Issuer metadata and pinned ERC20 reads are observations, never proof of reserves,
legal beneficial ownership, complete mint authority, unlocks or execution.
B20 precompiles have no ordinary deployed bytecode; source absence stays UNKNOWN.
"""
from decimal import Decimal,InvalidOperation
from urllib.parse import urlencode
from onchain import Rpc,address,uint
from verification import observation

BASE='https://api.coinbase.com/v1/tokenized-stocks'
PREFIX='0xb200000000000000000000'


def lookup(token,fetch):
    cursor=None;seen=set();pages=[]
    for _ in range(5):
        query={'page_size':100}
        if cursor:query['page_token']=cursor
        url=BASE+'?'+urlencode(query);raw=fetch(url)
        if not isinstance(raw.get('tokens'),list):raise ValueError('Invalid issuer list')
        pages.append(dict(url=url,raw=raw))
        matches=[x for x in raw['tokens'] if address(x['contract_address'])==token]
        if len(matches)>1:raise ValueError('Duplicate exact-contract records')
        if matches:return matches[0],pages
        cursor=raw.get('next_page_token')
        if not cursor:break
        if not isinstance(cursor,str) or cursor in seen:raise ValueError('Invalid or repeated pagination cursor')
        seen.add(cursor)
    raise ValueError('Exact contract not found in bounded issuer pages; no absence claim')


def collect(item,fetch,rpc=None):
    if item.get('network')!='base' or not str(item.get('token_address','')).lower().startswith(PREFIX):
        return observation('coinbase_stock_reference','',None,'UNKNOWN','Outside Base B20 candidate scope')
    try:
        token=address(item['token_address']);record,pages=lookup(token,fetch)
        rpc=rpc or Rpc('base');block=rpc.snapshot()
        total=uint(rpc.read(token,'18160ddd'));decimals=uint(rpc.read(token,'313ce567'))
        if type(record.get('decimals')) is not int or record['decimals']!=decimals or decimals>36:raise ValueError('Issuer/RPC units mismatch')
        # Omitted supply is not silently treated as zero, despite scalar omission
        # conventions in the issuer API: the observation must carry a value.
        if 'total_supply' not in record or isinstance(record['total_supply'],bool):raise ValueError('Explicit issuer supply unavailable')
        supplied=Decimal(str(record['total_supply']))
        if not supplied.is_finite() or supplied<0:raise ValueError('Invalid issuer supply')
        pinned=Decimal(str(total)+'e-'+str(decimals))  # exact; do not round uint256 supply to Decimal context precision
        multiplier=Decimal(str(record['multiplier']))
        if not multiplier.is_finite() or multiplier<=0:raise ValueError('Invalid share multiplier')
        rpc.unchanged();matches=pinned==supplied
        result=observation('coinbase_stock_reference',BASE,dict(pages=pages,block=block,calls=rpc.calls,record=record),
            'LIMITED' if matches else 'CONFLICTING',
            'Issuer reference and pinned supply agree; no complete mint/unlock, reserve, beneficiary or execution proof' if matches else 'Issuer normalized supply differs from pinned RPC; index timing or supply conflict unresolved')
        result['metrics']=dict(exact_contract_issuer_record=True,normalized_supply_matches_pinned=matches,
            pinned_total_base_units=str(total),decimals=decimals,issuer_total_tokens=str(supplied),
            pinned_total_tokens=str(pinned),share_multiplier=str(multiplier),
            nav_is_executable_quote=False,complete_supply_unlock_coverage=False,beneficial_ownership_verified=False,
            b20_precompile_documentation='https://docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks')
        return result
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError,InvalidOperation) as exc:
        return observation('coinbase_stock_reference',BASE,None,'UNKNOWN',
            'Exact-contract issuer record, explicit supply/units or pinned RPC corroboration unavailable: '+type(exc).__name__)
