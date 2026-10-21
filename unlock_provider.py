"""Tokenomist v5 optional authenticated unlock/allocation evidence.

Docs: https://docs.tokenomist.ai/api-documents/daily-emission/v5
Token-list has no contract address: an explicit sourced binding is mandatory.
Its slug/symbol is never inferred from a token name. TBD/untracked allocations
and bounded pagination cannot become complete future supply verification.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from decimal import Decimal
from supply_evidence import nonnegative
from token_unlocks import timestamp
from verification import observation

BASE='https://api.tokenomist.ai'


def request(url,key):
    req=urllib.request.Request(url,headers={'x-api-key':key,'User-Agent':'crypto-oracle-validation/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)


def validate(raw,now):
    if raw.get('status') is not True:raise ValueError('Provider unsuccessful')
    if not 0<=now-timestamp(raw['metadata']['queryDate'])<=300:raise ValueError('Stale/future provider snapshot')
    # API quota metadata is private operational context and is not evidence.
    raw=dict(raw);raw['metadata']={k:v for k,v in raw['metadata'].items() if k!='credit'}
    return raw


def collect(item,registry,env,transport=request,now=None):
    now=int(now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp())
    binding=registry.get('provider_bindings',{}).get(item.get('network','')+':'+item.get('token_address','').lower())
    key=env.get('TOKENOMIST_API_KEY','')
    if not key or not binding:
        return observation('tokenomist',BASE,None,'UNKNOWN','Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing')
    collected=[]
    try:
        slug=binding['tokenomist_id'];source=urllib.parse.urlsplit(binding['source_url'])
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,99}',slug) or source.scheme!='https' or not source.hostname or source.username or source.password:raise ValueError('Invalid provider binding')
        if not 0<=now-timestamp(binding['observed_at'])<=86400:raise ValueError('Binding stale/future')
        token_list=validate(transport(BASE+'/v5/token/list?'+urllib.parse.urlencode(dict(tokenId=slug)),key),now)
        matches=[x for x in token_list['data'] if x.get('id')==slug]
        if len(matches)!=1:raise ValueError('Provider dataset absent/ambiguous')
        collected.append(token_list)
        allocations=validate(transport(BASE+'/v5/allocations/'+slug,key),now);collected.append(allocations)
        data=allocations['data']
        tbd=nonnegative(data['totalTBDLockedAmount']);untracked=nonnegative(data['totalUntrackedAmount'])
        start=dt.datetime.fromtimestamp(now,dt.timezone.utc).date()
        end=start+dt.timedelta(days=365)
        rows=[];pages=None;expected_total=None
        for page in range(1,5):
            url=BASE+'/v5/daily-emission/'+slug+'?'+urllib.parse.urlencode(dict(start=str(start),end=str(end),page=page,pageSize=100))
            response=validate(transport(url,key),now);collected.append(response)
            meta=response['metadata']
            if type(meta['page']) is not int or meta['page']!=page or type(meta['totalPages']) is not int or type(meta['total']) is not int:raise ValueError('Invalid pagination')
            if meta['totalPages']<1 or meta['total']<0:raise ValueError('Invalid pagination count')
            if pages is None:pages=meta['totalPages'];expected_total=meta['total']
            if pages!=meta['totalPages'] or expected_total!=meta['total']:raise ValueError('Pagination changed during collection')
            if not isinstance(response['data'],list):raise ValueError('Invalid emission rows')
            rows.extend(response['data'])
            if page>=pages:break
        if not rows:raise ValueError('No emission rows cannot establish zero future unlocks')
        complete=pages<=4 and len(rows)==expected_total
        rows.sort(key=lambda x:timestamp(x['startDate']))
        previous_end=None
        seen=set();amount=Decimal(0)
        for row in rows:
            a,b=timestamp(row['startDate']),timestamp(row['endDate'])
            if b<=a or a in seen or not timestamp(str(start)+'T00:00:00+00:00')<=a<timestamp(str(end)+'T00:00:00+00:00'):raise ValueError('Invalid/duplicate emission interval')
            if previous_end is not None and a<previous_end:raise ValueError('Overlapping emission intervals')
            if b>timestamp(str(end)+'T00:00:00+00:00'):raise ValueError('Emission extends beyond queried window')
            previous_end=b
            seen.add(a);amount+=nonnegative(row['unlockAmount'])
        result=observation('tokenomist',BASE,collected,'LIMITED','Provider emissions only; exact-contract binding, TBD/untracked coverage, on-chain vesting and mint authority remain independently unverified')
        result['metrics']=dict(tokenomist_id=slug,binding_source=binding['source_url'],future_window_days=365,
            window_pagination_complete=complete,observed_emission_unlock_tokens=str(amount),
            tbd_locked_tokens=str(tbd),untracked_tokens=str(untracked),
            complete_future_coverage_verified=False,independent_contract_binding_verified=False)
        return result
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('tokenomist',BASE,collected or None,'UNKNOWN','Provider authentication, binding, allocation or pagination evidence incomplete/conflicting')
