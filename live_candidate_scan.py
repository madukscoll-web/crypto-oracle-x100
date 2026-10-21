"""Bounded reproducible live scan; no Telegram messages or persistent state writes.

Discovery raw responses, examined and unexamined pools, provider failures and
per-candidate mandatory blockers are retained. A partial scan is never global
market coverage. Diagnostic quotes use explicit chain-specific stablecoin base-unit probes;
this is not a proposed allocation, executable offer or user order.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import candidate_evidence
import crypto_oracle_scanner as scanner
import evidence_audit
import execution_quotes
import execution_checks
import gas_valuation
import market_corroboration
import onchain
import token_unlocks
import verification


def verification_observation(pool,network,mode):
    import math
    attrs=pool.get('attributes') or {};address=attrs.get('address') or str(pool.get('id','')).removeprefix(network+'_')
    relation=((pool.get('relationships') or {}).get('base_token') or {}).get('data') or {}
    hint=str(relation.get('id') or '').removeprefix(network+'_').lower()
    if not address or not hint:return None
    def measurement(value):
        try:
            result=float(value)
            return result if math.isfinite(result) and result>=0 else None
        except (ValueError,TypeError,OverflowError):return None
    age=None
    try:
        stamp=dt.datetime.fromisoformat(attrs['pool_created_at'].replace('Z','+00:00'))
        if stamp.tzinfo is not None:age=(dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()/3600
    except (KeyError,ValueError,TypeError):pass
    h1=(attrs.get('transactions') or {}).get('h1') or {};buys=measurement(h1.get('buys'));sells=measurement(h1.get('sells'))
    trades=buys+sells if buys is not None and sells is not None else None
    return dict(network=network,address=address,key=network+':'+address,name=attrs.get('name','Unnamed pool'),
                discovery_token_hint=hint,discovery_eligible=False,score=None,score_source='Not market-ranked; verification-only cohort',
                liquidity=measurement(attrs.get('reserve_in_usd')),volume=measurement((attrs.get('volume_usd') or {}).get('h24')),
                buys=buys,sells=sells,trades=trades,buy_share=buys/trades if trades else None,age_hours=age,
                pool_class='NEW POOL' if age is not None and 0<=age<=72 else 'EXISTING POOL' if age is not None and age>72 else 'UNKNOWN',
                flags=['Original discovery filters not met; independently assessed for evidence only'],
                base_token_price_usd=measurement(attrs.get('base_token_price_usd')),observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                change_h1=None,change_h24=None)


def select_candidates(ordered,networks,limit):
    selected=[];seen=set();queues={n:[x for x in ordered if x['network']==n] for n in networks}
    # Round-robin chains, preserving a new-pool sample in each chain, then
    # ranking. A token/pool duplicate cannot consume all assessment slots.
    for n,queue in queues.items():
        new=next((x for x in queue if x['pool_class']=='NEW POOL' and x.get('discovery_eligible') is not False),None)
        if new:queue.remove(new);queue.insert(0,new)
    while len(selected)<limit:
        progressed=False
        for n in networks:
            while queues[n]:
                item=queues[n].pop(0)
                identity=n+':'+(item.get('discovery_token_hint') or item['key'].lower())
                if identity in seen:continue
                seen.add(identity);selected.append(item);progressed=True;break
            if len(selected)>=limit:break
        if not progressed:break
    return selected


def update_counts(result,discovered,qualified):
    rejected=sum(x['decision']=='DISCARD' for x in result['candidates'])
    waiting=sum(x['decision']=='WAIT AND VERIFY' for x in result['candidates'])
    result['counts']=dict(pool_observations=sum(len(x['raw']['data']) for x in result['discovery']),
        discovered_unique_pools=len(discovered),discovery_filtered_out_unique_pools=len(discovered-set(qualified)),
        discovery_qualified_unique_pools=len(qualified),assessed_pools=len(result['candidates']),
        rejected_assessed_pools=rejected,still_unverified_assessed_pools=waiting,
        assessed_discovery_qualified_pools=sum(x.get('discovery_eligible') is not False for x in result['candidates']),
        assessed_verification_only_pools=sum(x.get('discovery_eligible') is False for x in result['candidates']),
        unassessed_qualified_pools=len(set(qualified)-{x.get('key','').lower() for x in result['candidates']}),verified_buy_signals=0,
        still_unverified_discovered_pools=len(discovered)-rejected,
        not_verified_discovered_pools=len(discovered)-rejected)


def coverage(candidates):
    result=dict(pool_identity_corroborated=0,fungible_lp_observed=0,concentrated_pool_identity=0,
                holder_balance_observations=0,ownable_owner_returned=0,source_runtime_matches=0,
                independent_sellability_results=0,two_way_calldata_built=0,encoded_parameter_pairs_matched=0,
                funded_sequential_execution_verified=0)
    safe=set();nfts=set();nft_conflicts=0
    for item in candidates:
        r=item['verification'];chain=(r.get('onchain',{}).get('raw') or {}).get('results') or {}
        lp=(r.get('pool_identity_followup',{}).get('metrics') if r.get('pool_identity_followup',{}).get('status')=='LIMITED' else None) or (chain.get('lp') or {}).get('metrics') or {}
        if lp.get('protocol'):result['pool_identity_corroborated']+=1
        if lp.get('position_type')=='fungible_v2_lp':result['fungible_lp_observed']+=1
        if lp.get('position_type')=='concentrated_nft':result['concentrated_pool_identity']+=1
        if (chain.get('holders') or {}).get('metrics'):result['holder_balance_observations']+=1
        custody=(r.get('custody_followup') or r.get('custody') or {}).get('raw') or {}
        if custody.get('token_authority',{}).get('status')=='LIMITED':result['ownable_owner_returned']+=1
        for row in custody.get('records') or []:
            if row.get('status')=='LIMITED':safe.add((item['network'],row['address']))
        if r.get('contract_source',{}).get('metrics',{}).get('runtime_source_match'):result['source_runtime_matches']+=1
        if r.get('sellability',{}).get('status') in ('LIMITED','FAIL'):result['independent_sellability_results']+=1
        for record in (r.get('nft_custody',{}).get('raw') or {}).get('records') or []:
            if record.get('status')=='LIMITED':nfts.add((item['network'],record['metrics']['position_manager'],record['metrics']['token_id']))
            if record.get('status')=='CONFLICTING':nft_conflicts+=1
        quotes=r.get('kyber',{});legs=quotes.get('raw') or []
        if quotes.get('status')=='LIMITED' and len(legs)==2 and all(x.get('build_response') for x in legs):result['two_way_calldata_built']+=1
        policy=r.get('calldata_policy',{});decoded=(policy.get('raw') or {}).get('legs') or []
        if policy.get('status')=='LIMITED' and len(decoded)==2 and all(x.get('encoded_policy_parameters_match') for x in decoded):result['encoded_parameter_pairs_matched']+=1
        for name in ('kyber_execution','execution_checks'):
            if ((r.get(name,{}).get('raw') or {}).get('sequential') or {}).get('sequential_simulation_succeeded'):
                result['funded_sequential_execution_verified']+=1;break
    result['unique_safe_signer_sets_corroborated']=len(safe)
    result['unique_nft_position_owners_corroborated']=len(nfts)
    result['nft_position_owner_disagreements']=nft_conflicts
    return result


def write_report(path,result):
    import gzip
    target=pathlib.Path(path)
    temporary=target.with_suffix(target.suffix+'.tmp')
    if target.suffix=='.gz':
        with gzip.open(temporary,'wt',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    else:temporary.write_text(json.dumps(result,indent=2)+'\n')
    temporary.replace(target)


def run(networks,limit=3,delay=3,fetch=None,pages=1,session=None,checkpoint=None):
    if not 1<=limit<=20:raise ValueError('limit must be 1–20')
    if not 1<=pages<=3:raise ValueError('pages must be 1–3')
    if fetch is None:
        from provider_session import Session
        with Session(max_requests=1500,max_seconds=1200) as session:
            def fetch_recover(url):
                try:return session.get(url)
                except OSError:
                    if session.wait_ready(url):return session.get(url)
                    raise
            return run(networks,limit,delay,fetch_recover,pages,session,checkpoint)
    registry=json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())
    result=dict(started_at=dt.datetime.now(dt.timezone.utc).isoformat(),requested_networks=list(networks),
                scope=f'First {pages} pages each of new_pools and trending_pools; chain/token-diversified bounded enrichment; not exhaustive',
                requested_pages=pages,run_state='IN_PROGRESS',
                discovery=[],discovery_failures=[],screened_out=[],candidates=[],verified_buy_signals=[],automated_trading_enabled=False)
    result['integration_requirements']=dict(
        public_api_checks=['chain/pool identity','RPC owner and holder balances','source/runtime and ABI matching','diagnostic calldata encoding/parameter checks'],
        credential_dependent=dict(tokenomist_key_configured=bool(os.environ.get('TOKENOMIST_API_KEY')),tokenomist_reviewed_bindings=len(registry.get('provider_bindings',{})),zerox_key_configured=bool(os.environ.get('ZEROX_API_KEY'))),
        account_state_dependent=['Funded public taker and existing allowances for non-overridden execution simulation; no signing or broadcast'],
        excluded_transaction_checks=['Actual settlement, realized fees/proceeds and trading performance require transactions and are not performed'])
    qualified={}
    discovered=set();pool_records={}
    for network in networks:
        for mode in ('new_pools','trending_pools'):
            for page in range(1,pages+1):
                url=f'{scanner.API}/networks/{network}/{mode}?page={page}'
                try:
                    raw=fetch(url);rows=raw['data']
                    if not isinstance(rows,list):raise ValueError('Invalid discovery list')
                    result['discovery'].append(dict(network=network,mode=mode,page=page,url=url,raw=raw,observed_at=dt.datetime.now(dt.timezone.utc).isoformat()))
                    for pool in rows:
                        attrs=pool.get('attributes') or {}
                        raw_address=attrs.get('address') or str(pool.get('id','')).removeprefix(network+'_')
                        if not raw_address:continue
                        key=(network+':'+raw_address).lower();discovered.add(key)
                        pool_records[key]=(pool,network,mode)
                        item=scanner.inspect(pool,network,mode)
                        if item:
                            relationship=((pool.get('relationships') or {}).get('base_token') or {}).get('data') or {}
                            item['discovery_token_hint']=str(relationship.get('id') or '').removeprefix(network+'_').lower()
                            qualified[key]=item
                        else:result['screened_out'].append(dict(network=network,pool_key=key,mode=mode,page=page,reason='Did not meet existing discovery filters in this observation; not a security rejection'))
                    if not rows:break
                except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError) as exc:
                    result['discovery_failures'].append(dict(network=network,mode=mode,page=page,url=url,error_type=type(exc).__name__,http_status=getattr(exc,'code',None)))
                if delay:time.sleep(delay)
    ordered=sorted(qualified.values(),key=lambda x:(x['score'],x['liquidity']),reverse=True)
    verification_only=[verification_observation(*record) for key,record in pool_records.items() if key not in qualified]
    verification_only=[x for x in verification_only if x is not None]
    selected=select_candidates(ordered+verification_only,networks,limit)
    result['qualified_discovery_count']=len(ordered)
    result['not_enriched_pool_keys']=[x['key'] for x in ordered if x not in selected]
    native={}
    for item in selected:
        scanner.enrich(item,fetch=fetch,delay=0)
        hint=item.get('discovery_token_hint','')
        if item.get('token_address')=='UNVERIFIED':
            try:
                item['token_address']=onchain.address(hint)
                item['token_identity_status']='UNVERIFIED (discovery hint only; fresh pool binding unavailable)'
            except ValueError:
                pass
        report=verification.collect(item,fetch)
        info=((report.get('contract_security',{}).get('raw') or {}).get('result') or {}).get(item['token_address'].lower(),{})
        if info:
            item['risk_category'],item['risk_reasons']=scanner.risk_gate(info)
        report['onchain']=onchain.collect(item,info.get('holders') or [],lock_descriptors=registry['lp_locks'].get(item['network']+':'+item['address'].lower(),[]))
        report['unlocks']=token_unlocks.collect(item,registry)
        if item['network'] in native and (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(native[item['network']]['observed_at'])).total_seconds()>120:
            del native[item['network']]
        if item['network'] not in native:native[item['network']]=gas_valuation.collect(item['network'],fetch)
        report['gas_valuation']=native[item['network']]
        price=native[item['network']].get('metrics',{}).get('native_usd')
        report['execution']=execution_quotes.collect(item,os.environ,native_price=price)
        report['execution_checks']=execution_checks.collect(item,report['execution'],os.environ.get('ORACLE_TAKER_ADDRESS',''))
        references={
            'eth':('0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48','100000000'),
            'base':('0x833589fcd6edb6e08f4c7c32d4f71b54bda02913','100000000'),
            'bsc':('0x55d398326f99059ff775485246999027b3197955','100000000000000000000')}
        reference=None
        if item['network'] in references:
            funding,amount=references[item['network']]
            reference=dict(funding_token=funding,amount_base_units=amount,build_calldata=True,
                           diagnostic_sender='0x0000000000000000000000000000000000000001',
                           purpose='Explicit diagnostic base-unit input and reserved sender fixture; no wallet ownership, balance or user order asserted')
        candidate_evidence.augment(item,report,fetch,os.environ,native_price=price,reference_order=reference)
        item['verification']=report
        item['market_corroboration']=market_corroboration.check(item,fetch)
        item['mandatory_blockers']=candidate_evidence.blockers(item)
        if item.get('discovery_eligible') is False:item['mandatory_blockers'].insert(0,'Verification-only cohort: original market discovery filters failed; ineligible for BUY')
        item['decision'],item['decision_reason']=scanner.decision_summary(item)
        item['audit']=evidence_audit.audit(item)
        result['candidates'].append(item)
        update_counts(result,discovered,qualified)
        if checkpoint:checkpoint(result)
        print(item['network'],item['token_address'],item['decision'],'mandatory_blockers='+str(len(item['mandatory_blockers'])),flush=True)
        print(json.dumps(dict(candidate=item['key'],contract=item['token_address'],mandatory_blockers=item['mandatory_blockers'])),flush=True)
    result['verification_coverage']=coverage(result['candidates'])
    result['run_state']='COMPLETED'
    update_counts(result,discovered,qualified)
    result['provider_session']=session.summary() if session is not None else None
    result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    result['assessed_candidate_count']=len(result['candidates'])
    result['conclusion']=('NO VERIFIED BUY: all assessed candidates have failed or unverified mandatory evidence; unexamined pools and failed feeds remain unassessed' if result['candidates'] else 'NO VERIFIED BUY: no candidates independently assessed; filters and provider failures do not establish market-wide absence')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--networks',default='eth,base,bsc')
    parser.add_argument('--limit',type=int,default=3)
    parser.add_argument('--pages',type=int,default=1)
    parser.add_argument('--output',default='live_candidate_scan.json')
    args=parser.parse_args()
    if not 1<=args.limit<=20:parser.error('limit must be 1–20')
    if not 1<=args.pages<=3:parser.error('pages must be 1–3')
    networks=tuple(x.strip() for x in args.networks.split(',') if x.strip())
    if not networks or any(x not in scanner.DEFAULT_NETWORKS for x in networks):parser.error('Unsupported network')
    result=run(networks,args.limit,pages=args.pages,checkpoint=lambda value:write_report(args.output,value))
    write_report(args.output,result)
    print(json.dumps({k:result[k] for k in ('qualified_discovery_count','assessed_candidate_count','conclusion')}))

if __name__=='__main__':main()
