import copy
import datetime as dt
import unittest
from unittest.mock import patch
from asset_identity import key,canonical,pool_address
from discovery_adapters import gecko_rows,deduplicate,EthereumDiscovery
import global_discovery as global_engine
import market_corroboration

TOKEN='0x'+'a'*40
POOL='0x'+'b'*40
SOL='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
NOW=1800000000


def pool_payload(network='eth',token=TOKEN,address=POOL):
    identity=network+'_'+token
    return {'data':[{'id':network+'_'+address,'attributes':{'address':address,'name':'Fixture / quote',
        'pool_created_at':dt.datetime.fromtimestamp(NOW-3600,dt.timezone.utc).isoformat(),
        'base_token_price_usd':'0.05','reserve_in_usd':'350000','volume_usd':{'h24':'800000'},
        'transactions':{'h1':{'buys':120,'sells':100}},'price_change_percentage':{'h1':'4','h24':'12'}},
        'relationships':{'base_token':{'data':{'id':identity}}}}],
        'included':[{'id':identity,'type':'token','attributes':{'address':token,'symbol':'SAME'}}]}

class IdentityTests(unittest.TestCase):
    def test_evm_case_normalizes_but_chain_and_native_wrapped_do_not_merge(self):
        self.assertEqual(key('eth',TOKEN),key('eth','0x'+TOKEN[2:].upper()))
        self.assertNotEqual(key('eth',TOKEN),key('base',TOKEN))
        with self.assertRaises(ValueError):key('eth','')
        with self.assertRaises(ValueError):key('eth','0x'+'0'*40)
    def test_solana_case_sensitive_exact_32_byte_shape(self):
        other=SOL.replace('j','J',1)
        self.assertNotEqual(key('solana',SOL),key('solana',other))
        for bad in ('0x'+'a'*40,'I'*44,SOL+'1',' '+SOL):
            with self.assertRaises(ValueError):canonical('solana',bad)
    def test_pool_hash_not_a_fungible_token_address(self):
        self.assertEqual(pool_address('eth','0x'+'1'*64),'0x'+'1'*64)
        with self.assertRaises(ValueError):key('eth','0x'+'1'*64)
    def test_dedup_by_chain_contract_not_symbol_and_no_double_counting(self):
        raw=pool_payload();rows,_=gecko_rows('eth',raw,'https://provider','new_pools',dt.datetime.fromtimestamp(NOW,dt.timezone.utc).isoformat())
        same=copy.deepcopy(rows[0]);same['network']='base'
        assets=deduplicate(rows+rows+[same])
        self.assertEqual(len(assets),2);self.assertEqual(len(assets[0]['pools']),2)
        self.assertEqual(assets[0]['pools'][0]['liquidity'],350000)
    def test_spoofed_include_relation_and_network_are_not_admitted(self):
        for field in ('include','network'):
            raw=pool_payload()
            if field=='include':raw['included'][0]['attributes']['address']='0x'+'c'*40
            else:raw['data'][0]['id']='base_'+POOL
            rows,invalid=gecko_rows('eth',raw,'https://provider','new_pools')
            self.assertEqual(rows,[]);self.assertEqual(len(invalid),1)
    def test_missing_metrics_remain_unknown_not_zero(self):
        raw=pool_payload();del raw['data'][0]['attributes']['reserve_in_usd']
        rows,_=gecko_rows('eth',raw,'https://provider','new_pools')
        self.assertIsNone(rows[0]['liquidity']);self.assertIsNone(rows[0]['market_cap_estimate_usd'])
    def test_unavailable_provider_produces_coverage_failure_not_empty_market_claim(self):
        result=EthereumDiscovery(lambda url:(_ for _ in ()).throw(OSError('fixture'))).discover()
        self.assertEqual(len(result['failures']),2);self.assertEqual(result['rows'],[])
    def test_solana_independent_confirmation_is_case_sensitive(self):
        item=dict(network='solana',address=SOL,token_address=SOL,base_token_price_usd=1)
        response={'pairs':[{'chainId':'solana','pairAddress':SOL,'baseToken':{'address':SOL.replace('j','J',1)},'priceUsd':'1'}]}
        self.assertNotEqual(market_corroboration.check(item,lambda url:response)['status'],'CORROBORATED')

class CategoryTests(unittest.TestCase):
    def test_no_gate_listing_requirement_or_bonus_in_global_score(self):
        from test_opportunity_alerts import candidate
        item=candidate();score=global_engine.activity(item,__import__('opportunity_alerts').policy())
        self.assertEqual(score['gate_listing_bonus'],0);self.assertEqual(score['status'],'UNCALIBRATED_HEURISTIC')
        watch={'classification':'HIGH-PRIORITY WATCH'}
        item['gate_spot']={'status':'UNKNOWN'}
        self.assertEqual(global_engine.global_category(item,watch,[])[0],'WATCH')
        item['gate_spot']={'status':'CONFIRMED_SPOT'}
        self.assertEqual(global_engine.global_category(item,watch,[])[0],'WATCH')
    def test_prior_exclusion_wins_over_watch_or_forged_verified_label(self):
        for label in ('HIGH-PRIORITY WATCH','VERIFIED BUY'):
            self.assertEqual(global_engine.global_category({},dict(classification=label,eligible_for_buy=True),[{'reason':'Prior adverse report'}])[0],'REJECTED')
    def test_forged_verified_label_cannot_bypass_existing_audit(self):
        item={'market_corroboration':{'status':'UNKNOWN'}}
        self.assertNotEqual(global_engine.global_category(item,dict(classification='VERIFIED BUY',eligible_for_buy=True),[])[0],'VERIFIED BUY')
    def test_missing_inputs_produce_unknown_score_and_unavailable_research_fields(self):
        result=global_engine.activity({},__import__('opportunity_alerts').policy())
        self.assertIsNone(result['score']);fields=global_engine.assessment_fields({})
        for name in ('developer_history','lp_withdrawal_risk','unlocks','credible_adoption','volume_quality'):
            self.assertEqual(fields[name]['status'],'UNKNOWN')
    def test_read_client_rejects_private_host(self):
        with self.assertRaises(ValueError):global_engine.EvidenceFetch(None)('http://169.254.169.254/latest/meta-data')

if __name__=='__main__':unittest.main()

class GlobalIntegrationTests(unittest.TestCase):
    def test_gate_outage_never_filters_global_universe_or_grants_buy(self):
        import tempfile
        import pathlib
        import urllib.error
        class Fetch:
            def __init__(self,session):self.events=[]
            def __call__(self,url):
                if 'api.gateio.ws' in url:raise urllib.error.HTTPError(url,403,'fixture denied',None,None)
                if '/networks/' in url and '_pools?' in url:
                    network=url.split('/networks/')[1].split('/')[0]
                    token=SOL if network=='solana' else TOKEN
                    address=SOL if network=='solana' else POOL
                    result=pool_payload(network,token,address)
                    result['data'][0]['attributes']['pool_created_at']=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1)).isoformat()
                    return result
                raise OSError('fixture unknown resource')
        with tempfile.TemporaryDirectory() as folder,patch.object(global_engine,'EvidenceFetch',Fetch),patch.object(global_engine,'prior_exclusions',return_value=({},[])),patch.object(global_engine.verification,'collect',return_value={}),patch.object(global_engine.market_corroboration,'check',side_effect=lambda item,fetch:{'status':'CORROBORATED','observed_at':dt.datetime.now(dt.timezone.utc).isoformat()}):
            report=global_engine.run(4,str(pathlib.Path(folder)/'report.json.gz'))
        self.assertEqual(report['counts']['unique_chain_contracts'],4)
        self.assertEqual(report['counts']['assessed_unique_tokens'],4)
        self.assertEqual({x['network'] for x in report['candidates']},{'solana','eth','base','bsc'})
        self.assertTrue(all(x['gate_spot']['status']=='UNKNOWN' for x in report['candidates']))
        self.assertTrue(all(x['global_assessment']['category']=='EARLY DISCOVERY' for x in report['candidates']))
        self.assertEqual(report['counts']['verified_buy'],0);self.assertFalse(report['orders_allowed'])

class PriorExclusionTests(unittest.TestCase):
    def test_earliest_committed_honeypot_exclusion_is_retained(self):
        excluded,_=global_engine.prior_exclusions(['validation/live-candidates-2026-10-21.json'])
        self.assertIn(key('bsc','0x2c3a8ee94ddd97244a93bc48298f97d2c412f7db'),excluded)
    def test_previous_global_rejection_is_retained_without_price_refresh(self):
        import json,tempfile,pathlib
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'previous.json'
            path.write_text(json.dumps({'candidates':[dict(network='eth',token_address=TOKEN,address=POOL,global_assessment={'category':'REJECTED','reason':'Known adverse evidence'})]}))
            excluded,_=global_engine.prior_exclusions([path])
        self.assertEqual(excluded[key('eth',TOKEN)][0]['reason'],'Known adverse evidence')

class FallbackTests(unittest.TestCase):
    def test_profile_fallback_is_bound_and_never_fetches_profile_links(self):
        from discovery_adapters import ProfileFallback
        calls=[]
        pair=dict(chainId='ethereum',pairAddress=POOL,baseToken={'address':TOKEN,'symbol':'SAME'},priceUsd='1',liquidity={'usd':100000},volume={'h24':200000},txns={'h1':{'buys':60,'sells':40}},priceChange={'h1':2,'h24':10})
        def fetch(url):
            calls.append(url)
            if url.endswith('/token-profiles/latest/v1'):return [dict(chainId='ethereum',tokenAddress=TOKEN,url='http://169.254.169.254/private')]
            return [pair]
        result=ProfileFallback(fetch).discover('eth')
        self.assertEqual(len(result['rows']),1)
        self.assertIn('promotional',result['rows'][0]['source'])
        self.assertTrue(all(url.startswith('https://api.dexscreener.com/') for url in calls))
    def test_wrong_chain_or_base_token_in_fallback_never_admitted(self):
        from discovery_adapters import ProfileFallback
        def fetch(url):
            if url.endswith('/token-profiles/latest/v1'):return [dict(chainId='ethereum',tokenAddress=TOKEN)]
            return [dict(chainId='bsc',pairAddress=POOL,baseToken={'address':TOKEN})]
        self.assertEqual(ProfileFallback(fetch).discover('eth')['rows'],[])

class HistoricalFailureTests(unittest.TestCase):
    def test_old_wait_decision_cannot_erase_known_security_failure(self):
        import tempfile,pathlib,json
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'old.json'
            path.write_text(json.dumps({'candidates':[dict(network='eth',token_address=TOKEN,address=POOL,decision='WAIT AND VERIFY',verification={'contract_security':{'status':'FAIL','reason':'Known balance authority'}})]}))
            excluded,_=global_engine.prior_exclusions([path])
        self.assertIn('Known balance authority',excluded[key('eth',TOKEN)][0]['reason'])
