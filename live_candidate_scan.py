"""Bounded reproducible live scan; no Telegram messages or persistent state writes.

Discovery raw responses, examined and unexamined pools, provider failures and
per-candidate mandatory blockers are retained. A partial scan is never global
market coverage. Diagnostic quotes use an explicit USDC probe only on Ethereum;
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


def run(networks,limit=3,delay=3,fetch=None):
    if not 1<=limit<=10:raise ValueError("limit must be 1–10")
    if fetch is None:
        def fetch(url):
            for attempt in range(2):
                try:return scanner.fetch_json(url)
                except urllib.error.HTTPError as exc:
                    if attempt or exc.code not in (500,502,503,504):raise
                except OSError:
                    if attempt:raise
                time.sleep(2)
    registry=json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())
    result=dict(started_at=dt.datetime.now(dt.timezone.utc).isoformat(),requested_networks=list(networks),
                scope='First page each of new_pools and trending_pools; bounded ranked enrichment; not exhaustive',
                discovery=[],discovery_failures=[],screened_out=[],candidates=[],verified_buy_signals=[],automated_trading_enabled=False)
    qualified={}
    for network in networks:
        for mode in ('new_pools','trending_pools'):
            url=f'{scanner.API}/networks/{network}/{mode}?page=1'
            try:
                raw=fetch(url);rows=raw['data']
                if not isinstance(rows,list):raise ValueError('Invalid discovery list')
                result['discovery'].append(dict(network=network,mode=mode,url=url,raw=raw,observed_at=dt.datetime.now(dt.timezone.utc).isoformat()))
                for pool in rows:
                    item=scanner.inspect(pool,network,mode)
                    if item:qualified[item['key']]=item
                    else:result['screened_out'].append(dict(network=network,pool_id=pool.get('id'),mode=mode,reason='Did not meet existing age/liquidity/volume/transaction discovery filters; not independently assessed'))
            except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError) as exc:
                result['discovery_failures'].append(dict(network=network,mode=mode,url=url,error_type=type(exc).__name__))
            if delay:time.sleep(delay)
    ordered=sorted(qualified.values(),key=lambda x:(x['score'],x['liquidity']),reverse=True)
    # Preserve a new-pool assessment where qualifying new pools exist.
    new=[x for x in ordered if x['pool_class']=='NEW POOL']
    selected=([new[0]] if new else [])
    for network in networks:
        representative=next((x for x in ordered if x['network']==network and x not in selected),None)
        if representative and len(selected)<limit:selected.append(representative)
    selected+= [x for x in ordered if x not in selected][:max(0,limit-len(selected))]
    result['qualified_discovery_count']=len(ordered)
    result['not_enriched_pool_keys']=[x['key'] for x in ordered if x not in selected]
    native={}
    for item in selected:
        scanner.enrich(item)
        report=verification.collect(item,fetch)
        info=((report.get('contract_security',{}).get('raw') or {}).get('result') or {}).get(item['token_address'].lower(),{})
        report['onchain']=onchain.collect(item,info.get('holders') or [],lock_descriptors=registry['lp_locks'].get(item['network']+':'+item['address'].lower(),[]))
        report['unlocks']=token_unlocks.collect(item,registry)
        if item['network'] not in native:native[item['network']]=gas_valuation.collect(item['network'],fetch)
        report['gas_valuation']=native[item['network']]
        price=native[item['network']].get('metrics',{}).get('native_usd')
        report['execution']=execution_quotes.collect(item,os.environ,native_price=price)
        report['execution_checks']=execution_checks.collect(item,report['execution'],os.environ.get('ORACLE_TAKER_ADDRESS',''))
        reference=None
        if item['network']=='eth':reference=dict(funding_token='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',amount_base_units='100000000',purpose='Explicit diagnostic 100000000 USDC base-unit route probe, not a user order or recommended allocation')
        candidate_evidence.augment(item,report,fetch,os.environ,native_price=price,reference_order=reference)
        item['verification']=report
        item['market_corroboration']=market_corroboration.check(item,fetch)
        item['mandatory_blockers']=candidate_evidence.blockers(item)
        item['decision'],item['decision_reason']=scanner.decision_summary(item)
        item['audit']=evidence_audit.audit(item)
        result['candidates'].append(item)
        print(item['network'],item['token_address'],item['decision'],'mandatory_blockers='+str(len(item['mandatory_blockers'])),flush=True)
        print(json.dumps(dict(candidate=item['key'],contract=item['token_address'],mandatory_blockers=item['mandatory_blockers'])),flush=True)
    result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    result['assessed_candidate_count']=len(result['candidates'])
    result['conclusion']=('NO VERIFIED BUY: all assessed candidates have failed or unverified mandatory evidence; unexamined pools and failed feeds remain unassessed' if result['candidates'] else 'NO VERIFIED BUY: no candidates independently assessed; filters and provider failures do not establish market-wide absence')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--networks',default='eth,base,bsc')
    parser.add_argument('--limit',type=int,default=3)
    parser.add_argument('--output',default='live_candidate_scan.json')
    args=parser.parse_args()
    if not 1<=args.limit<=10:parser.error('limit must be 1–10')
    networks=tuple(x.strip() for x in args.networks.split(',') if x.strip())
    if not networks or any(x not in scanner.DEFAULT_NETWORKS for x in networks):parser.error('Unsupported network')
    result=run(networks,args.limit)
    pathlib.Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('qualified_discovery_count','assessed_candidate_count','conclusion')}))

if __name__=='__main__':main()
