"""Two-layer research increment: global identity/discovery + exact Gate Spot joins.

Read-only, timestamped evidence and preview text only. No Telegram transmission,
production state writes, accounts, signatures, approvals, order endpoints or trades.
"""
import argparse
import project_context
import collections
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import re
from urllib.parse import urlsplit
import opportunity_alerts
import market_corroboration
import verification
import candidate_evidence
import evidence_audit
from asset_identity import key,CHAINS,DEX_CHAINS,canonical
from discovery_adapters import ADAPTERS,ProfileFallback,deduplicate,GECKO
from gate_spot_research import PublicGate
from live_candidate_scan import write_report
from provider_session import Session


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()


class EvidenceFetch:
    """Run-local successful-response cache with explicit age; failed hosts use Session."""
    HOSTS={'api.geckoterminal.com','api.dexscreener.com','api.gopluslabs.io','api.honeypot.is','api.gateio.ws'}
    def __init__(self,session):self.session=session;self.cache={};self.events=[]
    def __call__(self,url):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in self.HOSTS or parsed.username or parsed.password:raise ValueError('Unsupported public provider URL')
        now=dt.datetime.now(dt.timezone.utc).timestamp()
        # Cache only identical resources briefly; never use cached books as live.
        ttl=0 if '/order_book' in parsed.path else 20
        cached=self.cache.get(url)
        if cached and 0<=now-cached['at']<=ttl:
            self.events.append(dict(url=url,event='CACHE_HIT',original_retrieved_at=cached['retrieved_at']))
            return cached['raw']
        try:raw=self.session.get(url)
        except OSError:
            if self.session.wait_ready(url):raw=self.session.get(url)
            else:raise
        entry=dict(url=url,retrieved_at=utc(),at=now,raw=raw)
        self.cache[url]=entry;self.events.append(dict(url=url,event='RESPONSE',retrieved_at=entry['retrieved_at']))
        return raw


def prior_exclusions(paths):
    exclusions={};sources=[]
    for source in paths:
        path=pathlib.Path(source)
        if not path.exists():raise ValueError('Required prior exclusion evidence missing: '+str(path))
        with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as stream:report=json.load(stream)
        sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for item in report.get('candidates',[])+report.get('previous_rejections',[]):
            global_rejection=(item.get('global_assessment') or {}).get('category')=='REJECTED'
            hard_rejection=item.get('decision') in ('DISCARD','REJECT','REJECTED') or global_rejection
            retained_rejection=item.get('decision') is None and 'decision_reason' in item
            adverse=[name+': '+entry.get('reason','Adverse evidence') for name,entry in (item.get('verification') or {}).items()
                if name in opportunity_alerts.CRITICAL and isinstance(entry,dict) and entry.get('status') in ('FAIL','CONFLICTING')]
            if not (hard_rejection or retained_rejection or adverse):continue
            network=item.get('network') or item.get('key','').split(':')[0]
            try:identity=key(network,item['token_address'])
            except (ValueError,KeyError):continue
            exclusions.setdefault(identity,[]).append(dict(source_file=str(path),pool=item.get('address') or item.get('key'),reason=('Unresolved historical adverse evidence: '+'; '.join(adverse)) if adverse and not hard_rejection else item.get('decision_reason') or (item.get('global_assessment') or {}).get('reason','Retained prior exclusion'),observed_at=item.get('observed_at',report.get('started_at','UNKNOWN'))))
    return exclusions,sources


def activity(item,config):
    try:
        total,components=opportunity_alerts.score(item,config)
        return dict(status='UNCALIBRATED_HEURISTIC',score=total,components=components,gate_listing_bonus=0,
            calibration='UNKNOWN: no labelled forward-test dataset or calibrated return model in this increment; not a probability of profit')
    except (ValueError,KeyError,TypeError):return dict(status='UNKNOWN',score=None,components={},gate_listing_bonus=0,calibration='Unavailable market inputs; no positive score inferred')


def assessment_fields(item):
    report=item.get('verification') or {};fields={}
    market_status='OBSERVED' if opportunity_alerts.fresh(item.get('observed_at'),dt.datetime.now(dt.timezone.utc).timestamp(),300) else 'STALE'
    for name,field in [('liquidity','liquidity'),('volume_24h','volume')]:
        value=item.get(field);fields[name]=dict(status=market_status if value is not None else 'UNKNOWN',value=value,scope='Provider-reported pool observation; not audited depth/genuine volume')
    fields['volume_quality']=dict(status='UNKNOWN',reason='Cross-provider identity/price corroboration and flow ratios flag anomalies, but do not prove genuine volume, unique traders or adoption')
    for name,field in [('market_cap','market_cap_estimate_usd'),('fdv','fdv_estimate_usd')]:
        value=item.get(field);fields[name]=dict(status='ESTIMATE' if value is not None else 'UNKNOWN',value=value,scope='Provider estimate; supply/circulation methodology not independently reconciled')
    for field,check in [('circulating_supply','tokenomics'),('holder_concentration','holders'),('token_permissions','contract_security')]:
        entry=report.get(check,{})
        fields[field]=dict(status='LIMITED' if entry.get('status')=='LIMITED' else entry.get('status','UNKNOWN'),reason=entry.get('reason','Independent verification unavailable'))
    for field in ('developer_history','lp_withdrawal_risk','unlocks','credible_adoption'):
        fields[field]=dict(status='UNKNOWN',reason='Not independently established in this increment; never inferred from ticker, profile, volume or a missing schedule')
    return fields


def global_category(item,watch,exclusions):
    if exclusions:return 'REJECTED','Unresolved previously excluded exact token/pool evidence retained'
    if watch['classification']=='REJECT':return 'REJECTED','; '.join(watch['reasons'])
    if watch['classification']=='VERIFIED BUY' and watch.get('eligible_for_buy') is True and evidence_audit.audit(item)['trade_ready'] is True:return 'VERIFIED BUY','Original independent mandatory gates passed'
    if watch['classification'] in ('HIGH-PRIORITY WATCH','ENTRY WATCH'):return 'WATCH',watch['classification']+' — NOT A VERIFIED BUY SIGNAL'
    if item.get('market_corroboration',{}).get('status')=='CONFLICTING':return 'HIGH RISK','Independent pool/contract/market evidence conflicts; no identity or price clearance'
    try:
        liq=opportunity_alerts.number(item.get('liquidity'));vol=opportunity_alerts.number(item.get('volume'));share=opportunity_alerts.number(item.get('buy_share'))
        if liq<=0 or vol/liq>10 or not .2<=share<=.8:return 'HIGH RISK','Thin/abnormal or one-sided market flow; wash trading/manipulation not ruled out'
        if not opportunity_alerts.fresh(item.get('observed_at'),dt.datetime.now(dt.timezone.utc).timestamp(),300):return 'HIGH RISK','Market observations stale/future or unavailable'
        if item.get('market_corroboration',{}).get('status')=='CORROBORATED' and liq>=50000 and vol>=100000:
            return 'EARLY DISCOVERY','Fresh independent market corroboration; security/advanced evidence still incomplete. Pool age does not prove early token launch'
    except (ValueError,TypeError):pass
    return 'HIGH RISK','Insufficient independently corroborated evidence; unverified discovery lead only'


def fallback_confirmation(item,fetch):
    """Reverse corroboration when discovery itself came from DEX Screener."""
    try:
        url=f'{GECKO}/networks/{item["network"]}/pools/{item["address"]}?include=base_token,quote_token'
        raw=fetch(url)
        from discovery_adapters import gecko_rows
        rows,_=gecko_rows(item['network'],{'data':[raw['data']],'included':raw.get('included',[])},url,'fallback_confirmation')
        if len(rows)!=1 or rows[0]['asset_key']!=item['asset_key']:raise ValueError('Identity mismatch')
        first=opportunity_alerts.number(item['base_token_price_usd']);second=opportunity_alerts.number(rows[0]['base_token_price_usd'])
        if min(first,second)<=0:raise ValueError('Invalid price')
        return dict(status='CORROBORATED' if abs(first/second-1)<=.05 else 'CONFLICTING',reason='Independent Gecko pool/token/price comparison',source=url,observed_at=utc(),raw=raw)
    except (ValueError,KeyError,TypeError,OSError):return dict(status='UNKNOWN',reason='Independent confirmation of profile-fallback lead unavailable')


def preview(item):
    analysis=item['global_assessment'];gate=item['gate_spot'];score=item['prelisting_score']
    display=lambda value: 'UNKNOWN' if value is None else str(value)
    return '\n'.join(['CRYPTO-ORACLE X100 — '+analysis['category'],'NOT A VERIFIED BUY SIGNAL' if analysis['category']!='VERIFIED BUY' else 'Original mandatory evidence gates required',
        'Chain: '+CHAINS[item['network']],'Contract: '+item['token_address'],
        'Observed price (indicative USD): '+str(item.get('base_token_price_usd') if item.get('base_token_price_usd') is not None else 'UNKNOWN'),
        'Liquidity USD: '+display(item.get('liquidity'))+'; 24h volume USD: '+display(item.get('volume')),
        'Pool age hours: '+display(item.get('age_hours'))+'; token launch/pre-listing status UNKNOWN',
        'Retrieved UTC: '+item['observed_at']+'; provider market timestamp UNKNOWN',
        'Source: '+item['source_url'],'Independent evidence: '+item['market_corroboration']['status'],
        'Research score: '+display(score['score'])+' (UNCALIBRATED; not profit probability)',
        'Gate Spot: '+gate['status']+' — '+gate['reason'],
        'Decision/risk: '+analysis['reason'],
        'UNKNOWN: developer history, complete permissions/holders/LP withdrawal/unlocks/adoption and personal execution risk',
        'Next review: '+'; '.join(item.get('mandatory_blockers',[])[:3])+'; complete list in the evidence report',
        'Research: '+item['url'],'Manual research only. Orders, signatures and automatic trading DISABLED.'])


def run(limit=8,output='global_discovery_report.json.gz',previous=None):
    if not 4<=limit<=16:raise ValueError('Assessment bound must be 4–16 (four-chain coverage)')
    history=['validation/targeted-candidates-2026-10-21.json.gz','validation/larger-scan-2026-10-21.json.gz','validation/live-candidates-2026-10-21.json']
    if previous:history.append(str(previous))
    excluded,exclusion_sources=prior_exclusions(history)
    config=opportunity_alerts.policy()
    result=dict(started_at=utc(),scope='One new/trending page per chain; bounded unique-token assessment, not exhaustive global coverage',
        automated_trading_enabled=False,orders_allowed=False,telegram_transmission=False,verified_buy_signals=[],prior_exclusion_sources=exclusion_sources,
        discovery=[],discovery_failures=[],candidates=[],unassessed_asset_keys=[],run_state='IN_PROGRESS')
    with Session(max_requests=450,max_seconds=600) as session:
        fetch=EvidenceFetch(session);rows=[];fallback=ProfileFallback(fetch)
        for adapter in ADAPTERS:
            adapter_result=adapter(fetch).discover();rows+=adapter_result['rows'];result['discovery']+=adapter_result['observations'];result['discovery_failures']+=adapter_result['failures']
            if not adapter_result['rows']:
                extra=fallback.discover(adapter.network);rows+=extra['rows'];result['discovery']+=extra['observations'];result['discovery_failures']+=extra['failures']
        assets=deduplicate(rows)
        ranked={network:[] for network in CHAINS}
        for asset in assets:
            item=max(asset['pools'],key=lambda x:x.get('liquidity') if x.get('liquidity') is not None else -1)
            ranked[asset['network']].append((activity(item,config)['score'],asset,item))
        for queue in ranked.values():queue.sort(key=lambda x:x[0] if x[0] is not None else -1,reverse=True)
        chosen=[]
        while len(chosen)<limit:
            progressed=False
            for network in CHAINS:
                if ranked[network]:chosen.append(ranked[network].pop(0));progressed=True
                if len(chosen)>=limit:break
            if not progressed:break
        chosen_keys={x[1]['asset_key'] for x in chosen};result['unassessed_asset_keys']=[a['asset_key'] for a in assets if a['asset_key'] not in chosen_keys]
        gate=PublicGate(fetch)
        try:result['gate_catalog']=gate.catalog()
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:result['gate_catalog']=dict(status='UNKNOWN',error_type=type(exc).__name__,http_status=getattr(exc,'code',None))
        if previous:
            with (gzip.open(previous,'rt') if str(previous).endswith('.gz') else open(previous)) as stream:prior=json.load(stream)
            old_ids={p['id'] for o in prior.get('gate_evidence',[]) if o['url'].endswith('/spot/currency_pairs') for p in o['raw']}
            result['newly_observed_spot_pair_ids']=[p['id'] for p in getattr(gate,'pairs',[]) if p.get('type')=='normal' and p['id'] not in old_ids] if old_ids else None
        else:result['newly_observed_spot_pair_ids']=None
        for _,asset,item in chosen:
            item=dict(item);item['pool_observation_count']=len(asset['pools']);item['market_corroboration']=fallback_confirmation(item,fetch) if item['discovery_mode']=='profile_fallback' else market_corroboration.check(item,fetch)
            item['project_context']=project_context.discovery_only(item,dt.datetime.now(dt.timezone.utc).timestamp())
            item['verification']=verification.collect(item,fetch)
            item['mandatory_blockers']=candidate_evidence.blockers(item)
            item['prelisting_score']=activity(item,config)
            adverse=excluded.get(item['asset_key'],[])
            item['persistent_adverse_reasons']=['Retained prior exclusion: '+a['reason'] for a in adverse]
            watch=opportunity_alerts.classify(item,config)
            category,reason=global_category(item,watch,adverse)
            item['global_assessment']=dict(category=category,reason=reason,watch_subtype=watch['classification'],
                fields=assessment_fields(item),prior_exclusions=adverse,mandatory_blockers=item['mandatory_blockers'],verified_buy_allowed=False)
            if hasattr(gate,'index'):item['gate_spot']=gate.eligibility(asset)
            else:item['gate_spot']=dict(status='UNKNOWN',reason='Public Spot catalog unavailable; global discovery retained')
            item['gate_execution_research']=gate.research(item['gate_spot'],excluded=category in ('HIGH RISK','REJECTED'))
            result['candidates'].append(item);result['gate_evidence']=gate.evidence
            write_report(output,result)
            print('GLOBAL',item['asset_key'],category,'GATE',item['gate_spot']['status'],flush=True)
        # Separate exact-contract reference integration; never added to opportunity counts.
        reference=dict(network='eth',token_address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48')
        reference['asset_key']=key(reference['network'],reference['token_address'])
        eligibility=gate.eligibility(reference) if hasattr(gate,'index') else dict(status='UNKNOWN',reason='Catalog unavailable')
        result['gate_reference_integration']=dict(scope='USDC reference only, not a discovered opportunity or recommendation',identity=reference,
            eligibility=eligibility,research=gate.research(eligibility,excluded=False))
        result['gate_evidence']=gate.evidence;result['provider_session']=session.summary();result['fetch_ledger']=fetch.events
        result['counts']=dict(pool_observations=len(rows),unique_chain_pool_keys=len({(r['network'],r['address']) for r in rows}),
            unique_chain_contracts=len(assets),assessed_unique_tokens=len(chosen),unassessed_unique_tokens=len(result['unassessed_asset_keys']),
            categories=dict(collections.Counter(c['global_assessment']['category'] for c in result['candidates'])),
            gate_spot_eligible=sum(c['gate_spot']['status']=='CONFIRMED_SPOT' for c in result['candidates']),verified_buy=0)
    result['run_state']='COMPLETED';result['finished_at']=utc();write_report(output,result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=8);p.add_argument('--output',default='global_discovery_report.json.gz');p.add_argument('--previous');args=p.parse_args()
    result=run(args.limit,args.output,args.previous)
    target=pathlib.Path(args.output).with_suffix('.previews.txt')
    target.write_text('\n\n---\n\n'.join(preview(c) for c in result['candidates'])+'\n')
    print(json.dumps(result['counts']))

if __name__=='__main__':main()

