import copy
import datetime as dt
import json
import tempfile
import unittest
from unittest.mock import patch
import opportunity_alerts as alerts
from verification import observation

NOW=1800000000
STAMP=dt.datetime.fromtimestamp(NOW,dt.timezone.utc).isoformat()
TOKEN='0x'+'1'*40
POOL='0x'+'2'*40


def candidate():
    fields={'is_honeypot':'0','cannot_sell_all':'0','owner_change_balance':'0','hidden_owner':'0','is_blacklisted':'0','is_open_source':'1','is_mintable':'0','trading_cooldown':'0','is_proxy':'0','transfer_pausable':'0','slippage_modifiable':'0','personal_slippage_modifiable':'0','selfdestruct':'0'}
    return dict(key='base:'+POOL,network='base',address=POOL,token_address=TOKEN,name='Fixture — not live',age_hours=12,
        token_identity_status='Base token from GeckoTerminal pool relationship',observed_at=STAMP,
        liquidity=350000,volume=800000,trades=220,buy_share=.58,change_h1=6,change_h24=18,
        base_token_price_usd=.05,score=99,flags=[],risk_category='RESEARCH CANDIDATE — LIMITED CHECKS',
        price_source='Fixture only',url='https://www.geckoterminal.com/base/pools/'+POOL,
        mandatory_blockers=['Beneficial ownership UNKNOWN','Complete unlock inventory UNKNOWN','Funded executable quotes and risk UNKNOWN'],
        market_corroboration=dict(status='CORROBORATED',observed_at=STAMP),
        verification={'contract_security':dict(source='goplus',url='https://api.gopluslabs.io/api/v1/token_security/8453?contract_addresses='+TOKEN,observed_at=STAMP,status='LIMITED',reason='Preliminary screen only',raw={'code':1,'result':{TOKEN:fields}})})


def breakout(item):
    item['base_token_price_usd']=11.2
    bars=[]
    end=NOW//300*300-300
    for i in range(21):
        bars.append([end-(20-i)*300,10,11,9,10,100])
    bars[-1]=[end,10,11.3,9,11.2,200]
    item['verification']['entry']=dict(source='ohlcv',observed_at=STAMP,url=f'https://api.geckoterminal.com/api/v2/networks/base/pools/{POOL}/ohlcv/minute?aggregate=5&limit=30&currency=usd&token=base',raw={'data':{'attributes':{'ohlcv_list':bars}}})
    return item


class ClassificationTests(unittest.TestCase):
    def test_useful_watch_is_not_buy(self):
        result=alerts.classify(candidate(),now=NOW)
        self.assertEqual(result['classification'],'HIGH-PRIORITY WATCH');self.assertFalse(result['eligible_for_buy'])
        self.assertEqual(result['missing_checks'],candidate()['mandatory_blockers'])
        self.assertAlmostEqual(result['score'],sum(result['components'].values()))
    def test_existing_buy_gate_cannot_be_overridden_by_watch_score(self):
        item=candidate();item.update(sellability_verified=True,tokenomics_verified=True,executable_quote_verified=True)
        self.assertNotEqual(alerts.classify(item,now=NOW)['classification'],'VERIFIED BUY')
    def test_security_failures_win_even_with_high_score(self):
        for check in alerts.CRITICAL:
            item=candidate();item['verification'][check]={'status':'FAIL','reason':'Known adverse evidence'}
            self.assertEqual(alerts.classify(item,now=NOW)['classification'],'REJECT',check)
    def test_caller_clear_label_cannot_hide_raw_mint_or_honeypot_flag(self):
        for field in ('is_honeypot','owner_change_balance','is_mintable','is_proxy'):
            item=candidate();item['verification']['contract_security']['raw']['result'][TOKEN][field]='1'
            self.assertEqual(alerts.classify(item,now=NOW)['classification'],'REJECT')
    def test_unknown_security_is_silent(self):
        item=candidate();del item['verification']['contract_security']['raw']['result'][TOKEN]['cannot_sell_all']
        self.assertEqual(alerts.classify(item,now=NOW)['classification'],'INELIGIBLE')
    def test_unknown_extended_fields_are_disclosed_without_granting_buy(self):
        item=candidate();del item['verification']['contract_security']['raw']['result'][TOKEN]['trading_cooldown']
        item['verification']['contract_security']['status']='UNKNOWN'
        result=alerts.classify(item,now=NOW)
        self.assertEqual(result['classification'],'HIGH-PRIORITY WATCH')
        self.assertIn('trading_cooldown',result['missing_checks'][-1]);self.assertFalse(result['eligible_for_buy'])

    def test_wrong_chain_or_contract_is_not_a_watch(self):
        for mutate in ('chain','token'):
            item=candidate()
            if mutate=='chain':item['verification']['contract_security']['url']=item['verification']['contract_security']['url'].replace('/8453','/1')
            else:item['token_address']='0x'+'3'*40
            self.assertEqual(alerts.classify(item,now=NOW)['classification'],'INELIGIBLE')
    def test_stale_future_nonfinite_and_uncorroborated_data(self):
        for key,value in [('observed_at','2020-01-01T00:00:00+00:00'),('observed_at','2090-01-01T00:00:00+00:00'),('liquidity',float('nan')),('change_h1',60),('buy_share',.95),('trades',None)]:
            item=candidate();item[key]=value
            self.assertEqual(alerts.classify(item,now=NOW)['classification'],'INELIGIBLE',(key,value))
        item=candidate();item['market_corroboration']['status']='CONFLICTING'
        self.assertEqual(alerts.classify(item,now=NOW)['classification'],'INELIGIBLE')
    def test_entry_requires_real_bound_closed_volume_supported_candles(self):
        item=breakout(candidate());r=alerts.classify(item,now=NOW)
        self.assertEqual(r['classification'],'ENTRY WATCH');self.assertEqual(r['entry']['entry_reference'],11.2);self.assertEqual(r['entry']['invalidation'],9)
        item['verification']['entry']['url']=item['verification']['entry']['url'].replace(POOL,'wrongpool')
        self.assertEqual(alerts.classify(item,now=NOW)['classification'],'HIGH-PRIORITY WATCH')
    def test_fabricated_entry_analysis_and_low_volume_do_not_qualify(self):
        item=breakout(candidate());item['verification']['entry']['raw']['data']['attributes']['ohlcv_list'][-1][-1]=10
        item['verification']['entry']['analysis']={'status':'LIMITED','entry_reference':999}
        self.assertEqual(alerts.classify(item,now=NOW)['classification'],'HIGH-PRIORITY WATCH')
    def test_entry_far_from_current_price_is_not_promoted(self):
        item=breakout(candidate());item['base_token_price_usd']=14
        self.assertEqual(alerts.classify(item,now=NOW)['classification'],'HIGH-PRIORITY WATCH')

    def test_config_cannot_turn_off_security_or_allow_stale_market(self):
        with tempfile.NamedTemporaryFile(mode='w+',suffix='.json') as f:
            config=alerts.policy();config['maximum_market_age_seconds']=999999
            json.dump(config,f);f.flush()
            with self.assertRaises(ValueError):alerts.policy(f.name)


class StateTests(unittest.TestCase):
    def setUp(self):self.item=candidate();self.result=alerts.classify(self.item,now=NOW);self.state={}
    def first(self):
        p=alerts.plan(self.item,self.result,self.state,now=NOW);alerts.acknowledge(self.state,self.item['key'],p);return p
    def test_no_initial_wait_or_reject_spam(self):
        for category in ('INELIGIBLE','REJECT'):
            r=dict(self.result,classification=category)
            self.assertIsNone(alerts.plan(self.item,r,{},now=NOW))
    def test_dedup_survives_persistence_and_timestamp_changes(self):
        self.first();state=json.loads(json.dumps(self.state));self.item['observed_at']=dt.datetime.fromtimestamp(NOW+3600,dt.timezone.utc).isoformat()
        self.assertIsNone(alerts.plan(self.item,self.result,state,now=NOW+3600))
    def test_failures_retry_without_marking_delivered(self):
        p=alerts.plan(self.item,self.result,self.state,now=NOW);alerts.failed(self.state,self.item['key'],NOW)
        self.assertNotIn('delivered',self.state[self.item['key']]);self.assertIsNone(alerts.plan(self.item,self.result,self.state,now=NOW+1))
        self.assertEqual(alerts.plan(self.item,self.result,self.state,now=NOW+301)['fingerprint'],p['fingerprint'])
    def test_rejection_bypasses_cooldown_and_sends_once(self):
        self.first();r=dict(self.result,classification='REJECT',reasons=['New honeypot report'])
        p=alerts.plan(self.item,r,self.state,now=NOW+1);self.assertIn('ADVERSE',p['event']);alerts.acknowledge(self.state,self.item['key'],p)
        self.assertIsNone(alerts.plan(self.item,r,self.state,now=NOW+3601))
    def test_known_failure_is_persisted_even_when_next_provider_omits_it(self):
        r=dict(self.result,classification='REJECT',reasons=['Known honeypot']);alerts.plan(self.item,r,self.state,now=NOW)
        self.item['persistent_adverse_reasons']=self.state[self.item['key']]['unresolved_adverse_reasons']
        self.assertEqual(alerts.classify(self.item,now=NOW)['classification'],'REJECT')
    def test_unknown_refresh_invalidates_previous_watch_once(self):
        self.first();r=dict(self.result,classification='INELIGIBLE',reasons=['Provider unavailable'])
        p=alerts.plan(self.item,r,self.state,now=NOW+1);self.assertIn('INVALIDATED',p['event']);alerts.acknowledge(self.state,self.item['key'],p)
        self.assertIsNone(alerts.plan(self.item,r,self.state,now=NOW+4000))
    def test_new_scoped_evidence_and_improvement_respect_cooldown(self):
        self.first();self.item['verification']['custody']={'status':'LIMITED'}
        self.assertIsNone(alerts.plan(self.item,self.result,self.state,now=NOW+5))
        p=alerts.plan(self.item,self.result,self.state,now=NOW+1801);self.assertIn('NEW EVIDENCE',p['event'])
    def test_deterioration_and_entry_invalidation(self):
        self.result=dict(self.result,classification='ENTRY WATCH',entry={'invalidation':.04,'entry_reference':.05,'candle_at':NOW-300});self.first()
        self.item['base_token_price_usd']=.039
        self.assertIn('ENTRY INVALIDATED',alerts.plan(self.item,self.result,self.state,now=NOW+5)['event'])
    def test_entry_upgrade(self):
        self.first();r=dict(self.result,classification='ENTRY WATCH')
        self.assertIn('ENTRY WATCH',alerts.plan(self.item,r,self.state,now=NOW+1801)['event'])


class FormattingDeliveryTests(unittest.TestCase):
    def test_all_missing_checks_survive_chunking_with_unicode(self):
        item=candidate();r=alerts.classify(item,now=NOW);r['missing_checks']=['Missing-'+str(i)+' 🔎'*50 for i in range(80)]
        message=alerts.format_alert(item,r,example=True);parts=alerts.chunks(message)
        self.assertIn('EXAMPLE — NOT A LIVE SIGNAL',message);self.assertIn('NOT A VERIFIED BUY SIGNAL',message)
        self.assertIn(TOKEN,message);self.assertIn('Missing-79',''.join(parts));self.assertIn('Valuation: UNKNOWN',message)
        self.assertTrue(all(len(x.encode('utf-16-le'))//2<=4096 for x in parts))
    def test_destination_mismatch_never_acknowledged(self):
        item=candidate();r=alerts.classify(item,now=NOW)
        with self.assertRaises(RuntimeError):alerts.deliver(item,r,'NEW',{'TELEGRAM_BOT_TOKEN':'fixture','TELEGRAM_CHAT_ID':'42'},transport=lambda *a:{'ok':True,'result':{'id':43}})
    def test_multipart_failure_resumes_only_confirmed_parts(self):
        item=candidate();r=alerts.classify(item,now=NOW);r['missing_checks']=['long '*1600];state={};p=alerts.plan(item,r,state,now=NOW);sent=[];saved=[]
        def fail(token,method,data):
            if method=='getChat':return {'ok':True,'result':{'id':42}}
            sent.append(data['text'])
            if len(sent)==2:raise OSError('fixture transport failure')
            return {'ok':True,'result':{'message_id':1,'chat':{'id':42}}}
        env={'TELEGRAM_BOT_TOKEN':'fixture','TELEGRAM_CHAT_ID':'42'}
        with self.assertRaises(OSError):alerts.send_notification(item,r,p,state,env,lambda:saved.append(copy.deepcopy(state)),transport=fail)
        self.assertNotIn('delivered',state[item['key']]);self.assertEqual(state[item['key']]['pending_delivery']['completed'],[0])
        retry=[]
        def success(token,method,data):
            if method=='getChat':return {'ok':True,'result':{'id':42}}
            retry.append(data['text']);return {'ok':True,'result':{'message_id':2,'chat':{'id':42}}}
        state=json.loads(json.dumps(saved[-1]));alerts.send_notification(item,r,p,state,env,lambda:None,transport=success)
        self.assertNotIn(sent[0],retry);self.assertIn('delivered',state[item['key']]);self.assertNotIn('pending_delivery',state[item['key']])

if __name__=='__main__':unittest.main()
