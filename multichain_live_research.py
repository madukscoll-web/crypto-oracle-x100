"""Bounded provider-isolated discovery with durable fair rotation. No trading."""
import argparse
import datetime as dt
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from discovery_adapters import RESEARCH_ADAPTERS, GeckoDiscovery, deduplicate, ProfileFallback
from multichain_candidate_rotation import rotate
from provider_session import Session
from global_discovery import EvidenceFetch
from multichain_research_audit import audit
from stonk_launch_discovery import run as stonk_run, URL as STONK_URL
import research_state
import canonical_outcomes
import launchpad_discovery


def _market(fetch, adapters):
    rows=[];failures=[];observations=[]
    # Visit every network's new pools before spending budget on trending pools.
    for mode in ('new_pools','trending_pools'):
        for adapter in adapters:
            try:
                instance=adapter(fetch)
                if not isinstance(instance, GeckoDiscovery) and mode!='new_pools':continue
                result=instance.discover(modes=(mode,)) if isinstance(instance,GeckoDiscovery) else instance.discover()
                rows.extend(result['rows']);failures.extend(result['failures']);observations.extend(result.get('observations',[]))
            except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
                failures.append({'network':adapter.network,'source':'GeckoTerminal','error_type':type(exc).__name__})
    return dict(rows=rows,failures=failures,observations=observations)


def _profiles(fetch, adapters):
    result=dict(rows=[],failures=[],observations=[]);fallback=ProfileFallback(fetch)
    for network in dict.fromkeys(a.network for a in adapters):
        part=fallback.discover(network,limit=2)
        for field in result:result[field].extend(part[field])
    return result


def _launches(stonk_fetch, include_stonk, include_launchpads, request=None, fetch=None):
    result=dict(rows=[],failures=[],observations=[],feeds=[])
    if include_stonk:
        try:
            stonk=stonk_run(fetch=stonk_fetch)
            result['rows'].extend(stonk['tokens']);result['feeds'].append('StonkFun (provider-attested; on-chain unverified)')
            result['observations'].append(dict(source='StonkFun',url=stonk['source_url'],observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),raw=stonk))
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
            result['failures'].append(dict(source='StonkFun',error_type=type(exc).__name__,http_status=getattr(exc,'code',None)))
    if include_launchpads:
        for name, collector in [('LetsBONK',lambda:launchpad_discovery.bonk_discover(fetch,request)),
                                ('pump.fun',lambda:launchpad_discovery.pump_discover(request))]:
            part=collector()
            for field in ('rows','failures','observations'):result[field].extend(part[field])
            if part['rows']:result['feeds'].append(name)
    return result


def _live_task(kind, adapters, include_stonk, include_launchpads):
    # One serial session per provider family; no shared mutable Session across threads.
    with Session(max_requests=80,max_seconds=165,max_request_seconds=10,
                 host_intervals={'api.geckoterminal.com':8.0}) as session:
        if kind=='market':part=_market(EvidenceFetch(session),adapters)
        elif kind=='profiles':part=_profiles(EvidenceFetch(session),adapters)
        else:
            with session.budget(seconds=45,requests=15):
                part=_launches(session.get,include_stonk,include_launchpads,session.json,session.get)
        part['session']=session.summary();part['kind']=kind
        return part


def run(limit=12,cursor=0,fetch=None,adapters=RESEARCH_ADAPTERS,include_profiles=False,
        include_stonk=False,stonk_fetch=None,state=None,include_launchpads=False):
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid limit')
    if type(cursor) is not int or cursor<0:raise ValueError('Invalid cursor')
    adapters=tuple(adapters)
    start=cursor%len(adapters) if adapters else 0
    ordered=adapters[start:]+adapters[:start]
    if fetch is None:
        kinds=['market']+(['profiles'] if include_profiles else [])+(['launches'] if include_stonk or include_launchpads else [])
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(_live_task,kind,ordered,include_stonk,include_launchpads) for kind in kinds]
            parts=[future.result() for future in futures]
    else:
        parts=[_market(fetch,ordered)]
        if include_profiles:parts.append(_profiles(fetch,ordered))
        if include_stonk:parts.append(_launches(stonk_fetch,True,False))
        if include_launchpads:raise ValueError('Use explicit live session or launchpad unit collectors')
    rows=[r for part in parts for r in part['rows']]
    failures=[r for part in parts for r in part['failures']]
    observations=[r for part in parts for r in part['observations']]
    assets=research_state.retain_adverse(deduplicate(rows),state)
    if state is not None:assets=research_state.prioritize(assets,state)
    selection=rotate(assets,per_run=limit,cursor=cursor,enabled=tuple(a.network for a in adapters))
    at=dt.datetime.now(dt.timezone.utc).isoformat();selected=[]
    for asset in selection['selected']:
        pools=asset['pools'];representative=dict(next((p for p in pools if p.get('address')),pools[0]))
        representative['persistent_adverse_reasons']=asset['persistent_adverse_reasons']
        platforms=sorted({p['launchpad'] for p in pools if p.get('launchpad')})
        selected.append(dict(network=asset['network'],token_address=asset['token_address'],asset_key=asset['asset_key'],
            pool_count=sum(bool(p.get('address')) for p in pools),
            discovery_sources=sorted({str(p.get('source') or 'UNKNOWN') for p in pools}),
            launchpad='; '.join(platforms)+' — PROVIDER_ATTESTED OR SINGLE_RPC; NOT INDEPENDENTLY AUDITED' if platforms else 'UNKNOWN — no authenticated launchpad-origin evidence',
            origin_observations=[{k:p.get(k) for k in ('launchpad','launchpad_origin_status','source_url','observed_at','signature','slot')} for p in pools if p.get('launchpad')],
            assessment=canonical_outcomes.assess(representative)))
    report=dict(observed_at=at,mode='READ_ONLY_RESEARCH',orders_allowed=False,buy_authorized=False,telegram_transmission=False,
        observed_pools=sum(bool(row.get('address')) for row in rows),unique_tokens=len(assets),
        requested_networks=list(dict.fromkeys(a.network for a in adapters)),fetch_order=[a.network for a in ordered],
        observed_by_chain=dict(sorted(Counter(r['network'] for r in rows).items())),provider_observations=observations,
        discovery_sources=dict(sorted(Counter(str(r.get('source') or 'UNKNOWN') for r in rows).items())),
        launchpad_direct_feeds_active=[f for part in parts for f in part.get('feeds',[])],
        selected=selected,next_cursor=selection['next_cursor'],deferred=selection['deferred'],failures=failures,
        provider_health=[dict(provider=p.get('kind','injected'),status='DEGRADED' if p['failures'] else 'RESPONDED',
                              failure_count=len(p['failures']),observation_count=len(p['observations']),
                              session=p.get('session')) for p in parts],
        maximum_concurrent_providers=3 if fetch is None else 1,
        classification_counts=dict(Counter(s['assessment']['outcome'] for s in selected)))
    if state is not None:research_state.update(state,selection['selected'],at,selection['next_cursor'])
    report['coverage_audit']=audit(report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int,default=12);parser.add_argument('--cursor',type=int,default=0)
    parser.add_argument('--output',default='multichain_research_report.json')
    parser.add_argument('--include-profiles',action='store_true');parser.add_argument('--include-stonk',action='store_true')
    parser.add_argument('--include-launchpads',action='store_true');parser.add_argument('--state')
    args=parser.parse_args();state=research_state.load(args.state) if args.state else None
    report=run(args.limit,state['cursor'] if state is not None else args.cursor,
        include_profiles=args.include_profiles,include_stonk=args.include_stonk,state=state,include_launchpads=args.include_launchpads)
    with open(args.output,'w') as stream:json.dump(report,stream,indent=2)
    if args.state:research_state.save(state,args.state)
    print(json.dumps({k:v for k,v in report.items() if k not in ('selected','provider_observations')}))
