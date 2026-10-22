"""Read-only reassessment of an existing scan and its qualified backlog.

No new discovery, signing, broadcast, notifications or scanner-state changes.
Historical adverse evidence is retained explicitly even if a provider disappears.
"""
import argparse
import copy
import datetime as dt
import gzip
import json
import pathlib
import candidate_evidence
import crypto_oracle_scanner as scanner
import evidence_audit
from live_candidate_scan import assess_candidate,coverage,write_report
from provider_session import Session


def targets(previous):
    """Backlog of discovery-qualified pools first, then previous WAIT entries."""
    assessed={x['key'].lower() for x in previous['candidates']}
    qualified={}
    for feed in previous['discovery']:
        for pool in feed['raw']['data']:
            item=scanner.inspect(pool,feed['network'],feed['mode'])
            if item:
                relation=((pool.get('relationships') or {}).get('base_token') or {}).get('data') or {}
                item['discovery_token_hint']=str(relation.get('id') or '').removeprefix(feed['network']+'_').lower()
                qualified[item['key'].lower()]=item
    # Honor the historical qualified cohort. Recomputing age/rank later must not
    # silently drop a saved candidate from this targeted evidence review.
    historical=set(previous.get('not_enriched_pool_keys',[]))
    for key in historical:
        if key.lower() not in qualified:
            for feed in previous['discovery']:
                for pool in feed['raw']['data']:
                    from live_candidate_scan import verification_observation
                    item=verification_observation(pool,feed['network'],feed['mode'])
                    if item and item['key'].lower()==key.lower():
                        item['historical_discovery_qualified']=True
                        qualified[key.lower()]=item
    backlog=[copy.deepcopy(x) for key,x in qualified.items() if key not in assessed and (not historical or key in {k.lower() for k in historical})]
    waiting=[copy.deepcopy(x) for x in previous['candidates'] if x['decision']=='WAIT AND VERIFY']
    for item in backlog:item['review_cohort']='previously_unassessed_qualified'
    for item in waiting:item['review_cohort']='previously_unverified'
    return backlog+waiting


def preserve_adverse(item,previous):
    if not previous:return
    item['previous_decision']=previous['decision']
    adverse=[]
    old=previous.get('verification',{})
    for name,entry in old.items():
        if isinstance(entry,dict) and entry.get('status') in ('FAIL','CONFLICTING'):
            adverse.append(dict(check=name,evidence=entry))
    item['unresolved_prior_adverse_evidence']=adverse
    if adverse and item['decision']!='DISCARD':
        item['decision']='WAIT AND VERIFY'
        item['decision_reason']='Prior failed/conflicting evidence remains unresolved; see retained timestamped observations'
        item['mandatory_blockers'].extend('Unresolved prior '+x['check']+': '+x['evidence'].get('reason','') for x in adverse)
    item['audit']=evidence_audit.audit(item)


def run(previous,output):
    selected=targets(previous)
    registry=json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())
    result=dict(started_at=dt.datetime.now(dt.timezone.utc).isoformat(),scope='Saved discovery-qualified backlog first, then all previous unverified candidates; no new discovery',
                source_scan_started_at=previous['started_at'],candidates=[],verified_buy_signals=[],automated_trading_enabled=False,
                target_count=len(selected),previous_rejections=[dict(key=x['key'],token_address=x['token_address'],decision_reason=x['decision_reason']) for x in previous['candidates'] if x['decision']=='DISCARD'],run_state='IN_PROGRESS')
    old={x['key'].lower():x for x in previous['candidates']}
    with Session(max_requests=4000,max_seconds=1800) as session:
        # Carry forward known inaccessible hosts, rather than re-probing them.
        for host,status in (previous.get('provider_session') or {}).get('denied_hosts',{}).items():session.denied[host]=status
        result['inherited_denied_hosts']=dict(session.denied)
        def fetch(url):
            try:return session.get(url)
            except OSError:
                if session.wait_ready(url):return session.get(url)
                raise
        native={}
        for item in selected:
            prior=old.get(item['key'].lower())
            # Old verification objects are never reused as fresh observations.
            for key in ('verification','audit','mandatory_blockers','market_corroboration'):item.pop(key,None)
            assess_candidate(item,fetch,registry,native)
            preserve_adverse(item,prior)
            item['buy_consideration']='EXCLUDED: mandatory evidence incomplete or adverse'
            result['candidates'].append(item)
            result['provider_session']=session.summary()
            write_report(output,result)
            print(item['review_cohort'],item['network'],item['token_address'],item['decision'],flush=True)
        result['provider_session']=session.summary()
    result['verification_coverage']=coverage(result['candidates'])
    result['counts']=dict(assessed=len(result['candidates']),qualified_backlog_assessed=sum(x['review_cohort']=='previously_unassessed_qualified' for x in result['candidates']),previously_unverified_assessed=sum(x['review_cohort']=='previously_unverified' for x in result['candidates']),rejected=sum(x['decision']=='DISCARD' for x in result['candidates']),still_unverified=sum(x['decision']=='WAIT AND VERIFY' for x in result['candidates']),verified_buy=0)
    result['run_state']='COMPLETED';result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    write_report(output,result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    opener=gzip.open if args.input.endswith('.gz') else open
    with opener(args.input,'rt') as f:previous=json.load(f)
    print(json.dumps(run(previous,args.output)['counts']))

if __name__=='__main__':main()
