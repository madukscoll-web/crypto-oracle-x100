"""Independent current supply comparison; current supply is not unlock coverage.

Blockscout token-info and CoinGecko contract-address endpoints are keyed by exact
chain/contract. Gross on-chain supply and provider circulating definitions may
legitimately differ: report conflicts rather than silently choosing one.
"""
import datetime as dt
from decimal import Decimal,InvalidOperation
from onchain import Rpc,address,uint,ZERO,DEAD
from verification import observation

PLATFORMS={'eth':'ethereum','base':'base','bsc':'binance-smart-chain'}
EXPLORERS={'eth':'https://eth.blockscout.com','base':'https://base.blockscout.com'}


def nonnegative(value):
    if value is None or isinstance(value,bool):raise ValueError('Missing supply measurement')
    try:number=Decimal(str(value))
    except InvalidOperation as exc:raise ValueError('Invalid supply') from exc
    if not number.is_finite() or number<0:raise ValueError('Invalid supply')
    return number


def compare(coingecko,rpc_total,decimals,platform,token,now):
    if address(coingecko['platforms'][platform])!=address(token):raise ValueError('Provider contract mismatch')
    stamp=dt.datetime.fromisoformat(coingecko['last_updated'].replace('Z','+00:00'))
    if stamp.tzinfo is None or not 0<=now-stamp.timestamp()<=300:raise ValueError('Provider supply stale/future')
    market=coingecko['market_data']
    total=nonnegative(market['total_supply']);circulating=nonnegative(market['circulating_supply'])
    if total<=0 or circulating>total:raise ValueError('Invalid supply relationship')
    gross=Decimal(rpc_total)/Decimal(10**decimals)
    divergence=abs(total-gross)/gross
    return dict(provider_total_tokens=str(total),provider_circulating_tokens=str(circulating),
                provider_max_supply_tokens=None if market.get('max_supply') is None else str(nonnegative(market['max_supply'])),
                onchain_gross_total_tokens=str(gross),relative_total_divergence=str(divergence),
                definitions_resolved=False,complete_vesting_and_mint_coverage=False)


def sink_reconciliation(provider_total,total,decimals,balances):
    """Compare definitions, not safety: a sink balance is not a burn audit."""
    if set(balances)!={ZERO,DEAD} or any(type(x) is not int or not 0<=x<=total for x in balances.values()):
        raise ValueError('Pinned known-sink balances incomplete or invalid')
    sink_total=sum(balances.values())
    if sink_total>total:raise ValueError('Sink balances exceed gross total')
    net=Decimal(total-sink_total)/Decimal(10**decimals)
    provider=nonnegative(provider_total)
    match=net>0 and abs(provider-net)/net<=Decimal('.001')
    return dict(known_sink_balances_base_units={k:str(v) for k,v in balances.items()},
        observed_net_of_known_sinks_tokens=str(net),provider_total_matches_net_of_known_sinks=match,
        burn_authority_or_circulating_supply_verified=False)


def collect(item,fetch,rpc=None):
    observations={}
    try:
        token=address(item['token_address']);platform=PLATFORMS[item['network']]
        rpc=rpc or Rpc(item['network']);block=rpc.snapshot()
        total=uint(rpc.read(token,'18160ddd'));decimals=uint(rpc.read(token,'313ce567'))
        if total<=0 or decimals>36:raise ValueError('Unsupported token units')
        conflicts=[]
        if item['network'] in EXPLORERS:
            url=EXPLORERS[item['network']]+'/api/v2/tokens/'+token
            try:
                raw=fetch(url)
                if address(raw['address_hash'])!=token or int(raw['decimals'])!=decimals or raw.get('type')!='ERC-20':raise ValueError('Explorer identity/units mismatch')
                explorer=nonnegative(raw['total_supply'])
                if explorer!=explorer.to_integral():raise ValueError('Fractional base units')
                observations['blockscout']=dict(url=url,raw=raw,matches_pinned_total=int(explorer)==total)
                if int(explorer)!=total:conflicts.append('Explorer total differs from pinned RPC total; index lag or supply conflict unresolved')
            except (KeyError,ValueError,TypeError,OSError):observations['blockscout']=dict(status='UNKNOWN',reason='Explorer identity/supply unavailable or invalid')
        url='https://api.coingecko.com/api/v3/coins/'+platform+'/contract/'+token
        try:
            raw=fetch(url)
            metrics=compare(raw,total,decimals,platform,token,dt.datetime.now(dt.timezone.utc).timestamp())
            observations['coingecko']=dict(url=url,raw=raw,metrics=metrics)
            # Rounding tolerance is for diagnostics only, never a verification pass.
            if Decimal(metrics['relative_total_divergence'])>Decimal('.001'):
                try:
                    sinks=sink_reconciliation(metrics['provider_total_tokens'],total,decimals,
                        {owner:rpc.balance(token,owner) for owner in (ZERO,DEAD)})
                    metrics.update(sinks)
                except (ValueError,TypeError,AttributeError,OSError,KeyError):
                    sinks={}
                if not sinks.get('provider_total_matches_net_of_known_sinks'):
                    conflicts.append('CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved')
        except (KeyError,ValueError,TypeError,OSError,OverflowError):observations['coingecko']=dict(status='UNKNOWN',reason='Exact-contract current supply unavailable, stale or invalid')
        rpc.unchanged()
        return observation('supply_comparison',rpc.url,dict(block=block,total_supply_base_units=str(total),decimals=decimals,
                    observations=observations,conflicts=conflicts,calls=rpc.calls),'CONFLICTING' if conflicts else 'LIMITED',
                    '; '.join(conflicts) if conflicts else ('Provider total aligns with pinned gross supply minus known-sink balances; burn/circulation definitions remain unverified' if ((observations.get('coingecko') or {}).get('metrics') or {}).get('provider_total_matches_net_of_known_sinks') else 'Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified'))
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('supply_comparison','',observations or None,'UNKNOWN','Pinned supply/units or independent evidence unavailable')

