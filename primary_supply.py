"""Source-specific issuer disclosures, never a complete circulation/authority audit."""
import datetime as dt
import hashlib
import json
from decimal import Decimal

LINK='0x514910771af9ca656af840dff83e8264ecf986ca'
URL='https://supply.chain.link/supply'
REFERENCE='https://chain.link/circulating-supply'


def integer(value):
    if not isinstance(value,str) or not value.isascii() or not value.isdigit() or len(value)>80:
        raise ValueError('Explicit unsigned base-unit string required')
    return int(value)


def analyze(raw):
    total=integer(raw['totalSupply']);circulating=integer(raw['circulatingSupply'])
    if total!=10**27 or not 0<circulating<=total:raise ValueError('Issuer total/circulation invalid')
    balances=raw['balances'];seen=set();noncirculating=0
    if not isinstance(balances,list) or not 1<=len(balances)<=100:raise ValueError('Bounded issuer-wallet list required')
    import re
    for row in balances:
        address=row['address']
        if not isinstance(address,str) or not re.fullmatch('0x[0-9a-fA-F]{40}',address) or address.lower()in seen:
            raise ValueError('Invalid/duplicate issuer wallet')
        seen.add(address.lower());noncirculating+=integer(row['balance'])
    if noncirculating!=total-circulating:raise ValueError('Issuer-wallet balances do not reconcile to circulation')
    return dict(total_supply=str(Decimal(total)/10**18),circulating_supply=str(Decimal(circulating)/10**18),
                disclosed_noncirculating_wallets=sorted(seen),
                independent_onchain_balances_verified=False,complete_unlock_coverage_verified=False,
                interpretation='Issuer definition of circulation; published wallet balances are not independently checked at a pinned block')


def collect(asset,fetch,provider_supply=None):
    if asset.get('network')!='eth' or str(asset.get('token_address','')).lower()!=LINK:
        return dict(status='NOT_SUPPORTED',reason='No registered issuer supply adapter for this exact asset')
    result=dict(status='UNKNOWN',source_url=URL,reference_url=REFERENCE,network='eth',contract=LINK,
                retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),provider_updated_at=None,
                freshness_scope='Retrieval time only; issuer endpoint provides no observation timestamp')
    try:
        raw=fetch(URL);result['raw']=raw
        result['response_sha256']=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result['metrics']=analyze(raw);result['status']='ISSUER_DISCLOSURE'
        if provider_supply:
            for field,key in (('circulating_supply','circulating'),('total_supply','total')):
                supplied=provider_supply[key]
                if isinstance(supplied,bool):raise ValueError('Boolean provider measurement')
                other=Decimal(str(supplied));primary=Decimal(result['metrics'][field])
                if not other.is_finite() or other<=0:raise ValueError('Invalid provider measurement')
                if abs(other-primary)/primary>Decimal('.01'):
                    result['status']='CONFLICTING';result['reason']='Issuer and independent provider supply differ by more than 1%';return result
            result['status']='CORROBORATED_DISCLOSURE'
            result['reason']='Issuer wallet arithmetic and provider estimates agree within 1%; independent balances, unlock coverage and authority remain unverified'
    except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
        result['status']='UNKNOWN';result['reason']='Issuer disclosure unavailable/invalid: '+type(exc).__name__
    return result
