import copy
import datetime as dt
import unittest
from atl_evidence import dossier, instrument, independent_history, history, notify, DETAILS
from atl_hourly_research import enrich
from atl_monitor_core import labeled_message

NOW=dt.datetime(2026,11,8,3,tzinfo=dt.timezone.utc)
AT=NOW.isoformat()
TOKEN='0x'+'1'*40


def inputs():
    observation=dict(provider_id='example',provider_last_updated=AT,indicative_price_usd='1',
        provider_atl_candidate=dict(source_atl_usd='.99',source_atl_date='2020-01-01T00:00:00Z'))
    details=dict(id='example',name='Fixture',symbol='EX',platforms={'ethereum':TOKEN},categories=['Infrastructure'],
        market_data=dict(current_price={'usd':1},market_cap={'usd':200000000},circulating_supply=200000000,
                         total_volume={'usd':1000000},last_updated=AT))
    chart={'prices':[[int((NOW-dt.timedelta(days=1)).timestamp()*1000),1.1],[int(NOW.timestamp()*1000),1]]}
    return observation,details,chart


def build():
    return dossier(*inputs(),observed_at=AT,now=NOW.timestamp())


def transport(log,wrong=False):
    def call(token,method,data):
        log.append((method,data))
        if method=='getChat':return {'ok':True,'result':{'id':42}}
        return {'ok':True,'result':{'message_id':7,'chat':{'id':43 if wrong else 42}}}
    return call


class ATLEvidenceTests(unittest.TestCase):
    def test_provider_chart_never_establishes_lifetime_or_verified_cap(self):
        d=build()
        self.assertEqual(d['classification'],'UNVERIFIED ATL RESEARCH WATCH')
        self.assertTrue(d['telegram_research_eligible'])
        self.assertFalse(d['history']['lifetime_verified'])
        self.assertEqual(d['history']['independent_sources'],1)
        self.assertIn('NOT_INDEPENDENTLY_VERIFIED',d['market_cap_status'])
        self.assertFalse(d['buy_authorized']);self.assertFalse(d['orders_allowed'])
        self.assertEqual(d['asset']['contracts'],[{'network':'eth','contract':TOKEN}])

    def test_categories_exclude_stablecoin_wrapped_pegged_yield_and_tokenized(self):
        for category in ('Fiat-backed Stablecoins','Wrapped Tokens','Tokenized Treasury Bills','Money Market','Pegged Assets','Yield-Bearing Assets','Liquid Staking'):
            observation,details,chart=inputs();details['categories']=[category]
            d=dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())
            self.assertEqual(d['instrument']['status'],'EXCLUDED',category)
            self.assertFalse(d['telegram_research_eligible'],category)
        self.assertEqual(instrument({'categories':[]})['status'],'UNKNOWN')

    def test_ticker_cannot_replace_exact_identity(self):
        observation,details,chart=inputs();details['id']='other-asset'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())
        observation,details,chart=inputs();details['platforms']={}
        self.assertFalse(dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())['telegram_research_eligible'])

    def test_history_corruption_staleness_and_provider_low_conflict(self):
        observation,details,chart=inputs()
        for prices in ([[NOW.timestamp()*1000,True],[NOW.timestamp()*1000,1]],
                       [[NOW.timestamp()*1000,1],[NOW.timestamp()*1000,1]],
                       [[NOW.timestamp()*1000,1],[(NOW.timestamp()+1)*1000,1]]):
            d=dossier(observation,details,{'prices':prices},observed_at=AT,now=NOW.timestamp())
            self.assertFalse(d['telegram_research_eligible'])
        chart['prices'][0][1]=.5
        d=dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())
        self.assertTrue(d['history']['conflicting']);self.assertFalse(d['telegram_research_eligible'])

    def test_caller_completeness_and_buy_flags_never_validate_history(self):
        d=build();h=copy.deepcopy(d['historical_assessments'][0]);h.update(lifetime_complete=True,independently_verified=True,buy_authorized=True)
        self.assertFalse(independent_history([h])['lifetime_verified'])
        with self.assertRaises(ValueError):labeled_message('BUY CANDIDATE | MANUAL REVIEW','forged')

    def test_strict_cap_boundaries_staleness_and_fdv_not_substituted(self):
        for changes in (dict(market_cap={'usd':4999999},circulating_supply=4999999),dict(market_cap={}),dict(circulating_supply=1),dict(last_updated='2020-01-01T00:00:00Z')):
            observation,details,chart=inputs();details['market_data'].update(changes)
            with self.assertRaises(ValueError):dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())

    def test_transport_confirmed_destination_and_durable_daily_dedup(self):
        state={};log=[];env=dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='42')
        result=notify([build()],state,env,transport(log),now=NOW.timestamp())
        self.assertEqual(result['message_id'],7);self.assertEqual(result['delivered'],1)
        self.assertTrue(log[-1][1]['text'].startswith('🚨 <b>ALL-TIME LOW WATCH</b>\n<i>Unverified ATL Research Watch</i>\n'))
        self.assertEqual(log[-1][1]['parse_mode'],'HTML')
        self.assertIn('NOT A BUY SIGNAL',log[-1][1]['text'])
        result=notify([build()],state,env,transport(log),now=NOW.timestamp())
        self.assertEqual(result['decisions'][0]['status'],'UNCHANGED_CONFIRMED_CONDITION');self.assertEqual(len(log),2)

    def test_distinct_verified_research_receipts_not_blocked_by_first_daily_alert(self):
        state={};log=[];env=dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='42')
        for index in range(3):
            observation,details,chart=inputs()
            identifier='fixture-'+str(index)
            observation['provider_id']=identifier
            details['id']=identifier
            details['name']=identifier
            finding=dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())
            result=notify([finding],state,env,transport(log),now=NOW.timestamp())
            self.assertEqual(result['delivered'],1)
            self.assertFalse(result['buy_authorized'])
        observation,details,chart=inputs()
        observation['provider_id']='fixture-3';details['id']='fixture-3';details['name']='fixture-3'
        fourth=dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())
        self.assertEqual(notify([fourth],state,env,transport(log),now=NOW.timestamp())['status'],'DAILY_LIMIT')
        self.assertEqual(len([x for x in log if x[0]=='sendMessage']),3)

    def test_wrong_receipt_and_forged_summary_never_advance_state(self):
        env=dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='42');state={}
        self.assertEqual(notify([build()],state,env,transport([],wrong=True),now=NOW.timestamp())['failed'],1)
        self.assertEqual(state,{})
        forged={'classification':'UNVERIFIED ATL RESEARCH WATCH','telegram_research_eligible':True,'buy_authorized':False,'orders_allowed':False}
        log=[];self.assertEqual(notify([forged],state,env,transport(log),now=NOW.timestamp())['delivered'],0)
        self.assertEqual(log,[])
        d=build();d['_source_input']['details']['categories']=['Stablecoins'];d['telegram_research_eligible']=True
        self.assertEqual(notify([d],state,env,transport(log),now=NOW.timestamp())['delivered'],0)

    def test_transient_chart_failure_is_retried_on_next_cycle(self):
        observation,details,chart=inputs()
        report={'observations':[observation]}
        state={}
        def unavailable(url):
            if '/market_chart?' in url:
                raise OSError('provider cooldown')
            return details
        enrich(report,state,unavailable,now=NOW)
        self.assertEqual(report['candidate_dispositions'][0]['status'],'HISTORY_UNAVAILABLE')
        self.assertIn('example',state['pending_leads'])
        self.assertNotIn('example',state['evidence_cache'])

        report={'observations':[]}
        enrich(report,state,lambda url: chart if '/market_chart?' in url else details,now=NOW)
        self.assertEqual(state['pending_leads'],{})
        self.assertIn('example',state['evidence_cache'])
        self.assertTrue(report['research_dossiers'][0]['historical_assessments'])
        self.assertFalse(report['research_dossiers'][0]['history']['lifetime_verified'])

    def test_rotation_cache_and_provider_failure_are_bounded(self):
        observation,details,chart=inputs();observations=[]
        for identifier in ('aaa','bbb','ccc'):
            o=copy.deepcopy(observation);o['provider_id']=identifier;observations.append(o)
        state={'version':1,'cursor':2};report={'observations':observations};calls=[]
        def fetch(url):
            calls.append(url);identifier=url[len(DETAILS):].split('?')[0].split('/')[0]
            if '/market_chart?' in url:return chart
            d=copy.deepcopy(details);d['id']=identifier;return d
        enrich(report,state,fetch,now=NOW)
        self.assertEqual(len(calls),4);self.assertEqual(state['enrichment_after'],'bbb')
        self.assertEqual(report['enrichment_deferred'],1)
        enrich(report,state,fetch,now=NOW)
        self.assertEqual(state['enrichment_after'],'aaa');self.assertEqual(len(calls),6)
        def outage(url):raise OSError('unavailable')
        state={};enrich(report,state,outage,now=NOW)
        self.assertEqual(len(report['enrichment_errors']),2)
        self.assertFalse(report['research_dossiers'])

if __name__=='__main__':unittest.main()
